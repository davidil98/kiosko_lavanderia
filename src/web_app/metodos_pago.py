from abc import ABC, abstractmethod
from typing import Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from models import KioskoState


class ResultadoPago:
    """Estandariza el resultado de cualquier intento de pago."""

    def __init__(self, exito: bool, mensaje: str = "", datos: Optional[dict] = None):
        self.exito = exito
        self.mensaje = mensaje
        self.datos = datos or {}


class MetodoPago(ABC):
    """Clase base para todos los métodos de pago (Strategy pattern + Open/Close)."""

    codigo: str = "base"
    nombre: str = "Método"
    icono: str = "/media/icons/leaf.svg"
    descripcion: str = ""

    def __init__(self, state: "KioskoState"):
        self.state = state

    @abstractmethod
    async def procesar_pago(self) -> ResultadoPago:
        """Inicia o ejecuta el flujo de pago. Puede ser asíncrono (polling)."""
        raise NotImplementedError

    @abstractmethod
    def render_panel(self, on_cancelar: Callable, on_pago_exitoso: Callable) -> None:
        """Renderiza el panel NiceGUI con los controles del método."""
        raise NotImplementedError


class MetodoMonedas(MetodoPago):
    codigo = "monedas"
    nombre = "Monedas"
    icono = "/media/icons/money-bag.svg"
    descripcion = "Inserta monedas tú mismo"

    async def procesar_pago(self) -> ResultadoPago:
        return ResultadoPago(
            exito=True,
            datos={"monto": self.state.servicio_seleccionado.precio},
        )

    def render_panel(self, on_cancelar, on_pago_exitoso):
        from nicegui import ui

        with ui.element("div").props("id=pago-panel"):
            ui.html(
                '<p style="font-size:0.88rem;color:#94a3b8;margin:0 0 2px;font-weight:600;">Cliente</p>'
            )
            ui.html(
                f'<p style="font-size:1.3rem;font-weight:800;color:#e2e8f0;margin:0 0 4px;">{self.state.nombre_cliente}</p>'
            )
            ui.html(
                f'<p style="font-size:0.82rem;color:#64748b;margin:0 0 2px;">Servicio: <strong style="color:#93c5fd;">{self.state.servicio_seleccionado.nombre}</strong></p>'
            )
            ui.html(
                f'<p style="font-size:0.82rem;color:#64748b;margin:0 0 10px;">Peso: <strong style="color:#93c5fd;">{self.state.peso_ingresado} kg</strong></p>'
            )

            faltante = self.state.get_faltante()
            pct = (
                min(
                    100,
                    int(
                        self.state.dinero_ingresado
                        / self.state.servicio_seleccionado.precio
                        * 100
                    ),
                )
                if self.state.servicio_seleccionado.precio > 0
                else 100
            )

            with ui.element("div").classes("monto-box"):
                ui.html('<div class="monto-label">Falta por insertar</div>')
                ui.html(f'<div class="monto-valor">${faltante}</div>')
                ui.html(
                    f'<div class="monto-sub">Ingresado ${self.state.dinero_ingresado} de ${self.state.servicio_seleccionado.precio}</div>'
                )

            ui.html(
                f'<div class="progress-bar-bg"><div class="progress-bar-fill" style="width:{pct}%;"></div></div>'
            )
            ui.html(
                f'<div class="progress-pct">{pct}% completado — inserte monedas en el dispensador</div>'
            )

            btn_confirmar = ui.button("Confirmar y Registrar Pago")
            if self.state.puede_pagar():
                btn_confirmar.on("click", on_pago_exitoso)
                btn_confirmar.style(
                    "width:100%; margin-top:16px; padding:14px; font-size:1.1rem; font-weight:700; cursor:pointer;"
                )
            else:
                btn_confirmar.disable()
                btn_confirmar.style(
                    "width:100%; margin-top:16px; padding:14px; background:#1e293b; color:#475569; border-radius:11px; font-size:1.1rem; font-weight:700; cursor:not-allowed;"
                )

            ui.button("Cancelar y regresar", color="red").classes("btn-cancelar").on(
                "click", on_cancelar
            )


class MetodoTerminalPoint(MetodoPago):
    codigo = "terminal"
    nombre = "Punto Point"
    icono = "/media/icons/ticket.svg"
    descripcion = "Paga con tarjeta en la terminal Point"

    async def procesar_pago(self) -> ResultadoPago:
        return ResultadoPago(
            exito=True,
            datos={"monto": self.state.servicio_seleccionado.precio},
        )

    def render_panel(self, on_cancelar, on_pago_exitoso):
        import asyncio
        import database_web
        from nicegui import ui
        from services import mercadopago

        state = self.state

        with ui.element("div").props("id=pago-panel"):
            ui.html(
                '<p style="font-size:0.88rem;color:#94a3b8;margin:0 0 2px;font-weight:600;">Cliente</p>'
            )
            ui.html(
                f'<p style="font-size:1.3rem;font-weight:800;color:#e2e8f0;margin:0 0 4px;">{state.nombre_cliente}</p>'
            )
            ui.html(
                f'<p style="font-size:0.82rem;color:#64748b;margin:0 0 2px;">Servicio: <strong style="color:#93c5fd;">{state.servicio_seleccionado.nombre}</strong></p>'
            )
            ui.html(
                f'<p style="font-size:0.82rem;color:#64748b;margin:0 0 10px;">Peso: <strong style="color:#93c5fd;">{state.peso_ingresado} kg</strong></p>'
            )

            with ui.element("div").classes("monto-box"):
                ui.html('<div class="monto-label">Total a pagar</div>')
                ui.html(
                    f'<div class="monto-valor">${state.servicio_seleccionado.precio}</div>'
                )
                ui.html(
                    '<div class="monto-sub">Al continuar, se enviará la orden a la terminal Point</div>'
                )

            async def _iniciar_cobro_point():
                if state.ultimo_id_transaccion is None:
                    ui.notify(
                        "No hay una orden activa. Vuelve a ingresar el peso.",
                        type="negative",
                    )
                    return
                monto = state.servicio_seleccionado.precio
                descripcion = f"EcoLuna - {state.servicio_seleccionado.nombre}"
                ref = f"ECOLUNA_KIOSKO_{state.ultimo_id_transaccion}"

                # Llamada bloqueante a MP en hilo separado para no congelar el kiosko
                order = await asyncio.to_thread(
                    mercadopago.crear_orden_point, monto, descripcion, ref
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

                base = state.servicio_seleccionado.modalidad or "autoservicio"
                id_orden = await database_web.marcar_pendiente_pago_async(
                    state.ultimo_id_transaccion,
                    monto,
                    modalidad=f"{base}-point",
                    mp_order_id=mp_order_id,
                )
                if id_orden is None:
                    # Fallback: crear registro nuevo
                    id_orden = (
                        await database_web.registrar_venta_pendiente_terminal_async(
                            servicio=state.servicio_seleccionado.nombre,
                            peso_kg=state.peso_ingresado,
                            monto=monto,
                            nombre_cliente=state.nombre_cliente,
                            duracion=state.servicio_seleccionado.duracion_min,
                            modalidad=f"{base}-point",
                        )
                    )
                    # Guardar mp_order_id en la nueva fila
                    await database_web.guardar_mp_order_id_async(id_orden, mp_order_id)
                state.ultimo_id_transaccion = id_orden
                state.metodo_pago_codigo = "point"
                state.marcar_esperando_admin("pago")
                if callable(getattr(state, "notificar_admin", None)):
                    state.notificar_admin()

            ui.button(
                "Pagar con Point",
                color="green",
                on_click=_iniciar_cobro_point,
            ).classes("w-full text-lg font-bold py-3").style("margin-top:16px;")

            ui.button("Cancelar y regresar", color="red").classes("btn-cancelar").on(
                "click", on_cancelar
            )


async def _async_sleep(secs: float) -> None:
    import asyncio

    await asyncio.sleep(secs)


METODOS_PAGO_DISPONIBLES = [MetodoMonedas, MetodoTerminalPoint]
