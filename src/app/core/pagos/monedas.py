"""Pago en monedas. Es inmediato: cuando el dinero cubre el precio, la orden
pasa a `Pendiente` y se publica `pago.confirmado` en el bus."""

from dataclasses import replace as _r
from nicegui import ui

from app.core.estados import MetodoPago
from app.core.pagos.estrategia import ContextoPago, MetodoPagoStrategy
from app.core.precio import calcular_precio
from app.eventos.tipos import pago_confirmado
from app.eventos.bus import bus
from app.repo import transacciones
from app.ui.compartido.estilos import badge_metodo_pago


class MetodoMonedas(MetodoPagoStrategy):
    codigo = MetodoPago.MONEDAS
    nombre = "Monedas"
    icono = "/media/icons/money-bag.svg"
    descripcion = "Inserta monedas tú mismo"

    def render_panel(self, ctx: ContextoPago) -> None:
        w = ctx.wizard
        precio = w.precio_total()
        faltante = max(0, precio - w.dinero)
        pct = min(100, int(w.dinero / precio * 100)) if precio > 0 else 100

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
                ui.html('<div class="monto-label">Falta por insertar</div>')
                ui.html(f'<div class="monto-valor">${faltante}</div>')
                ui.html(
                    f'<div class="monto-sub">Ingresado ${w.dinero} de ${precio}</div>'
                )

            ui.html(
                f'<div class="progress-bar-bg">'
                f'<div class="progress-bar-fill" style="width:{pct}%;"></div>'
                f"</div>"
            )
            ui.html(
                f'<div class="progress-pct">{pct}% completado — '
                f"inserte monedas en el dispensador</div>"
            )

            btn = ui.button("Confirmar y Registrar Pago")
            if w.dinero >= precio:
                btn.on("click", lambda: _confirmar(ctx))
                btn.style(
                    "width:100%; margin-top:16px; padding:14px; font-size:1.1rem; "
                    "font-weight:700; cursor:pointer;"
                )
            else:
                btn.disable()
                btn.style(
                    "width:100%; margin-top:16px; padding:14px; background:#1e293b; "
                    "color:#475569; border-radius:11px; font-size:1.1rem; "
                    "font-weight:700; cursor:not-allowed;"
                )

            ui.button("Cancelar y regresar", color="red").classes("btn-cancelar").on(
                "click", lambda: ctx.on_cancelar()
            )


async def _confirmar(ctx: ContextoPago) -> None:
    """Confirma el pago en monedas y avanza al paso de éxito."""
    w = ctx.wizard
    if w.ultimo_id_transaccion is None:
        ui.notify(
            "No hay una orden activa. Vuelve a ingresar el peso.",
            type="negative",
            position="top",
        )
        return
    if w.servicio is None:
        return
    base = "personalizado" if w.servicio.es_personalizado else "autoservicio"
    modalidad = f"{base}-{MetodoPago.MONEDAS.value}"
    item = w.segmentacion or w.servicio
    precio = calcular_precio(item, w.peso)
    cambio = max(0, w.dinero - precio)

    new_id = await transacciones.guardar_pago_orden(
        w.ultimo_id_transaccion,
        precio,
        w.dinero,
        cambio,
        modalidad,
    )
    if new_id is None:
        ui.notify(
            "La orden ya no está disponible. Reiniciando…",
            type="negative",
            position="top",
        )
        ctx.refresh(w.reset())
        return

    # Sincronizar el tipo_servicio en la BD si hay segmentación
    if w.segmentacion and w.servicio:
        await transacciones.actualizar_tipo_servicio(
            new_id,
            f"{w.servicio.nombre} · {w.segmentacion.nombre}",
        )

    nuevo = _r(w, metodo=MetodoPago.MONEDAS).ir_a_exito(new_id)
    bus.publish(pago_confirmado(new_id, folio=""))
    ctx.refresh(nuevo)
