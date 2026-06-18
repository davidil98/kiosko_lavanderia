import asyncio
from nicegui import ui
import nicegui as _ng

import hardware
import database_web
from services.auth import redirigir_si_no_autenticado
from services.notifications import (
    state,
    registrar_callback_autoservicio,
    remover_callback_autoservicio,
    registrar_admin_client,
    remover_admin_client,
    get_admin_client,
)
from components.admin.header import render_admin_header
from components.shared import badge_servicio, badge_metodo_pago, render_seccion


@ui.page("/admin/autoservicio")
async def admin_autoservicio():
    if redirigir_si_no_autenticado():
        return

    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
    )
    ui.add_head_html('<link rel="stylesheet" href="/static/admin.css">')

    page_client = _ng.context.client
    client_id = registrar_admin_client(page_client)
    page_client.on_disconnect(lambda c=page_client: remover_admin_client(client_id))

    def _client():
        return get_admin_client(client_id)

    render_admin_header(
        icon_path="/media/icons/leaf.svg",
        title="Autoservicio",
        back_url="/admin",
    )

    @ui.refreshable
    async def vista_ordenes():
        with ui.element("div").props("id=admin-content").style("width:100%;"):
            ordenes = await database_web.obtener_ordenes_autoservicio_asignacion_async()

            pendientes = [v for v in ordenes if v["estado"] == "Pendiente"]
            en_proceso = [v for v in ordenes if v["estado"] == "En proceso"]

            def _render_auto_pendiente(v, en_proceso):
                nombre = v.get("nombre_cliente") or "Sin nombre"
                peso = v.get("peso_kg", 0) or 0
                modalidad = v.get("modalidad", "")
                with ui.element("div").classes("orden-card"):
                    with ui.element("div").style("flex:1;min-width:0;"):
                        ui.html(
                            f'<div class="orden-numero">Orden #{v["id_transaccion"]}</div>'
                            f"{badge_servicio(v['tipo_servicio'])} "
                            f"{badge_metodo_pago(modalidad)}"
                        )
                        ui.html(f'<div class="orden-nombre">{nombre}</div>')
                        ui.html(
                            f'<div class="orden-meta">{v["fecha_hora"]} · {peso} kg · Pagado: <strong>${v["monto_pagado"]}</strong></div>'
                        )
                    with ui.element("div").style("flex-shrink:0;"):
                        ui.html('<div class="maquina-label">Asignar a:</div>')
                        with ui.element("div").classes("maquinas-row"):
                            for equipo_id, equipo in hardware.EQUIPOS.items():
                                ocupado = hardware.equipo_esta_ocupado(equipo_id)
                                supera = peso > equipo["capacidad_kg"]
                                if ocupado:
                                    with (
                                        ui.element("div")
                                        .classes("btn-maquina btn-disabled")
                                        .style(
                                            "display:inline-flex;align-items:center;gap:6px;"
                                        )
                                    ):
                                        ui.image("/media/icons/gear.svg").style(
                                            "width:16px;height:16px;"
                                        )
                                        ui.html(f"{equipo['nombre']} (En uso)")
                                elif supera:
                                    with (
                                        ui.element("div")
                                        .classes("btn-maquina btn-disabled")
                                        .style(
                                            "display:inline-flex;align-items:center;gap:6px;"
                                        )
                                        .tooltip(
                                            f"Supera capacidad: {peso}kg > {equipo['capacidad_kg']}kg"
                                        )
                                    ):
                                        ui.image("/media/icons/warning.svg").style(
                                            "width:16px;height:16px;"
                                        )
                                        ui.html(
                                            f"{equipo['nombre']} ({equipo['capacidad_kg']}kg max)"
                                        )
                                else:
                                    with (
                                        ui.element("div")
                                        .classes("btn-maquina btn-iniciar")
                                        .style(
                                            "display:inline-flex;align-items:center;gap:6px;cursor:pointer;"
                                        )
                                        .on(
                                            "click",
                                            lambda e, venta=v, eid=equipo_id, en=equipo[
                                                "nombre"
                                            ]: asyncio.create_task(
                                                iniciar_maquina(venta, en, eid)
                                            ),
                                        )
                                    ):
                                        ui.image("/media/icons/gear.svg").style(
                                            "width:16px;height:16px;filter:brightness(0) invert(1);"
                                        )
                                        ui.html(f"{equipo['nombre']}")

            def _render_auto_en_proceso(v):
                nombre = v.get("nombre_cliente") or "Sin nombre"
                minutos_txt = ""
                if v.get("inicio_servicio"):
                    try:
                        from datetime import datetime as dt

                        inicio = dt.strptime(
                            v["inicio_servicio"], "%Y-%m-%d %H:%M:%S"
                        )
                        mins = int((dt.now() - inicio).total_seconds() / 60)
                        minutos_txt = f" · ⏱ {mins} min"
                    except Exception:
                        pass

                equipo_id = next(
                    (
                        eid
                        for eid, eq in hardware.EQUIPOS.items()
                        if eq["nombre"] == v.get("id_equipo", "")
                    ),
                    None,
                )
                es_sostenido = (
                    equipo_id
                    and hardware.EQUIPOS.get(equipo_id, {}).get("modo") == "sostenido"
                )
                seg_restantes = (
                    hardware.tiempo_restante_sostenido(equipo_id)
                    if es_sostenido
                    else 0
                )
                timer_txt = ""
                if es_sostenido and seg_restantes > 0:
                    m, s = divmod(seg_restantes, 60)
                    timer_txt = f" · ⏳ {m:02d}:{s:02d}"

                modalidad = v.get("modalidad", "")
                with ui.element("div").classes("orden-card en-proceso"):
                    with ui.element("div").style("flex:1;min-width:0;"):
                        ui.html(
                            f'<div class="orden-numero">Orden #{v["id_transaccion"]}</div>'
                            f"{badge_servicio(v['tipo_servicio'])} "
                            f"{badge_metodo_pago(modalidad)} "
                            f'<span style="font-size:0.78rem;color:#b45309;font-weight:700;display:inline-flex;align-items:center;gap:4px;">'
                            f'<img src="/media/icons/gear.svg" style="width:14px;height:14px;"> {v["id_equipo"]}</span>'
                        )
                        ui.html(f'<div class="orden-nombre">{nombre}</div>')
                        ui.html(
                            f'<div class="orden-meta">{v["fecha_hora"]}{minutos_txt}{timer_txt} · Pagado: <strong>${v["monto_pagado"]}</strong></div>'
                        )
                    with ui.element("div").style(
                        "flex-shrink:0;display:flex;flex-direction:column;gap:8px;align-items:flex-end;"
                    ):
                        if es_sostenido:
                            ui.label("⏹ Detener").classes(
                                "btn-maquina btn-pausar"
                            ).on(
                                "click",
                                lambda e, venta=v, eid=equipo_id: asyncio.create_task(
                                    detener_maquina_sostenida(venta, eid)
                                ),
                            )
                        else:
                            ui.label("✅ Finalizar").classes(
                                "btn-maquina btn-finalizar"
                            ).on(
                                "click",
                                lambda e, venta=v: asyncio.create_task(
                                    finalizar_orden(venta)
                                ),
                            )
                        ui.label("⏸ Cancelar").classes(
                            "btn-maquina btn-pausar"
                        ).on(
                            "click",
                            lambda e, venta=v: asyncio.create_task(
                                cancelar_orden(venta)
                            ),
                        )

            render_seccion(
                "circle-yellow",
                "Órdenes Pendientes",
                "badge-pendiente",
                pendientes,
                lambda v: _render_auto_pendiente(v, en_proceso),
            )
            render_seccion(
                "circle-orange",
                "En Proceso",
                "badge-en-proceso",
                en_proceso,
                _render_auto_en_proceso,
            )

    async def iniciar_maquina(venta, nombre_maquina, equipo_id):
        await hardware.activar_lavadora(equipo_id)
        await database_web.marcar_en_proceso_async(
            venta["id_transaccion"], nombre_maquina
        )
        cl = _client()
        if cl:
            with cl:
                ui.notify(
                    f"▶ {nombre_maquina} iniciada — {venta.get('nombre_cliente', 'Orden')} #{venta['id_transaccion']}",
                    type="positive",
                    position="top",
                )
        await vista_ordenes.refresh()

    async def detener_maquina_sostenida(venta, equipo_id):
        await hardware.apagar_maquina(equipo_id)
        await database_web.marcar_completado_async(
            venta["id_transaccion"], venta["id_equipo"]
        )
        cl = _client()
        if cl:
            with cl:
                ui.notify(
                    f"⏹ {venta.get('id_equipo')} detenida — Orden #{venta['id_transaccion']}",
                    type="warning",
                    position="top",
                )
        await vista_ordenes.refresh()

    async def finalizar_orden(venta):
        equipo_id = next(
            (
                eid
                for eid, eq in hardware.EQUIPOS.items()
                if eq["nombre"] == venta.get("id_equipo", "")
            ),
            None,
        )
        if equipo_id and hardware.EQUIPOS[equipo_id].get("modo") == "sostenido":
            await hardware.apagar_maquina(equipo_id)

        await database_web.marcar_completado_async(
            venta["id_transaccion"], venta["id_equipo"]
        )
        cl = _client()
        if cl:
            with cl:
                ui.notify(
                    f"✅ Orden #{venta['id_transaccion']} completada",
                    type="positive",
                    position="top",
                )
        await vista_ordenes.refresh()

    async def cancelar_orden(venta):
        equipo_id = next(
            (
                eid
                for eid, eq in hardware.EQUIPOS.items()
                if eq["nombre"] == venta.get("id_equipo", "")
            ),
            None,
        )
        if equipo_id:
            eq = hardware.EQUIPOS[equipo_id]
            if eq.get("modo") == "sostenido":
                await hardware.apagar_maquina(equipo_id)
            else:
                await hardware.activar_lavadora(equipo_id)
        await database_web.marcar_completado_async(
            venta["id_transaccion"], venta["id_equipo"]
        )
        cl = _client()
        if cl:
            with cl:
                ui.notify(
                    f"⏸ Orden #{venta['id_transaccion']} cancelada",
                    type="warning",
                    position="top",
                )
        await vista_ordenes.refresh()

    await vista_ordenes()
    registrar_callback_autoservicio(vista_ordenes.refresh)
    page_client.on_disconnect(lambda: remover_callback_autoservicio(vista_ordenes.refresh))
