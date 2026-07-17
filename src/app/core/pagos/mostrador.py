"""Pago en mostrador. El cliente indica que pagará en efectivo en mostrador.

La orden queda en `Pendiente-pago` con modalidad `personalizado-mostrador` (o
`autoservicio-mostrador`). El operador registra el pago desde el panel admin,
lo que confirma la orden y publica `pago.confirmado` en el bus.
"""

from nicegui import ui

from app.core.estados import MetodoPago
from app.core.pagos.estrategia import ContextoPago, MetodoPagoStrategy
from app.core.precio import calcular_precio
from app.repo import transacciones
from app.ui.compartido.estilos import badge_metodo_pago


class MetodoMostrador(MetodoPagoStrategy):
    codigo = MetodoPago.MOSTRADOR
    nombre = "Mostrador"
    icono = "/media/icons/ticket.svg"
    descripcion = "Paga en efectivo en el mostrador"

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
                ui.html('<div class="monto-label">Total a pagar en mostrador</div>')
                ui.html(f'<div class="monto-valor">${precio}</div>')
                ui.html(
                    '<div class="monto-sub">'
                    "Al continuar, el operador cobrará en mostrador"
                    "</div>"
                )

            ui.button(
                "Pagar en mostrador al recibir",
                on_click=lambda: _solicitar_pago_mostrador(ctx),
            ).classes("btn-confirmar-nombre max-w-sm mx-auto mt-4").style(
                "background:#a78bfa;width:100%;font-weight:700;"
            )

            ui.button("Cancelar y regresar", color="red").classes("btn-cancelar").on(
                "click", lambda: ctx.on_cancelar()
            )


async def _solicitar_pago_mostrador(ctx: ContextoPago) -> None:
    from dataclasses import replace as _r

    w = ctx.wizard
    if w.ultimo_id_transaccion is None:
        ui.notify(
            "No hay una orden activa. Vuelve a ingresar el peso.",
            type="negative",
        )
        return
    if w.servicio is None:
        return
    base = "personalizado" if w.servicio.es_personalizado else "autoservicio"
    modalidad = f"{base}-{MetodoPago.MOSTRADOR.value}"
    item = w.segmentacion or w.servicio
    precio = calcular_precio(item, w.peso)

    new_id = await transacciones.marcar_pendiente_pago(
        w.ultimo_id_transaccion,
        precio,
        modalidad,
    )
    if new_id is None:
        ui.notify(
            "La orden ya no está disponible. Vuelve a intentar.",
            type="negative",
            position="top",
        )
        ctx.refresh(w.reset())
        return

    nuevo = _r(w, metodo=MetodoPago.MOSTRADOR).empezar_espera("pago", "mostrador")
    ctx.refresh(nuevo)
