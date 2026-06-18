from nicegui import ui
from components.shared import render_user_chip
from services.auth import usuario_actual


def render_admin_header(
    icon_path, title, back_url="/admin", extra_buttons=None, dialogo_cambio=None
):
    with ui.element("div").props("id=admin-header"):
        with ui.element("div").props("id=admin-header-inner"):
            with ui.element("div").classes("logo-area"):
                ui.image("/media/logo_slogan.png")
                with ui.element("div"):
                    ui.html(
                        f'<div class="admin-title" style="display:flex;align-items:center;gap:8px;">'
                        f'<img src="{icon_path}" style="width:28px;height:28px;">'
                        f"{title}</div>"
                    )
                    ui.html('<div class="admin-subtitle">Lavandería EcoLuna</div>')
            with ui.element("div").style("display:flex;align-items:center;gap:12px;"):
                if extra_buttons:
                    for btn in extra_buttons:
                        btn()
                if back_url:
                    ui.button(
                        "← Dashboard", on_click=lambda: ui.navigate.to(back_url)
                    ).props("flat size=sm")
                render_user_chip(dialogo_cambio)
