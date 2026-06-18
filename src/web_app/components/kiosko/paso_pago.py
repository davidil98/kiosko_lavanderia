import asyncio
from nicegui import ui
from metodos_pago import MetodoMonedas
from services.notifications import state, get_kiosko_ui_ref, notificar_admin
from components.kiosko.paso_peso import _eliminar_orden_activa_si_existe


def render_paso_pago():
    if not state.metodo_pago_instancia:
        state.metodo_pago_instancia = MetodoMonedas(state)
        state.metodo_pago_codigo = "monedas"

    async def _on_cancelar():
        async def _confirmar_cancelacion():
            await _eliminar_orden_activa_si_existe(
                state.ultimo_id_transaccion
            )
            state.ultimo_id_transaccion = None
            if state.metodo_pago_instancia is not None and hasattr(
                state.metodo_pago_instancia, "cancelar"
            ):
                await state.metodo_pago_instancia.cancelar()
            state.reset()
            kiosko_ref = get_kiosko_ui_ref()
            if kiosko_ref:
                kiosko_ref()
            notificar_admin()

        if (
            state.metodo_pago_codigo == "monedas"
            and state.dinero_ingresado > 0
        ):
            with ui.dialog() as dialog, ui.card():
                ui.label("Advertencia").style(
                    "font-size:1.25rem;font-weight:bold;color:#ef4444;margin-bottom:8px;"
                )
                ui.label(
                    "Tienes saldo ingresado. ¿Deseas cancelar? Deberías reclamarlo en mostrador."
                ).style("color:#64748b;white-space:normal;")
                with ui.row().style(
                    "width:100%;justify-content:flex-end;margin-top:16px;gap:8px;"
                ):
                    ui.button("No, continuar", on_click=dialog.close)
                    ui.button(
                        "Sí, cancelar",
                        on_click=lambda: (
                            dialog.close(),
                            asyncio.create_task(_confirmar_cancelacion()),
                        ),
                        color="red",
                    )
            dialog.open()
            return
        await _confirmar_cancelacion()

    async def _on_pago_exitoso():
        from pages.kiosko import finalizar_pago

        await finalizar_pago()

    state.metodo_pago_instancia.render_panel(
        on_cancelar=_on_cancelar,
        on_pago_exitoso=_on_pago_exitoso,
    )
