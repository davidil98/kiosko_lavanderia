from nicegui import ui, app
import nicegui as _ng
import database_web
from services.auth import esta_autenticado, usuario_actual, es_superadmin
from services.notifications import (
    registrar_callback_operativo,
    remover_callback_operativo,
)
from components.shared import render_user_chip


@ui.page("/admin")
async def admin_dashboard():
    if not esta_autenticado():
        ui.navigate.to("/admin/login")
        return

    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
    )
    ui.add_head_html('<link rel="stylesheet" href="/static/admin.css">')

    page_client = _ng.context.client

    with ui.element("div").props("id=admin-header"):
        with ui.element("div").props("id=admin-header-inner"):
            with ui.element("div").classes("logo-area"):
                ui.image("/media/logo_slogan.png")
                with ui.element("div"):
                    ui.html('<div class="admin-title">Panel de Administración</div>')
                    ui.html('<div class="admin-subtitle">Lavandería EcoLuna</div>')
            render_user_chip()

    @ui.refreshable
    async def contenido_dashboard():
        with ui.element("div").props("id=admin-content"):
            ui.html(
                '<h2 style="font-size:1.5rem;font-weight:800;color:#1e293b;margin-bottom:6px;display:flex;align-items:center;gap:10px;">'
                '<img src="/media/icons/wave.svg" style="width:32px;height:32px;">'
                "Bienvenido</h2>"
            )
            ui.html(
                f'<p style="color:#64748b;margin-bottom:32px;">Selecciona el módulo de trabajo, <strong>{usuario_actual()}</strong>.</p>'
            )

            contadores = await database_web.obtener_contadores_pendientes_async()
            pendiente_peso = contadores.get("Pendiente-peso", 0)
            pendiente_pago = contadores.get("Pendiente-pago", 0) + contadores.get(
                "Procesando-pago", 0
            )
            urgente_total = pendiente_peso + pendiente_pago
            asignar_auto = contadores.get("Pendiente", 0)
            en_proceso_auto = contadores.get("En proceso", 0)

            with ui.element("div").classes("dash-grid"):
                with (
                    ui.element("div")
                    .classes("dash-card")
                    .on("click", lambda: ui.navigate.to("/admin/operativo"))
                ):
                    with ui.element("div").classes("dash-card-icon"):
                        ui.image("/media/icons/inbox.svg").style(
                            "width:64px;height:64px;object-fit:contain;"
                        )
                    ui.html(
                        '<div class="dash-card-title" style="display:flex;align-items:center;justify-content:center;gap:8px;">'
                        "Panel Operativo"
                        f'<span class="badge badge-en-proceso" style="font-size:0.9rem;padding:4px 12px;">{urgente_total}</span>'
                        "</div>"
                    )
                    ui.html(
                        '<div class="dash-card-sub">'
                        f"Aprobar pesos ({pendiente_peso}) · Confirmar pagos ({pendiente_pago})"
                        "</div>"
                    )

                total_auto = asignar_auto + en_proceso_auto
                with (
                    ui.element("div")
                    .classes("dash-card")
                    .on("click", lambda: ui.navigate.to("/admin/autoservicio"))
                ):
                    with ui.element("div").classes("dash-card-icon"):
                        ui.image("/media/icons/leaf.svg").style(
                            "width:64px;height:64px;object-fit:contain;"
                        )
                    ui.html(
                        '<div class="dash-card-title" style="display:flex;align-items:center;justify-content:center;gap:8px;">'
                        "Autoservicio"
                        f'<span class="badge badge-pendiente" style="font-size:0.9rem;padding:4px 12px;">{total_auto}</span>'
                        "</div>"
                    )
                    ui.html(
                        '<div class="dash-card-sub">'
                        f"Asignar ({asignar_auto}) · En proceso ({en_proceso_auto})"
                        "</div>"
                    )

                with (
                    ui.element("div")
                    .classes("dash-card")
                    .on("click", lambda: ui.navigate.to("/admin/personalizado"))
                ):
                    with ui.element("div").classes("dash-card-icon"):
                        ui.image("/media/icons/shirt.svg").style(
                            "width:64px;height:64px;object-fit:contain;"
                        )
                    ui.html('<div class="dash-card-title">Servicio Personalizado</div>')
                    ui.html(
                        '<div class="dash-card-sub">Tablero kanban de lavado, secado y doblado</div>'
                    )

                with (
                    ui.element("div")
                    .classes("dash-card")
                    .on("click", lambda: ui.navigate.to("/admin/cortes"))
                ):
                    with ui.element("div").classes("dash-card-icon"):
                        ui.image("/media/icons/ticket.svg").style(
                            "width:64px;height:64px;object-fit:contain;"
                        )
                    ui.html('<div class="dash-card-title">Cortes de Caja</div>')
                    ui.html(
                        '<div class="dash-card-sub">Apertura, movimientos y cierre de caja</div>'
                    )

                if es_superadmin():
                    with (
                        ui.element("div")
                        .classes("dash-card")
                        .on("click", lambda: ui.navigate.to("/admin/superadmin"))
                    ):
                        with ui.element("div").classes("dash-card-icon"):
                            ui.image("/media/icons/gear.svg").style(
                                "width:64px;height:64px;object-fit:contain;"
                            )
                        ui.html(
                            '<div class="dash-card-title" '
                            'style="display:flex;align-items:center;justify-content:center;gap:8px;">'
                            "Superadmin"
                            '<span class="badge" style="background:#fef3c7;color:#92400e;font-size:0.7rem;padding:2px 8px;">'
                            "MOI/DAVID"
                            "</span></div>"
                        )
                        ui.html(
                            '<div class="dash-card-sub">Configuración de '
                            "servicios, segmentaciones y calculadora</div>"
                        )

    def cerrar_sesion():
        app.storage.user["authenticated"] = False
        app.storage.user["usuario"] = ""
        ui.navigate.to("/admin/login")

    with ui.page_sticky(position="bottom-right", x_offset=20, y_offset=20):
        ui.button("Cerrar sesión", on_click=cerrar_sesion).props("flat color=negative")

    await contenido_dashboard()
    registrar_callback_operativo(contenido_dashboard.refresh)
    page_client.on_disconnect(
        lambda: remover_callback_operativo(contenido_dashboard.refresh)
    )
