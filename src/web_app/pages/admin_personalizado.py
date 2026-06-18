import asyncio
from nicegui import ui, app
import nicegui as _ng_p

import hardware
import database_web
from services.auth import redirigir_si_no_autenticado, usuario_actual, USUARIOS
from services.notifications import (
    registrar_callback_admin,
    remover_callback_admin,
    registrar_admin_client,
    remover_admin_client,
    get_admin_client,
)
from components.admin.header import render_admin_header
from database_web import ETAPAS_KANBAN


@ui.page("/admin/personalizado")
async def admin_personalizado():
    if redirigir_si_no_autenticado():
        return

    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
    )
    ui.add_head_html('<link rel="stylesheet" href="/static/admin.css">')

    page_client = _ng_p.context.client
    client_id = registrar_admin_client(page_client)
    page_client.on_disconnect(lambda c=page_client: remover_admin_client(client_id))

    def _client():
        return get_admin_client(client_id)

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
            else:
                ui.notify("Contraseña incorrecta", type="negative")

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancelar", on_click=dialogo_cambio.close).props("flat")
            ui.button("Confirmar", on_click=confirmar_cambio).props("color=primary")

    render_admin_header(
        icon_path="/media/icons/shirt.svg",
        title="Servicio Personalizado",
        back_url="/admin",
        dialogo_cambio=dialogo_cambio,
    )

    # ── Kanban ──
    @ui.refreshable
    async def vista_kanban():
        with ui.element("div").props("id=admin-content").style("width:100%;"):
            ordenes = await database_web.obtener_ordenes_personalizadas_async()

            ETAPAS_INFO = [
                ("Recibido", "/media/icons/inbox.svg", "#eff6ff", "#3b82f6"),
                ("En Proceso", "/media/icons/gear.svg", "#fff7ed", "#f59e0b"),
                ("Alistando", "/media/icons/basket.svg", "#f0fdf4", "#22c55e"),
                (
                    "Listo para Entrega",
                    "/media/icons/box.svg",
                    "#fdf4ff",
                    "#a855f7",
                ),
                ("Entregado", "/media/icons/box.svg", "#f0fdf4", "#16a34a"),
            ]

            with ui.element("div").classes("kanban-board"):
                for etapa_nombre, icono_path, bg, color in ETAPAS_INFO:
                    cards_etapa = [
                        o for o in ordenes if o.get("etapa_kanban") == etapa_nombre
                    ]
                    with (
                        ui.element("div")
                        .classes("kanban-col")
                        .style(f"background:{bg};")
                    ):
                        with (
                            ui.element("div")
                            .classes("kanban-col-title")
                            .style(
                                f"color:{color};display:flex;align-items:center;gap:6px;"
                            )
                        ):
                            ui.image(icono_path).style(
                                "width:18px;height:18px;object-fit:contain;"
                            )
                            ui.html(
                                f'{etapa_nombre} <span style="font-weight:500;font-size:0.8rem;opacity:0.6;">({len(cards_etapa)})</span>'
                            )
                        for orden in cards_etapa:
                            _render_kanban_card(orden, etapa_nombre)

    def _render_kanban_card(orden, etapa_actual):
        nombre = orden.get("nombre_cliente") or "Sin nombre"
        peso = orden.get("peso_kg", 0) or 0
        notas = orden.get("notas") or ""
        servicio = orden.get("tipo_servicio", "")

        with ui.element("div").classes("kanban-card"):
            ui.html(f'<div class="kanban-card-nombre">{nombre}</div>')
            ui.html(
                f'<div class="kanban-card-meta">#{orden["id_transaccion"]} · {servicio} · {peso} kg</div>'
            )
            ui.html(f'<div class="kanban-card-meta">{orden["fecha_hora"]}</div>')
            if notas:
                ui.html(
                    f'<div class="kanban-card-notas" style="display:flex;align-items:flex-start;gap:6px;">'
                    f'<img src="/media/icons/notes.svg" style="width:14px;height:14px;margin-top:2px;">'
                    f"<span>{notas}</span></div>"
                )

            if etapa_actual == "En Proceso" and orden.get("id_equipo"):
                equipo_id = next(
                    (
                        eid
                        for eid, eq in hardware.EQUIPOS.items()
                        if eq["nombre"] == orden["id_equipo"]
                    ),
                    None,
                )
                if (
                    equipo_id
                    and hardware.EQUIPOS.get(equipo_id, {}).get("modo") == "sostenido"
                ):
                    seg_restantes = hardware.tiempo_restante_sostenido(equipo_id)
                    if seg_restantes > 0:
                        m, s = divmod(seg_restantes, 60)
                        ui.html(
                            f'<div style="font-size:0.8rem;color:#f59e0b;font-weight:700;margin-top:4px;display:flex;align-items:center;gap:4px;">'
                            f'<img src="/media/icons/gear.svg" style="width:14px;height:14px;">'
                            f"⏳ {m:02d}:{s:02d} restantes</div>"
                        )
                    else:
                        ui.html(
                            '<div style="font-size:0.8rem;color:#ef4444;font-weight:700;margin-top:4px;">'
                            "Tiempo expirado — finalice la orden</div>"
                        )

            with ui.row().classes("gap-1 mt-2 flex-wrap"):
                idx_actual = (
                    ETAPAS_KANBAN.index(etapa_actual)
                    if etapa_actual in ETAPAS_KANBAN
                    else 0
                )

                if idx_actual < len(ETAPAS_KANBAN) - 1:
                    siguiente = ETAPAS_KANBAN[idx_actual + 1]

                    if siguiente == "En Proceso":

                        async def abrir_iniciar(o=orden):
                            peso_o = o.get("peso_kg") or 0
                            duracion_default = o.get("duracion_estimada_min") or 60

                            cl = _client()
                            if not cl:
                                return
                            with cl:
                                with ui.dialog() as d, ui.card().style(
                                    "min-width:420px;"
                                ):
                                    ui.label(
                                        f"Iniciar — {o.get('nombre_cliente')} #{o['id_transaccion']}"
                                    ).classes("text-lg font-bold mb-2")

                                    async def iniciar_sin_maquina():
                                        await database_web.actualizar_etapa_kanban_async(
                                            o["id_transaccion"], "En Proceso"
                                        )
                                        d.close()
                                        await vista_kanban.refresh()
                                        cl2 = _client()
                                        if cl2:
                                            with cl2:
                                                ui.notify(
                                                    "Orden iniciada sin máquina del sistema",
                                                    type="info",
                                                )

                                    ui.button(
                                        "Iniciar sin máquina (equipo externo)",
                                        on_click=iniciar_sin_maquina,
                                    ).props("flat color=grey").classes("w-full mb-2")

                                    ui.html(
                                        '<div style="border-top:1px solid #e2e8f0;margin:8px 0;"></div>'
                                    )
                                    ui.label(
                                        "O asignar máquina del sistema:"
                                    ).classes("font-semibold mb-1")

                                    maquinas_ok = {
                                        eid: eq
                                        for eid, eq in hardware.EQUIPOS.items()
                                        if peso_o <= eq["capacidad_kg"]
                                    }

                                    if not maquinas_ok:
                                        ui.html(
                                            '<div style="color:#ef4444;">Ninguna máquina tiene capacidad para este peso.</div>'
                                        )
                                    else:
                                        opts_texto = {
                                            f"{eq['nombre']} ({eq['modo']}, máx {eq['capacidad_kg']}kg)": eid
                                            for eid, eq in maquinas_ok.items()
                                        }
                                        sel_maq = ui.select(
                                            list(opts_texto.keys()), label="Máquina"
                                        ).classes("w-full")
                                        sel_tiempo = ui.number(
                                            "Duración (min)",
                                            value=duracion_default,
                                            min=1,
                                            step=1,
                                        ).classes("w-full mt-2")

                                        async def iniciar_con_maquina():
                                            eid = opts_texto.get(sel_maq.value)
                                            if not eid:
                                                ui.notify(
                                                    "Selecciona una máquina",
                                                    type="warning",
                                                )
                                                return
                                            eq = hardware.EQUIPOS[eid]
                                            duracion = int(
                                                sel_tiempo.value or duracion_default
                                            )
                                            if duracion < 1:
                                                ui.notify(
                                                    "La duración debe ser mayor a 0",
                                                    type="warning",
                                                )
                                                return
                                            if hardware.equipo_sostenido_activo(eid):
                                                ui.notify(
                                                    f"{eq['nombre']} ya está en uso.",
                                                    type="warning",
                                                )
                                                return

                                            if eq.get("modo") == "sostenido":
                                                await hardware.activar_lavadora_con_duracion(
                                                    eid, duracion
                                                )
                                            else:
                                                await hardware.activar_lavadora(eid)

                                            await database_web.actualizar_etapa_kanban_async(
                                                o["id_transaccion"],
                                                "En Proceso",
                                                equipo_id=eq["nombre"],
                                            )
                                            d.close()
                                            await vista_kanban.refresh()
                                            cl2 = _client()
                                            if cl2:
                                                with cl2:
                                                    ui.notify(
                                                        f"▶ {eq['nombre']} iniciada por {duracion}min",
                                                        type="positive",
                                                    )

                                        with ui.row().classes(
                                            "w-full justify-end mt-3"
                                        ):
                                            ui.button(
                                                "Cancelar", on_click=d.close
                                            ).props("flat")
                                            ui.button(
                                                "Iniciar con máquina",
                                                on_click=iniciar_con_maquina,
                                            ).props("color=green")
                            d.open()

                        ui.button(
                            f"→ {siguiente}", on_click=abrir_iniciar
                        ).props("size=xs color=primary outline").classes("text-xs")
                    else:

                        async def avanzar(o=orden, sig=siguiente):
                            if etapa_actual == "En Proceso" and o.get("id_equipo"):
                                equipo_id = next(
                                    (
                                        eid
                                        for eid, eq in hardware.EQUIPOS.items()
                                        if eq["nombre"] == o["id_equipo"]
                                    ),
                                    None,
                                )
                                if (
                                    equipo_id
                                    and hardware.EQUIPOS.get(equipo_id, {}).get("modo")
                                    == "sostenido"
                                ):
                                    await hardware.apagar_maquina(equipo_id)
                            await database_web.actualizar_etapa_kanban_async(
                                o["id_transaccion"], sig
                            )
                            await vista_kanban.refresh()

                        ui.button(f"→ {siguiente}", on_click=avanzar).props(
                            "size=xs color=primary outline"
                        ).classes("text-xs")

                async def abrir_notas(o=orden):
                    cl = _client()
                    if not cl:
                        return
                    with cl:
                        with ui.dialog() as d_notas, ui.card().style(
                            "min-width:360px;"
                        ):
                            ui.label(
                                f"Notas — {o.get('nombre_cliente')} #{o['id_transaccion']}"
                            ).classes("font-bold mb-2")
                            txt = (
                                ui.textarea("Notas", value=o.get("notas") or "")
                                .classes("w-full")
                                .style("min-height:120px;")
                            )
                            with ui.row().classes("w-full justify-end mt-2"):
                                ui.button("Cancelar", on_click=d_notas.close).props(
                                    "flat"
                                )

                                async def guardar_notas():
                                    await database_web.actualizar_notas_async(
                                        o["id_transaccion"], txt.value
                                    )
                                    d_notas.close()
                                    await vista_kanban.refresh()

                                ui.button("Guardar", on_click=guardar_notas).props(
                                    "color=primary"
                                )
                            d_notas.open()

                ui.button("Notas", on_click=abrir_notas).props(
                    "icon=img:/media/icons/notes.svg size=xs flat"
                ).classes("text-xs")

    await vista_kanban()
    registrar_callback_admin(vista_kanban.refresh)
    page_client.on_disconnect(lambda: remover_callback_admin(vista_kanban.refresh))
