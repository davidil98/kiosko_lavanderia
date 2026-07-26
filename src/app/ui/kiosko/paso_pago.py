"""Paso 4: Pagar.

Muestra las tarjetas de los métodos de pago disponibles. Al elegir uno,
delega al `MetodoPago` correspondiente (Strategy pattern). El método renderiza
su panel y, cuando el cliente confirma, llama al `iniciar` que persiste la
orden y (si aplica) publica `pago.confirmado` en el bus.

Los botones "← Volver" dentro de cada panel de método delegan a `on_volver`
del `ContextoPago`, que ejecuta la lógica específica según el método:
- Monedas: diálogo de advertencia si hay dinero, luego limpia y notifica.
- Point: cancela en MP y notifica.
- Mostrador: limpia y notifica sin advertencia.
"""

import asyncio
from dataclasses import replace
from datetime import datetime

from nicegui import ui

from app.core.pagos import METODOS_PAGO_DISPONIBLES
from app.core.pagos.estrategia import ContextoPago
from app.core.estados import MetodoPago
from app.eventos.bus import bus
from app.eventos.tipos import EventoDominio, TIPO_PAGO_CANCELADO
from app.repo import transacciones
from app.ui.kiosko.wizard import Sub, WizardKiosko


def render_paso_pago(wizard: WizardKiosko, refresh) -> None:
    if wizard.sub == Sub.METODOS_PAGO:
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
            if es_personalizado and metodo.codigo == MetodoPago.MONEDAS:
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

    ui.button(
        "← Volver",
        on_click=lambda: refresh(wizard.volver_a_pesar()),
    ).classes("btn-confirmar-nombre max-w-xs mx-auto mt-6").style("background:#334155;")

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
        on_volver=lambda: asyncio.create_task(_volver_desde_pago(wizard, refresh)),
        refresh=refresh,
    )
    metodo.render_panel(ctx)


async def _cancelar_pago(wizard: WizardKiosko, refresh) -> None:
    if wizard.dinero > 0 and wizard.metodo == MetodoPago.MONEDAS:
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


async def _volver_desde_pago(wizard: WizardKiosko, refresh) -> None:
    """Callback on_volver: comportamiento según método de pago."""
    if wizard.metodo == MetodoPago.MONEDAS and wizard.dinero > 0:
        await _confirmar_regreso_con_dinero(wizard, refresh)
        return
    await _regresar_a_pesar(wizard, refresh)


async def _confirmar_regreso_con_dinero(wizard: WizardKiosko, refresh) -> None:
    """Diálogo de advertencia cuando hay dinero en monedas y se presiona ← Volver."""
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
                    _regresar_a_pesar(wizard, refresh),
                ),
                color="red",
            )
    dialog.open()


async def _regresar_a_pesar(wizard: WizardKiosko, refresh) -> None:
    """Cancela la orden activa, notifica al admin y regresa al paso PESO."""
    oid = wizard.ultimo_id_transaccion
    if oid is not None:
        if wizard.metodo == MetodoPago.POINT:
            from app.adaptadores.mercado_pago import point as mp_point

            mp_id = await transacciones.obtener_mp_order_id(oid)
            if mp_id:
                try:
                    await asyncio.to_thread(mp_point.cancelar_orden, mp_id)
                except Exception:
                    pass
        await transacciones.eliminar_si_activa(oid)
        bus.publish(
            EventoDominio(
                tipo=TIPO_PAGO_CANCELADO,
                orden_id=oid,
                extra={},
                cuando=datetime.now(),
            )
        )
    nuevo = replace(
        wizard, metodo=None, sub=Sub.NINGUNO, dinero=0, ultimo_id_transaccion=None
    )
    refresh(nuevo.volver_a_pesar())


async def _confirmar_cancelacion(wizard: WizardKiosko, refresh) -> None:
    if wizard.ultimo_id_transaccion is not None:
        await transacciones.eliminar_si_activa(wizard.ultimo_id_transaccion)
    refresh(wizard.reset())


def _metodo_por_codigo(codigo: MetodoPago):
    for m in METODOS_PAGO_DISPONIBLES:
        if m.codigo == codigo:
            return m
    return None
