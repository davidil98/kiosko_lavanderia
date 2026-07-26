"""Panel autoservicio (`@ui.page("/admin/autoservicio")`).

El operador ve las órdenes `Pendiente` y `En proceso` del modo autoservicio.
- Pendiente: asignar máquina y disparar el ciclo.
- En proceso: marcar como completado (verde), pausar/reanudar (amarillo,
  solo modo sostenido) o detener y cancelar (rojo).

Toda validación de "máquina ocupada" se hace contra `core.estado_maquinas`.
"""

import asyncio
from datetime import datetime

from nicegui import ui

from app.adaptadores.hardware import maquinas_pin
from app.core.estados import EstadoOrden
from app.core.estado_maquinas import (
    ESTADO,
    asignar as em_asignar,
    obtener as em_obtener,
    registrar_maquina as em_registrar_maquina,
)
from app.core.maquinas import EQUIPOS
from app.eventos.bus import bus
from app.eventos.tipos import (
    EventoDominio,
    TIPO_CICLO_INICIADO,
    TIPO_MAQUINA_ASIGNADA,
    TIPO_MAQUINA_LIBERADA,
    TIPO_MAQUINA_PAUSADA,
    TIPO_MAQUINA_REANUDADA,
    TIPO_ORDEN_CANCELADA,
    TIPO_ORDEN_FINALIZADA,
    TIPO_PAGO_CONFIRMADO,
    TIPO_PESO_APROBADO,
    TIPO_PESO_RECHAZADO,
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


@ui.page("/admin/autoservicio")
async def admin_autoservicio():
    if redirigir_si_no_autenticado():
        return
    usuario = usuario_actual()
    render_header(usuario)

    @ui.refreshable
    async def contenido() -> None:
        pendientes = await transacciones.listar_para_asignar_autoservicio()
        por_asignar = [
            o for o in pendientes if o["estado"] == EstadoOrden.PENDIENTE.value
        ]
        en_proceso = [o for o in pendientes if o["estado"] == "En proceso"]

        def _render_pendiente(o: dict) -> None:
            tarjeta_orden(
                o,
                [
                    AccionTarjeta(
                        label="⚙ Asignar máquina",
                        color="primary",
                        handler=_abrir_asignar,
                    ),
                ],
            )

        def _render_proceso(o: dict) -> None:
            acciones = _construir_acciones_en_proceso(o)
            eq_nombre = o.get("id_equipo", "")
            eq = None
            if eq_nombre:
                eq = next(
                    (
                        m
                        for m in repo_maquinas._listar(solo_activas=True)
                        if m.nombre == eq_nombre
                    ),
                    None,
                )
            o_render: dict = dict(o)
            if eq is not None:
                em = em_obtener(eq.codigo)
                if em is not None and em.ocupada:
                    encendida = em.tiempo_encendida_min
                    if eq.modo == "sostenido":
                        restante = int(em.tiempo_restante_min)
                        o_render["nota_maquina"] = (
                            f"<span class='orden-meta'>"
                            f"Encendida: <strong>{encendida} min</strong> · "
                            f"Restante: <strong>{restante} min</strong>"
                            f"</span>"
                        )
                    else:
                        o_render["nota_maquina"] = (
                            f"<span class='orden-meta'>"
                            f"Encendida: <strong>{encendida} min</strong> "
                            f"(modo pulso, no tiene auto-apagado)"
                            f"</span>"
                        )
            tarjeta_orden(o_render, acciones)

        render_seccion("leaf", "Por asignar", por_asignar, _render_pendiente)
        render_seccion("gear", "En proceso", en_proceso, _render_proceso)

    # Header estático fuera del refreshable: no se re-renderiza con el
    # timer, así no se regresa el scroll al inicio.
    with ui.element("div").props("id=admin-content"):
        ui.html(
            '<h2 style="font-size:1.5rem;font-weight:800;color:#1e293b;'
            'margin-bottom:6px;display:flex;align-items:center;gap:10px;">'
            '<img src="/media/icons/leaf.svg" style="width:32px;height:32px;">'
            "Autoservicio</h2>"
        )
        ui.html(
            f'<p style="color:#64748b;margin-bottom:24px;">'
            f"Asigna máquina y dispara el ciclo. Operador: <strong>{usuario}</strong>.</p>"
        )
        with ui.element("div").props("id=autoservicio-contenido"):
            await contenido()

    colas = [
        bus.subscribe(t)
        for t in (
            TIPO_ORDEN_CANCELADA,
            TIPO_PAGO_CONFIRMADO,
            TIPO_PESO_APROBADO,
            TIPO_PESO_RECHAZADO,
            TIPO_MAQUINA_ASIGNADA,
            TIPO_MAQUINA_LIBERADA,
            TIPO_MAQUINA_PAUSADA,
            TIPO_MAQUINA_REANUDADA,
            TIPO_ORDEN_FINALIZADA,
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


# ── Construcción de acciones para órdenes "En proceso" ─────────────────────


def _construir_acciones_en_proceso(o: dict) -> list:
    """Devuelve 2 o 3 AccionTarjeta según el modo de la máquina.

    - Verde: Marcar completado
    - Amarillo: Pausar / Reanudar (solo si modo == sostenido)
    - Rojo: Detener y cancelar
    """
    acciones: list[AccionTarjeta] = []
    eq_nombre = o.get("id_equipo", "")
    eq = None
    if eq_nombre:
        eq = next(
            (
                m
                for m in repo_maquinas._listar(solo_activas=True)
                if m.nombre == eq_nombre
            ),
            None,
        )

    acciones.append(
        AccionTarjeta(
            label="✓ Marcar completado",
            color="positive",
            handler=_completar,
        )
    )

    if eq and eq.modo == "sostenido":
        em = em_obtener(eq.codigo)
        pausada = em.pausada if em else False
        if pausada:
            acciones.append(
                AccionTarjeta(
                    label="▶ Reanudar",
                    color="warning",
                    handler=_hacer_reanudar(eq.codigo),
                )
            )
        else:
            acciones.append(
                AccionTarjeta(
                    label="⏸ Pausar",
                    color="warning",
                    handler=_hacer_pausar(eq.codigo),
                )
            )

    acciones.append(
        AccionTarjeta(
            label="⏹ Detener y terminar",
            color="negative",
            handler=_hacer_detener_y_cancelar(o["id_transaccion"]),
        )
    )

    return acciones


def _hacer_pausar(codigo: str):
    async def handler(_o: dict) -> None:
        await maquinas_pin.pausar(codigo)
        ui.notify(f"Máquina pausada", type="warning")

    return handler


def _hacer_reanudar(codigo: str):
    async def handler(_o: dict) -> None:
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
            ref["min"] = ui.number(
                label="Minutos extra", value=10, min=1, max=120
            ).classes("w-full mb-4")
            with ui.row().classes("w-full justify-end"):
                ui.button("Cancelar", on_click=dialogo.close).props("flat")
                ui.button("Reanudar", on_click=confirmar).props("color=warning")
        dialogo.open()

    return handler


def _hacer_detener_y_cancelar(orden_id: int):
    async def handler(_o: dict) -> None:
        from app.ui.compartido.auth import usuario_actual as _ua

        eq_nombre = await transacciones.obtener_maquina_nombre_de_orden(orden_id)
        if eq_nombre:
            eq = next(
                (
                    m
                    for m in repo_maquinas._listar(solo_activas=True)
                    if m.nombre == eq_nombre
                ),
                None,
            )
            if eq:
                await maquinas_pin.apagar(eq.codigo)
        await transacciones.cancelar_orden(orden_id, f"Detenido por {_ua()}")
        bus.publish(
            EventoDominio(
                tipo=TIPO_ORDEN_CANCELADA,
                orden_id=orden_id,
                extra={"motivo": "detenida_manual", "maquina": eq_nombre or ""},
                cuando=datetime.now(),
            )
        )
        ui.notify(f"Orden #{orden_id} detenida y cancelada", type="warning")

    return handler


# ── Asignación de máquina (orden pendiente) ─────────────────────────────────


async def _abrir_asignar(o: dict) -> None:
    oid = o["id_transaccion"]
    seleccion_ref: dict = {"select": None}
    todas = repo_maquinas._listar(solo_activas=True)
    for m in todas:
        em_registrar_maquina(m.codigo, m.nombre, m.tipo, m.modo)
    lista_maquinas = [
        m
        for m in todas
        if em_obtener(m.codigo) is None or not em_obtener(m.codigo).ocupada
    ]

    if not lista_maquinas:
        ui.notify(
            "No hay máquinas disponibles. Libera una antes de asignar.",
            type="warning",
        )
        return

    async def confirmar() -> None:
        sel = seleccion_ref["select"].value if seleccion_ref["select"] else None
        if not sel:
            ui.notify("Selecciona una máquina", type="warning")
            return
        eq = next((m for m in lista_maquinas if m.codigo == sel), None)
        if eq is None:
            ui.notify("Máquina inválida", type="negative")
            return
        em = em_obtener(sel)
        if em and em.ocupada:
            ui.notify("Esa máquina ya está ocupada", type="warning")
            return
        eq_nombre = eq.nombre
        eq_modo = eq.modo
        duracion = eq.duracion_max_min

        try:
            em_asignar(
                codigo=sel,
                orden_id=oid,
                nombre_cliente=o.get("nombre_cliente", ""),
                servicio=o.get("tipo_servicio", ""),
                duracion_min=duracion,
            )
        except RuntimeError as exc:
            ui.notify(str(exc), type="negative")
            return

        await transacciones.marcar_en_proceso(oid, eq_nombre)
        if eq_modo == "pulso":
            await maquinas_pin.activar(sel)
        else:
            await maquinas_pin.activar_con_duracion(sel, duracion)
        bus.publish(
            EventoDominio(
                tipo=TIPO_MAQUINA_ASIGNADA,
                orden_id=oid,
                extra={"maquina": eq_nombre, "modo": eq_modo},
                cuando=datetime.now(),
            )
        )
        bus.publish(
            EventoDominio(
                tipo=TIPO_CICLO_INICIADO,
                orden_id=oid,
                extra={"maquina": eq_nombre},
                cuando=datetime.now(),
            )
        )
        dialogo.close()
        ui.notify(f"Ciclo iniciado en {eq_nombre}", type="positive")

    with ui.dialog() as dialogo, ui.card().style("min-width:340px;"):
        ui.label(f"Asignar máquina a Orden #{oid}").classes(
            "text-lg font-bold text-slate-800 mb-2"
        )
        opciones = {
            m.codigo: f"{m.nombre} ({m.tipo} · {m.modo})"
            + (
                " · OCUPADA"
                if (em_obtener(m.codigo) and em_obtener(m.codigo).ocupada)
                else ""
            )
            for m in lista_maquinas
        }
        seleccion_ref["select"] = ui.select(opciones, label="Máquina").classes(
            "w-full mb-4"
        )
        with ui.row().classes("w-full justify-end"):
            ui.button("Cancelar", on_click=dialogo.close).props("flat")
            ui.button("Asignar e iniciar", on_click=confirmar).props("color=positive")
    dialogo.open()


async def _completar(o: dict) -> None:
    oid = o["id_transaccion"]
    eq_nombre = o.get("id_equipo", "")
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
    await transacciones.marcar_completado(oid, eq_nombre)
    bus.publish(
        EventoDominio(
            tipo=TIPO_ORDEN_FINALIZADA,
            orden_id=oid,
            extra={"maquina": eq_nombre},
            cuando=datetime.now(),
        )
    )
    ui.notify(f"Orden #{oid} completada", type="positive")
