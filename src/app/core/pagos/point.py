"""Pago con terminal Point (Mercado Pago).

Flujo:
1. `iniciar()` llama al adaptador `point.crear_orden_point()` para enviar la
   orden a la terminal NEWLAND N950.
2. La orden local pasa a `Pendiente-pago` con `mp_order_id`.
3. El polling global de `adaptadores/mercado_pago/polling.py` confirma el
   pago automáticamente y publica `pago.confirmado` en el bus.
4. El kiosko se suscribe a `pago.confirmado` y avanza a paso de éxito.

Mientras la confirmación no llega, el kiosko muestra un overlay de espera.
"""

import asyncio
from dataclasses import replace as _r
from nicegui import ui

from app.adaptadores.mercado_pago import point as mp_point
from app.core.estados import MetodoPago
from app.core.pagos.estrategia import ContextoPago, MetodoPagoStrategy
from app.core.precio import calcular_precio
from app.repo import transacciones
from app.ui.compartido.estilos import badge_metodo_pago


class MetodoPoint(MetodoPagoStrategy):
    codigo = MetodoPago.POINT
    nombre = "Punto Point"
    icono = "/media/icons/ticket.svg"
    descripcion = "Paga con tarjeta en la terminal Point"

    def render_panel(self, ctx: ContextoPago) -> None:
        w = ctx.wizard
        precio = w.precio_total()

        with ui.element("div").props("id=pago-panel"):
            ui.html(
                '<p style="font-size:0.88rem;color:#94a3b8;margin:0 0 2px;'
                'font-weight:600;">Cliente</p>'
            )
            ui.html(
                f'<p style="font-size:1.3rem;font-weight:800;color:#e2e8f0;'
                f'margin:0 0 4px;">{w.nombre or "—"}</p>'
            )
            ui.html(
                f'<p style="font-size:0.82rem;color:#64748b;margin:0 0 2px;">'
                f'Servicio: <strong style="color:#93c5fd;">{w.servicio.nombre if w.servicio else "—"}</strong></p>'
            )
            if w.peso > 0:
                ui.html(
                    f'<p style="font-size:0.82rem;color:#64748b;margin:0 0 10px;">'
                    f'Peso: <strong style="color:#93c5fd;">{w.peso} kg</strong></p>'
                )
            ui.html(
                f'<div style="margin:0 0 8px;">{badge_metodo_pago(self.codigo.value)}</div>'
            )

            with ui.element("div").classes("monto-box"):
                ui.html('<div class="monto-label">Total a pagar</div>')
                ui.html(f'<div class="monto-valor">${precio}</div>')
                ui.html(
                    '<div class="monto-sub">'
                    "Al continuar, se enviará la orden a la terminal Point"
                    "</div>"
                )

            ui.button(
                "Pagar con Point",
                color="green",
                on_click=lambda: _iniciar_cobro_point(ctx),
            ).classes("w-full text-lg font-bold py-3").style("margin-top:16px;")

            ui.button("Cancelar y regresar", color="red").classes("btn-cancelar").on(
                "click", lambda: ctx.on_cancelar()
            )


async def _iniciar_cobro_point(ctx: ContextoPago) -> None:
    w = ctx.wizard
    if w.ultimo_id_transaccion is None or w.servicio is None:
        ui.notify(
            "No hay una orden activa. Vuelve a ingresar el peso.",
            type="negative",
        )
        return
    item = w.segmentacion or w.servicio
    monto = calcular_precio(item, w.peso)
    descripcion = f"EcoLuna - {w.servicio.nombre}"
    ref = f"ECOLUNA_KIOSKO_{w.ultimo_id_transaccion}"

    # Llamada bloqueante a MP en hilo separado para no congelar el kiosko
    order = await asyncio.to_thread(
        mp_point.crear_orden_point,
        monto,
        descripcion,
        ref,
    )
    mp_order_id = str(order.get("id", "")) if order else ""
    if not mp_order_id:
        ui.notify(
            "No se pudo conectar con la terminal Point. Intenta de nuevo.",
            type="negative",
            position="top",
            timeout=6000,
        )
        return

    base = "personalizado" if w.servicio.es_personalizado else "autoservicio"
    modalidad = f"{base}-{MetodoPago.POINT.value}"
    new_id = await transacciones.marcar_pendiente_pago(
        w.ultimo_id_transaccion,
        monto,
        modalidad,
        mp_order_id=mp_order_id,
    )
    if new_id is None:
        ui.notify(
            "La orden ya no está disponible. Vuelve a intentar.",
            type="negative",
            position="top",
        )
        ctx.refresh(w.reset())
        return

    nuevo = _r(w, metodo=MetodoPago.POINT).empezar_espera("pago", "point")
    ctx.refresh(nuevo)
