"""Panel personalizado (`@ui.page("/admin/personalizado")`).

Kanban de 3 columnas (Recibido / Alistando / Listo para Entrega) para
las órdenes con modalidad `personalizado`.

En la etapa `ALISTANDO` (o `LISTO_ENTREGA`) el admin puede asignar
una máquina del catálogo de autoservicio como recurso compartido,
con duración flexible (solo para modo `sostenido`).
"""

import asyncio
from datetime import datetime

from nicegui import ui

from app.adaptadores.hardware import maquinas_pin
from app.core.estados import EtapaKanban
from app.core.estado_maquinas import (
    asignar as em_asignar,
    obtener as em_obtener,
    registrar_maquina as em_registrar_maquina,
)
from app.eventos.bus import bus
from app.eventos.tipos import (
    EventoDominio,
    TIPO_ETAPA_KANBAN_CAMBIADA,
    TIPO_ORDEN_CANCELADA,
    etapa_kanban_cambiada,
)
from app.repo import maquinas as repo_maquinas
from app.repo import transacciones
from app.ui.admin._componentes import (
    AccionTarjeta,
    boton_cerrar_sesion,
    boton_volver_dashboard,
    render_header,
    render_seccion,
    tarjeta_orden,
)
from app.ui.compartido.auth import redirigir_si_no_autenticado, usuario_actual

ETAPAS = [
    (EtapaKanban.RECIBIDO, "inbox", "Recibido"),
    (EtapaKanban.ALISTANDO, "gear", "Alistando"),
    (EtapaKanban.LISTO_ENTREGA, "check", "Listo para Entrega"),
]

SENTINEL_NINGUNA = "__NINGUNA__"


@ui.page("/admin/personalizado")
async def admin_personalizado():
    if redirigir_si_no_autenticado():
        return
    usuario = usuario_actual()
    render_header(usuario)

    @ui.refreshable
    async def contenido() -> None:
        ordenes = await transacciones.listar_personalizadas()
        ordenes = [o for o in ordenes if o.get("etapa_kanban") != "Entregado"]
        por_etapa: dict[EtapaKanban, list] = {e: [] for e, _, _ in ETAPAS}
        for o in ordenes:
            try:
                etapa = (
                    EtapaKanban(o.get("etapa_kanban"))
                    if o.get("etapa_kanban")
                    else EtapaKanban.RECIBIDO
                )
            except ValueError:
                etapa = EtapaKanban.RECIBIDO
            por_etapa.setdefault(etapa, []).append(o)

        with ui.element("div").style(
            "display:grid;grid-template-columns:repeat(3, 1fr);gap:18px;"
        ):
            for etapa, icono, titulo in ETAPAS:
                with ui.element("div").classes("kanban-col"):
                    ui.html(
                        f'<div class="kanban-col-header">'
                        f'<img src="/media/icons/{icono}.svg" '
                        f'style="width:20px;height:20px;vertical-align:middle;margin-right:6px;">'
                        f"{titulo}"
                        f'<span class="badge" style="margin-left:auto;">{len(por_etapa[etapa])}</span>'
                        f"</div>"
                    )
                    for o in por_etapa[etapa]:
                        _render_kanban_card(o)

    with ui.element("div").props("id=admin-content"):
        ui.html(
            '<h2 style="font-size:1.5rem;font-weight:800;color:#1e293b;'
            'margin-bottom:6px;display:flex;align-items:center;gap:10px;">'
            '<img src="/media/icons/shirt.svg" style="width:32px;height:32px;">'
            "Servicio Personalizado</h2>"
        )
        ui.html(
            f'<p style="color:#64748b;margin-bottom:24px;">'
            f"Mueve las órdenes por las 3 etapas. Operador: <strong>{usuario}</strong>.</p>"
        )
        with ui.element("div").props("id=personalizado-contenido"):
            await contenido()

    from app.eventos.bus import bus
    from app.eventos.tipos import (
        TIPO_ORDEN_CREADA,
        TIPO_ORDEN_CANCELADA,
        TIPO_ORDEN_FINALIZADA,
        TIPO_PAGO_CONFIRMADO,
        TIPO_MAQUINA_LIBERADA,
        TIPO_MAQUINA_PAUSADA,
        TIPO_MAQUINA_REANUDADA,
        TIPO_ETAPA_KANBAN_CAMBIADA,
    )

    colas = [
        bus.subscribe(t)
        for t in (
            TIPO_ORDEN_CREADA,
            TIPO_ORDEN_CANCELADA,
            TIPO_ORDEN_FINALIZADA,
            TIPO_PAGO_CONFIRMADO,
            TIPO_MAQUINA_LIBERADA,
            TIPO_MAQUINA_PAUSADA,
            TIPO_MAQUINA_REANUDADA,
            TIPO_ETAPA_KANBAN_CAMBIADA,
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

    ui.timer(0.3, _consumir)
    boton_volver_dashboard()
    boton_cerrar_sesion()


def _render_kanban_card(o: dict) -> None:
    """Una tarjeta del kanban con sus acciones contextuales."""
    etapa_actual = o.get("etapa_kanban")
    try:
        etapa = EtapaKanban(etapa_actual) if etapa_actual else EtapaKanban.RECIBIDO
    except ValueError:
        etapa = EtapaKanban.RECIBIDO

    idx = next((i for i, (e, _, _) in enumerate(ETAPAS) if e is etapa), 0)
    acciones: list[AccionTarjeta] = []

    if idx < len(ETAPAS) - 1:
        siguiente = ETAPAS[idx + 1][0]
        acciones.append(
            AccionTarjeta(
                label=f"→ {ETAPAS[idx + 1][2]}",
                color="primary",
                handler=_hacer_avanzar_etapa(siguiente),
            )
        )
    else:
        acciones.append(
            AccionTarjeta(
                label="✓ Entregar",
                color="positive",
                handler=_hacer_cancelar(),
            )
        )

    if idx >= 1 and o.get("id_equipo", "") in ("", "N/A"):
        acciones.append(
            AccionTarjeta(
                label="⚙ Usar máquina disponible",
                color="primary",
                handler=_abrir_asignar_pers,
            )
        )

    tarjeta_orden(o, acciones)


def _hacer_avanzar_etapa(siguiente: EtapaKanban):
    """Crea un handler async que avanza la orden a la etapa siguiente.

    Si la orden tiene una máquina asignada y aún está en uso, muestra
    un diálogo de advertencia y no avanza.
    """

    async def handler(o: dict) -> None:
        oid = o["id_transaccion"]
        eq_actual = o.get("id_equipo", "")
        if eq_actual not in ("", "N/A"):
            eq = next(
                (
                    m
                    for m in repo_maquinas._listar(solo_activas=True)
                    if m.nombre == eq_actual
                ),
                None,
            )
            if eq is not None:
                em = em_obtener(eq.codigo)
                if em is None or em.ocupada:
                    with ui.dialog() as dialogo, ui.card().style("min-width:380px;"):
                        ui.label("Advertencia: maquina en uso").classes(
                            "text-lg font-bold text-amber-600 mb-2"
                        )
                        ui.html(
                            f'<p style="font-size:0.9rem;color:#475569;margin-bottom:8px;">'
                            f"La orden tiene asignada la maquina "
                            f"<strong>{eq.nombre}</strong>, que aun esta en uso."
                            f"</p>"
                            f'<p style="font-size:0.85rem;color:#64748b;margin-bottom:12px;">'
                            f"Antes de avanzar a <strong>{siguiente.value}</strong>, "
                            f"asegurate de que la maquina haya parado:"
                            f"</p>"
                            f'<ul style="font-size:0.85rem;color:#64748b;'
                            f'margin-bottom:12px;padding-left:20px;">'
                            f"<li>Espera a que termine el tiempo asignado "
                            f"(en el panel de maquinas)</li>"
                            f"<li>O parala manualmente desde el panel de maquinas</li>"
                            f"</ul>"
                        )
                        with ui.row().classes("w-full justify-end"):
                            ui.button(
                                "Ir al panel de maquinas",
                                on_click=lambda: (
                                    dialogo.close(),
                                    ui.navigate.to("/admin/maquinas"),
                                ),
                            ).props("flat color=warning")
                            ui.button("Cerrar", on_click=dialogo.close).props(
                                "flat color=warning"
                            )
                    dialogo.open()
                    return
        await transacciones.actualizar_etapa_kanban(oid, siguiente.value)
        bus.publish(etapa_kanban_cambiada(oid, siguiente.value))
        try:
            ui.notify(f"Etapa actualizada a {siguiente.value}", type="positive")
        except Exception:
            pass

    return handler


def _hacer_cancelar():
    async def handler(o: dict) -> None:
        oid = o["id_transaccion"]
        eq_nombre = await transacciones.obtener_maquina_nombre_de_orden(oid)
        if eq_nombre:
            eq = next(
                (
                    m
                    for m in repo_maquinas._listar(solo_activas=True)
                    if m.nombre == eq_nombre
                ),
                None,
            )
            if eq is not None:
                await maquinas_pin.apagar(eq.codigo)
        await _finalizar_entrega(oid)

    return handler


async def _finalizar_entrega(oid: int) -> None:
    """Marca la orden como entregada y publica el evento correspondiente."""
    await transacciones.actualizar_etapa_kanban(oid, "Entregado")
    bus.publish(
        EventoDominio(
            tipo=TIPO_ORDEN_CANCELADA,
            orden_id=oid,
            extra={"motivo": "entregado"},
            cuando=datetime.now(),
        )
    )
    ui.notify(f"Orden #{oid} entregada", type="positive")


# ── Asignación de máquina (etapa ALISTANDO o LISTO_ENTREGA) ─────────────────


async def _abrir_asignar_pers(o: dict) -> None:
    oid = o["id_transaccion"]
    seleccion_ref: dict = {"select": None, "duracion": None}
    todas = repo_maquinas._listar(solo_activas=True)
    for m in todas:
        em_registrar_maquina(m.codigo, m.nombre, m.tipo, m.modo)
    lista_maquinas = [
        m
        for m in todas
        if em_obtener(m.codigo) is None or not em_obtener(m.codigo).ocupada
    ]

    opciones: dict[str, str] = {SENTINEL_NINGUNA: "(Sin máquina)"}
    for m in lista_maquinas:
        opciones[m.codigo] = f"{m.nombre} ({m.tipo} · {m.modo})" + (
            " · OCUPADA"
            if (em_obtener(m.codigo) and em_obtener(m.codigo).ocupada)
            else ""
        )

    sostenidas = [m for m in lista_maquinas if m.modo == "sostenido"]

    async def confirmar() -> None:
        sel = seleccion_ref["select"].value if seleccion_ref["select"] else None
        if not sel:
            ui.notify("Selecciona una opción", type="warning")
            return

        if sel == SENTINEL_NINGUNA:
            await transacciones.asignar_maquina_personalizado(oid, "", 0)
            bus.publish(
                etapa_kanban_cambiada(oid, o.get("etapa_kanban") or "Alistando")
            )
            dialogo.close()
            ui.notify(
                "Orden marcada como 'sin máquina' (usa equipo externo)",
                type="info",
            )
            return

        eq = next((m for m in lista_maquinas if m.codigo == sel), None)
        if eq is None:
            ui.notify("Máquina inválida", type="negative")
            return
        em = em_obtener(sel)
        if em and em.ocupada:
            ui.notify("Esa máquina ya está ocupada", type="warning")
            return

        duracion = 0
        if eq.modo == "sostenido":
            val = seleccion_ref["duracion"].value if seleccion_ref["duracion"] else None
            try:
                duracion = int(val) if val else 0
            except (TypeError, ValueError):
                duracion = 0
            if duracion <= 0:
                ui.notify(
                    "Para máquinas en modo sostenido, indica la duración (>0)",
                    type="warning",
                )
                return

        try:
            em_asignar(
                codigo=sel,
                orden_id=oid,
                nombre_cliente=o.get("nombre_cliente", ""),
                servicio=o.get("tipo_servicio", ""),
                duracion_min=duracion if duracion > 0 else eq.duracion_max_min,
            )
        except RuntimeError as exc:
            ui.notify(str(exc), type="negative")
            return

        await transacciones.asignar_maquina_personalizado(
            oid, eq.nombre, duracion if duracion > 0 else eq.duracion_max_min
        )
        bus.publish(etapa_kanban_cambiada(oid, o.get("etapa_kanban") or "Alistando"))
        if eq.modo == "pulso":
            await maquinas_pin.activar(sel)
        else:
            await maquinas_pin.activar_con_duracion(
                sel, duracion if duracion > 0 else eq.duracion_max_min
            )
        dialogo.close()
        ui.notify(
            f"{eq.nombre} asignada a Orden #{oid}"
            + (f" por {duracion} min" if duracion > 0 else ""),
            type="positive",
        )

    with ui.dialog() as dialogo, ui.card().style("min-width:360px;"):
        ui.label(f"Asignar máquina a Orden #{oid}").classes(
            "text-lg font-bold text-slate-800 mb-2"
        )
        ui.html(
            '<p style="font-size:0.78rem;color:#64748b;margin-bottom:8px;">'
            "Si el servicio usa equipo externo, elige "
            "<strong>(Sin máquina)</strong>."
            "</p>"
        )
        seleccion_ref["select"] = ui.select(opciones, label="Máquina").classes(
            "w-full mb-2"
        )
        if sostenidas:
            ui.html(
                '<p style="font-size:0.78rem;color:#64748b;margin:8px 0 0;">'
                "Duración del ciclo (min) — solo para máquinas en modo "
                "<strong>sostenido</strong>:"
                "</p>"
            )
            seleccion_ref["duracion"] = ui.number(
                label="Minutos", value=25, min=1, max=180
            ).classes("w-full mb-4")
        with ui.row().classes("w-full justify-end"):
            ui.button("Cancelar", on_click=dialogo.close).props("flat")
            ui.button("Asignar", on_click=confirmar).props("color=positive")
    dialogo.open()
