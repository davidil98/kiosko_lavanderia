"""Panel de control de máquinas (`@ui.page("/admin/maquinas")`).

Muestra el estado en tiempo real de cada máquina del catálogo:
- Libre (verde)
- En uso (rojo) con orden asignada, cliente, tiempo restante
- Pausada (amarillo) con tiempo restante congelado

Acciones disponibles según estado:
- Pausar / Reanudar (sostenido)
- Liberar manualmente (apaga GPIO y libera la máquina)

Se suscribe a TIPO_MAQUINA_LIBERADA, TIPO_MAQUINA_PAUSADA, TIPO_MAQUINA_REANUDADA
para sincronización en tiempo real con múltiples pestañas.
"""

import asyncio

from nicegui import ui

from app.adaptadores.hardware import maquinas_pin
from app.core.estado_maquinas import ESTADO, listar_todas
from app.eventos.bus import bus
from app.eventos.tipos import (
    TIPO_MAQUINA_ASIGNADA,
    TIPO_MAQUINA_LIBERADA,
    TIPO_MAQUINA_PAUSADA,
    TIPO_MAQUINA_REANUDADA,
    TIPO_ORDEN_CANCELADA,
    TIPO_ORDEN_FINALIZADA,
    TIPO_PAGO_CONFIRMADO,
    TIPO_PESO_APROBADO,
)
from app.repo import maquinas as repo_maquinas
from app.repo import transacciones
from app.ui.admin._componentes import (
    boton_cerrar_sesion,
    boton_volver_dashboard,
    render_header,
    tarjeta_maquina,
)
from app.ui.compartido.auth import redirigir_si_no_autenticado, usuario_actual


@ui.page("/admin/maquinas")
async def admin_maquinas():
    if redirigir_si_no_autenticado():
        return
    usuario = usuario_actual()
    render_header(usuario)

    @ui.refreshable
    async def contenido() -> None:
        maquinas = repo_maquinas._listar(solo_activas=False)
        estados = {e.codigo: e for e in listar_todas()}

        with ui.element("div").style(
            "display:grid;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));gap:14px;"
        ):
            for m in maquinas:
                em = estados.get(m.codigo)
                tarjeta_maquina(m, em, _on_pausar, _on_reanudar, _on_liberar)

    with ui.element("div").props("id=admin-content"):
        ui.html(
            '<h2 style="font-size:1.5rem;font-weight:800;color:#1e293b;'
            'margin-bottom:6px;display:flex;align-items:center;gap:10px;">'
            '<img src="/media/icons/gear.svg" style="width:32px;height:32px;">'
            "Estado de Máquinas</h2>"
        )
        ui.html(
            f'<p style="color:#64748b;margin-bottom:24px;">'
            f"Visualización en tiempo real. Operador: <strong>{usuario}</strong>.</p>"
        )
        with ui.element("div").props("id=maquinas-contenido"):
            await contenido()

    colas = [
        bus.subscribe(t)
        for t in (
            TIPO_MAQUINA_LIBERADA,
            TIPO_MAQUINA_PAUSADA,
            TIPO_MAQUINA_REANUDADA,
            TIPO_MAQUINA_ASIGNADA,
            TIPO_ORDEN_FINALIZADA,
            TIPO_ORDEN_CANCELADA,
            TIPO_PAGO_CONFIRMADO,
            TIPO_PESO_APROBADO,
        )
    ]

    async def _consumir():
        while True:
            for cola in colas:
                try:
                    cola.get_nowait()
                    contenido.refresh()
                except Exception:
                    pass
            await asyncio.sleep(0.5)

    asyncio.create_task(_consumir())
    boton_volver_dashboard()
    boton_cerrar_sesion()


# ── Acciones del panel máquinas ────────────────────────────────────────────


async def _on_pausar(codigo: str) -> None:
    ok = await maquinas_pin.pausar(codigo)
    if ok:
        ui.notify("Máquina pausada", type="warning")
    else:
        ui.notify("No se pudo pausar", type="negative")


async def _on_reanudar(codigo: str) -> None:
    ref: dict = {"min": None}

    async def confirmar() -> None:
        val = ref["min"].value if ref["min"] else None
        try:
            extra = int(val) if val else 0
        except (TypeError, ValueError):
            extra = 0
        if extra <= 0:
            ui.notify("Duración debe ser > 0", type="warning")
            return
        ok = await maquinas_pin.reanudar(codigo, extra)
        if ok:
            dialogo.close()
            ui.notify(f"Reanudada con +{extra} min", type="positive")
        else:
            ui.notify("No se pudo reanudar", type="negative")

    with ui.dialog() as dialogo, ui.card().style("min-width:300px;"):
        ui.label("Reanudar con cuántos minutos adicionales?").classes(
            "text-base font-bold text-slate-800 mb-2"
        )
        ref["min"] = ui.number(label="Minutos extra", value=10, min=1, max=120).classes(
            "w-full mb-4"
        )
        with ui.row().classes("w-full justify-end"):
            ui.button("Cancelar", on_click=dialogo.close).props("flat")
            ui.button("Reanudar", on_click=confirmar).props("color=warning")
    dialogo.open()


async def _on_liberar(codigo: str) -> None:
    async def confirmar() -> None:
        from app.core.estado_maquinas import obtener as _em_obtener

        em = _em_obtener(codigo)
        orden_id = em.orden_id if em else None
        await maquinas_pin.apagar(codigo)
        if orden_id:
            from datetime import datetime
            from app.eventos.tipos import EventoDominio, TIPO_ORDEN_CANCELADA

            bus.publish(
                EventoDominio(
                    tipo=TIPO_ORDEN_CANCELADA,
                    orden_id=orden_id,
                    extra={"motivo": "liberada_manual_panel"},
                    cuando=datetime.now(),
                )
            )
            await transacciones.cancelar_orden(orden_id, "Liberada manualmente")
        dialogo.close()
        ui.notify("Máquina liberada", type="warning")

    with ui.dialog() as dialogo, ui.card().style("min-width:300px;"):
        ui.label("¿Liberar esta máquina?").classes(
            "text-lg font-bold text-slate-800 mb-2"
        )
        ui.html(
            '<p style="font-size:0.85rem;color:#475569;margin-bottom:8px;">'
            "Si hay una orden asignada, será marcada como CANCELADO."
            "</p>"
        )
        with ui.row().classes("w-full justify-end"):
            ui.button("No", on_click=dialogo.close).props("flat")
            ui.button("Sí, liberar", on_click=confirmar).props("color=negative")
    dialogo.open()
