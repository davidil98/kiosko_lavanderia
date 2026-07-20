"""Paso 4: Pagar.

Muestra las tarjetas de los métodos de pago disponibles. Al elegir uno,
delega al `MetodoPago` correspondiente (Strategy pattern). El método renderiza
su panel y, cuando el cliente confirma, llama al `iniciar` que persiste la
orden y (si aplica) publica `pago.confirmado` en el bus.
"""

import asyncio

from nicegui import ui

from app.core.pagos import METODOS_PAGO_DISPONIBLES
from app.core.pagos.estrategia import ContextoPago
from app.core.estados import MetodoPago
from app.repo import transacciones
from app.ui.kiosko.wizard import Sub, WizardKiosko


def render_paso_pago(wizard: WizardKiosko, refresh) -> None:
    if wizard.sub is Sub.METODOS_PAGO:
        _render_metodos_pago(wizard, refresh)
        return
    if wizard.metodo is not None:
        _render_panel_metodo(wizard, refresh)
        return
    # Sin método seleccionado: mostrar selección
    refresh(wizard.mostrar_metodos_pago())


def _render_metodos_pago(wizard: WizardKiosko, refresh) -> None:
    es_personalizado = wizard.servicio is not None and wizard.servicio.es_personalizado

    ui.html('<p class="instruccion">¿Cómo deseas pagar?</p>')
    with ui.element("div").style(
        "display:flex; gap:24px; flex-wrap:wrap; justify-content:center;"
    ):
        for metodo in METODOS_PAGO_DISPONIBLES:
            # En personalizado, no se ofrece pago en monedas.
            if es_personalizado and metodo.codigo is MetodoPago.MONEDAS:
                continue
            with (
                ui.element("div")
                .classes("card-servicio")
                .on(
                    "click",
                    lambda m=metodo: refresh(
                        wizard.seleccionar_metodo(m.codigo).iniciar_pago()
                    ),
                )
            ):
                ui.html(
                    f'<img src="{metodo.icono}" '
                    f'style="width:80px;height:80px;object-fit:contain;" '
                    f'alt="{metodo.nombre}">'
                )
                ui.html(
                    f'<span style="font-size:1.2rem;font-weight:800;color:#e2e8f0;">{metodo.nombre}</span>'
                )
                ui.html(
                    f'<span style="font-size:0.78rem;color:#94a3b8;">{metodo.descripcion}</span>'
                )

    async def _cancelar() -> None:
        if wizard.ultimo_id_transaccion is not None:
            await transacciones.eliminar_si_activa(wizard.ultimo_id_transaccion)
        refresh(wizard.reset())

    ui.button(
        "✕ Cancelar orden",
        on_click=lambda: asyncio.create_task(_cancelar()),
    ).classes("btn-confirmar-nombre max-w-xs mx-auto mt-6").style(
        "background:#991b1b;color:#fecaca;"
    )


def _render_panel_metodo(wizard: WizardKiosko, refresh) -> None:
    metodo = _metodo_por_codigo(wizard.metodo)
    if metodo is None:
        refresh(wizard.reset())
        return
    ctx = ContextoPago(
        wizard=wizard,
        on_cancelar=lambda: asyncio.create_task(_cancelar_pago(wizard, refresh)),
        refresh=refresh,
    )
    metodo.render_panel(ctx)


async def _cancelar_pago(wizard: WizardKiosko, refresh) -> None:
    if wizard.dinero > 0 and wizard.metodo is MetodoPago.MONEDAS:
        with ui.dialog() as dialog, ui.card():
            ui.label("Advertencia").style(
                "font-size:1.25rem;font-weight:bold;color:#ef4444;margin-bottom:8px;"
            )
            ui.label(
                "Tienes saldo ingresado. ¿Deseas cancelar? "
                "Deberías reclamarlo en mostrador."
            ).style("color:#64748b;white-space:normal;")
            with ui.row().style(
                "width:100%;justify-content:flex-end;margin-top:16px;gap:8px;"
            ):
                ui.button("No, continuar", on_click=dialog.close)
                ui.button(
                    "Sí, cancelar",
                    on_click=lambda: (
                        dialog.close(),
                        _confirmar_cancelacion(wizard, refresh),
                    ),
                    color="red",
                )
        dialog.open()
        return
    await _confirmar_cancelacion(wizard, refresh)


async def _confirmar_cancelacion(wizard: WizardKiosko, refresh) -> None:
    if wizard.ultimo_id_transaccion is not None:
        await transacciones.eliminar_si_activa(wizard.ultimo_id_transaccion)
    refresh(wizard.reset())


def _metodo_por_codigo(codigo: MetodoPago):
    for m in METODOS_PAGO_DISPONIBLES:
        if m.codigo is codigo:
            return m
    return None
