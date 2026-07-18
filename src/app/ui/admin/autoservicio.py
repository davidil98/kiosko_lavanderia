"""Panel autoservicio (`@ui.page("/admin/autoservicio")`).

El operador ve las órdenes `Pendiente` y `En proceso` del modo autoservicio.
- Pendiente: asignar máquina y disparar el pulso de inicio.
- En proceso: marcar como completado.
"""

import asyncio
from datetime import datetime

from nicegui import ui

from app.adaptadores.hardware import maquinas_pin
from app.core.estados import EstadoOrden
from app.core.maquinas import EQUIPOS
from app.eventos.bus import bus
from app.eventos.tipos import (
    EventoDominio,
    TIPO_CICLO_INICIADO,
    TIPO_MAQUINA_ASIGNADA,
    TIPO_ORDEN_FINALIZADA,
)
from app.repo import maquinas as repo_maquinas
from app.repo import transacciones
from app.ui.admin._componentes import (
    AccionTarjeta,
    boton_cerrar_sesion,
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
            tarjeta_orden(
                o,
                [
                    AccionTarjeta(
                        label="✓ Marcar completado",
                        color="positive",
                        handler=_completar,
                    ),
                ],
            )

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

    # NO usamos ui.timer() con .refresh() porque regresa el scroll al
    # inicio y cierra dialogs abiertos. Refrescamos solo cuando hay
    # eventos del bus (peso aprobado, pago confirmado, etc.).
    from app.eventos.bus import bus
    from app.eventos.tipos import (
        TIPO_ORDEN_CREADA,
        TIPO_ORDEN_CANCELADA,
        TIPO_PAGO_CONFIRMADO,
        TIPO_PESO_APROBADO,
        TIPO_PESO_RECHAZADO,
        TIPO_MAQUINA_ASIGNADA,
        TIPO_ORDEN_FINALIZADA,
    )

    colas = [
        bus.subscribe(t)
        for t in (
            TIPO_ORDEN_CREADA,
            TIPO_ORDEN_CANCELADA,
            TIPO_PAGO_CONFIRMADO,
            TIPO_PESO_APROBADO,
            TIPO_PESO_RECHAZADO,
            TIPO_MAQUINA_ASIGNADA,
            TIPO_ORDEN_FINALIZADA,
        )
    ]

    async def _consumir():
        import asyncio

        while True:
            for cola in colas:
                try:
                    cola.get_nowait()
                    contenido.refresh()
                except Exception:
                    pass
            await asyncio.sleep(0.5)

    asyncio.create_task(_consumir())
    boton_cerrar_sesion()


# ── Acciones ────────────────────────────────────────────────────────────────


def _abrir_asignar(o: dict) -> None:
    oid = o["id_transaccion"]
    seleccion_ref: dict = {"select": None}
    lista_maquinas = repo_maquinas._listar(solo_activas=True)

    async def confirmar() -> None:
        sel = seleccion_ref["select"].value if seleccion_ref["select"] else None
        if not sel:
            ui.notify("Selecciona una máquina", type="warning")
            return
        eq = next((m for m in lista_maquinas if m.codigo == sel), None)
        if eq is None:
            ui.notify("Máquina inválida", type="negative")
            return
        eq_nombre = eq.nombre
        eq_modo = eq.modo
        duracion = eq.duracion_max_min

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
        opciones = [f"{m.nombre} ({m.tipo} · {m.modo})" for m in lista_maquinas]
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
        # Apagar la máquina
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
