from nicegui import ui, app
from services.auth import esta_autenticado, usuario_actual
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

    with ui.element("div").props("id=admin-header"):
        with ui.element("div").props("id=admin-header-inner"):
            with ui.element("div").classes("logo-area"):
                ui.image("/media/logo_slogan.png")
                with ui.element("div"):
                    ui.html('<div class="admin-title">Panel de Administración</div>')
                    ui.html('<div class="admin-subtitle">Lavandería EcoLuna</div>')
            render_user_chip()

    with ui.element("div").props("id=admin-content"):
        ui.html(
            '<h2 style="font-size:1.5rem;font-weight:800;color:#1e293b;margin-bottom:6px;display:flex;align-items:center;gap:10px;">'
            '<img src="/media/icons/wave.svg" style="width:32px;height:32px;">'
            "Bienvenido</h2>"
        )
        ui.html(
            f'<p style="color:#64748b;margin-bottom:32px;">Selecciona el módulo de trabajo, <strong>{usuario_actual()}</strong>.</p>'
        )

        with ui.element("div").classes("dash-grid"):
            with (
                ui.element("div")
                .classes("dash-card")
                .on("click", lambda: ui.navigate.to("/admin/autoservicio"))
            ):
                with ui.element("div").classes("dash-card-icon"):
                    ui.image("/media/icons/leaf.svg").style(
                        "width:64px;height:64px;object-fit:contain;"
                    )
                ui.html('<div class="dash-card-title">Lavado de Autoservicio</div>')
                ui.html(
                    '<div class="dash-card-sub">Asignar máquinas y gestionar pedidos del kiosko</div>'
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

        def cerrar_sesion():
            app.storage.user["authenticated"] = False
            app.storage.user["usuario"] = ""
            ui.navigate.to("/admin/login")

        ui.button("Cerrar sesión", on_click=cerrar_sesion).props(
            "flat color=negative"
        ).classes("mt-8")
