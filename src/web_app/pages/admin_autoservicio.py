import asyncio
import os
from nicegui import ui, app
import nicegui as _ng

import hardware
import database_web
from services.auth import esta_autenticado, usuario_actual, redirigir_si_no_autenticado, USUARIOS
from services.notifications import (
    state,
    notificar_admin,
    notificar_kiosko,
    registrar_callback_admin,
    remover_callback_admin,
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

    # ── Bypass Dialog ──
    async def ejecutar_bypass():
        pwd = input_bypass_pwd.value
        if pwd == os.getenv("BYPASS_PASSWORD", "admin123"):
            nuevo_id = await database_web.registrar_venta_async(
                servicio="Cortesía / Bypass",
                monto=0,
                ingresado=0,
                cambio=0,
                equipo="N/A",
                duracion=45,
                nombre_cliente="Cortesía",
                peso_kg=0,
                modalidad="autoservicio",
            )
            dialogo_bypass.close()
            input_bypass_pwd.value = ""
            ui.notify(
                "Servicio de cortesía creado y añadido a pendientes.", type="positive"
            )
            notificar_admin()
        else:
            ui.notify("Contraseña incorrecta", type="negative")

    with ui.dialog() as dialogo_bypass, ui.card().style("min-width:300px;"):
        ui.label("Autorizar Servicio de Cortesía").classes(
            "text-lg font-bold text-slate-800 mb-2"
        )
        input_bypass_pwd = (
            ui.input("Contraseña").props("type=password").classes("w-full mb-4")
        )
        with ui.row().classes("w-full justify-end"):
            ui.button("Cancelar", on_click=dialogo_bypass.close).props("flat")
            ui.button("Autorizar", on_click=ejecutar_bypass).props("color=green")

    # ── Cambio de usuario Dialog ──
    with ui.dialog() as dialogo_cambio, ui.card().style("min-width:320px;"):
        ui.label("Cambiar operador en turno").classes(
            "text-lg font-bold text-slate-800 mb-2"
        )
        sel_usuario = ui.select(
            list(USUARIOS.keys()), label="Selecciona usuario", value=usuario_actual()
        ).classes("w-full")
        input_cambio_pwd = (
            ui.input("Contraseña").props("type=password").classes("w-full mt-3 mb-4")
        )

        def confirmar_cambio():
            u = sel_usuario.value
            p = input_cambio_pwd.value
            if u in USUARIOS and USUARIOS[u] == p:
                app.storage.user["usuario"] = u
                ui.notify(f"Sesión cambiada a {u}", type="positive")
                dialogo_cambio.close()
                input_cambio_pwd.value = ""
                ui.navigate.to("/admin/autoservicio")
            else:
                ui.notify("Contraseña incorrecta", type="negative")

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancelar", on_click=dialogo_cambio.close).props("flat")
            ui.button("Confirmar", on_click=confirmar_cambio).props("color=primary")

    # ── Header ──
    def extra_bypass():
        ui.button(
            "Cortesía / Bypass",
            on_click=dialogo_bypass.open,
        ).props(
            "icon=img:/media/icons/ticket.svg outline color=primary size=sm"
        ).classes("font-bold")

    render_admin_header(
        icon_path="/media/icons/leaf.svg",
        title="Autoservicio",
        back_url="/admin",
        extra_buttons=[extra_bypass],
        dialogo_cambio=dialogo_cambio,
    )

    # ── Vista de Órdenes ──
    @ui.refreshable
    async def vista_ordenes():
        with ui.element("div").props("id=admin-content").style("width:100%;"):
            ventas = await database_web.obtener_ventas_activas_async()

            # DEDUPLICAR por id_transaccion
            seen = {}
            for v in ventas:
                seen[v["id_transaccion"]] = v
            ventas = list(seen.values())

            esperando_peso = [v for v in ventas if v["estado"] == "Pendiente-peso"]
            procesando_pago = [
                v
                for v in ventas
                if v["estado"] in ("Procesando-pago", "Pendiente-pago")
            ]
            pendientes = [v for v in ventas if v["estado"] == "Pendiente"]
            en_proceso = [v for v in ventas if v["estado"] == "En proceso"]

            def _render_esperando_peso(v):
                nombre = v.get("nombre_cliente") or "Sin nombre"
                peso = v.get("peso_kg", 0) or 0
                with (
                    ui.element("div")
                    .classes("orden-card")
                    .style("border-left:4px solid #a855f7;")
                ):
                    with ui.element("div").style("flex:1;min-width:0;"):
                        ui.html(
                            f'<div class="orden-numero">Orden #{v["id_transaccion"]}</div>'
                            f"{badge_servicio(v['tipo_servicio'])} "
                            f'<span class="orden-servicio-badge" style="background:#f3e8ff;color:#7e22ce;">Validar peso</span>'
                        )
                        ui.html(f'<div class="orden-nombre">{nombre}</div>')
                        ui.html(
                            f'<div class="orden-meta">{v["fecha_hora"]} · Peso registrado: <strong>{peso} kg</strong></div>'
                        )
                    with ui.element("div").style(
                        "flex-shrink:0;display:flex;flex-direction:column;gap:8px;align-items:flex-end;"
                    ):
                        ui.label("✓ Aprobar").classes("btn-maquina btn-iniciar").on(
                            "click",
                            lambda e, venta=v: asyncio.create_task(
                                aprobar_peso(venta)
                            ),
                        )
                        ui.label("✕ Rechazar").classes("btn-maquina btn-pausar").on(
                            "click",
                            lambda e, venta=v: asyncio.create_task(
                                rechazar_peso(venta)
                            ),
                        )

            def _render_procesando_pago(v):
                nombre = v.get("nombre_cliente") or "Sin nombre"
                peso = v.get("peso_kg", 0) or 0
                monto = v.get("monto_pagado", 0) or 0
                modalidad = v.get("modalidad", "")
                es_pago_pendiente = v["estado"] == "Pendiente-pago"
                if "pendiente-pago" in modalidad or "mostrador" in modalidad:
                    label = "Efectivo mostrador"
                    color = "#16a34a"
                elif "terminal" in modalidad:
                    label = "Terminal"
                    color = "#f59e0b"
                else:
                    label = "En pago"
                    color = "#3b82f6"
                folio_input = None
                with (
                    ui.element("div")
                    .classes("orden-card")
                    .style(f"border-left:4px solid {color};")
                ):
                    with ui.element("div").style("flex:1;min-width:0;"):
                        ui.html(
                            f'<div class="orden-numero">Orden #{v["id_transaccion"]}</div>'
                            f"{badge_servicio(v['tipo_servicio'])} "
                            f'<span class="orden-servicio-badge" style="background:{color}22;color:{color};">{label}</span> '
                            f"{badge_metodo_pago(modalidad)}"
                        )
                        ui.html(f'<div class="orden-nombre">{nombre}</div>')
                        ui.html(
                            f'<div class="orden-meta">{v["fecha_hora"]} · {peso} kg · Monto: <strong>${monto}</strong></div>'
                        )
                        if es_pago_pendiente:
                            folio_input = (
                                ui.input("Folio de transacción (opcional)")
                                .props("outlined dense")
                                .classes("mb-2")
                            )
                    with ui.element("div").style(
                        "flex-shrink:0;display:flex;flex-direction:column;gap:8px;align-items:flex-end;"
                    ):
                        if es_pago_pendiente:
                            ui.label("✓ Confirmar pago").classes(
                                "btn-maquina btn-iniciar"
                            ).on(
                                "click",
                                lambda e, venta=v, inp=folio_input: asyncio.create_task(
                                    confirmar_folio(venta, inp)
                                ),
                            )
                            ui.label("✕ Cancelar").classes(
                                "btn-maquina btn-pausar"
                            ).on(
                                "click",
                                lambda e, venta=v: asyncio.create_task(
                                    cancelar_pago_pendiente_handler(venta)
                                ),
                            )

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
                                en_uso = any(
                                    p["id_equipo"] == equipo["nombre"]
                                    for p in en_proceso
                                )
                                supera = peso > equipo["capacidad_kg"]
                                if en_uso:
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
                                            ]: (
                                                asyncio.create_task(
                                                    iniciar_maquina(venta, en, eid)
                                                )
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

            # Render sections
            render_seccion(
                "scale",
                "Esperando validación de peso",
                "badge-pendiente",
                esperando_peso,
                _render_esperando_peso,
            )
            render_seccion(
                "ticket",
                "Procesando pago",
                "badge-en-proceso",
                procesando_pago,
                _render_procesando_pago,
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

    # ── Action handlers ──
    async def aprobar_peso(venta):
        await database_web.aprobar_peso_async(
            venta["id_transaccion"], venta.get("peso_kg", 0), usuario_actual()
        )
        state.peso_ingresado = venta.get("peso_kg", 0)
        state.mostrando_metodos_pago = True
        state.limpiar_espera_admin()
        cl = _client()
        if cl:
            with cl:
                ui.notify(
                    f"✓ Peso aprobado — {venta.get('nombre_cliente', 'Orden')} #{venta['id_transaccion']}",
                    type="positive",
                    position="top",
                )
        await vista_ordenes.refresh()
        notificar_kiosko("Peso aprobado. Selecciona tu método de pago.", "positive")

    async def rechazar_peso(venta):
        await database_web.rechazar_peso_async(
            venta["id_transaccion"], usuario_actual()
        )
        state.peso_ingresado = 0.0
        state.peso_en_revision = 0.0
        state.peso_rechazado_notificado = True
        state.paso_actual = 2
        state.mostrando_metodos_pago = False
        state.limpiar_espera_admin()
        cl = _client()
        if cl:
            with cl:
                ui.notify(
                    f"↩ Peso rechazado — {venta.get('nombre_cliente', 'Orden')} #{venta['id_transaccion']}",
                    type="warning",
                    position="top",
                )
        await vista_ordenes.refresh()
        notificar_kiosko("El administrador pidió volver a pesar.", "warning")

    async def confirmar_folio(venta, folio_input):
        folio = folio_input.value.strip() if folio_input else ""
        await database_web.aprobar_pago_terminal_async(
            venta["id_transaccion"], folio, usuario_actual()
        )
        state.limpiar_espera_admin()
        state.procesar_exito(venta["id_transaccion"])
        notificar_admin()
        cl = _client()
        if cl:
            with cl:
                ui.notify(
                    f"✓ Pago confirmado — Orden #{venta['id_transaccion']}",
                    type="positive",
                    position="top",
                )
        await vista_ordenes.refresh()
        notificar_kiosko("Pago confirmado. Gracias por tu compra.", "positive")
        await asyncio.sleep(7)
        state.reset()

    async def cancelar_pago_pendiente_handler(venta):
        await database_web.cancelar_pago_pendiente_async(
            venta["id_transaccion"], usuario_actual()
        )
        state.mostrando_metodos_pago = True
        state.limpiar_espera_admin()
        cl = _client()
        if cl:
            with cl:
                ui.notify(
                    f"✕ Pago cancelado — Orden #{venta['id_transaccion']}",
                    type="warning",
                    position="top",
                )
        await vista_ordenes.refresh()
        notificar_kiosko(
            "El pago fue cancelado. Puedes intentar de nuevo.", "warning"
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
    registrar_callback_admin(vista_ordenes.refresh)
    page_client.on_disconnect(
        lambda: remover_callback_admin(vista_ordenes.refresh)
    )
