"""Página de login del panel admin (`@ui.page("/admin/login")`).

Formulario con usuario + contraseña. Si las credenciales son válidas
(vía `ui.compartido.auth.login`), redirige a `/admin`. Si no, notifica
error y limpia el campo de contraseña.
"""

from nicegui import app, ui

from app.ui.compartido.auth import login
from app.ui.compartido.estilos import ADMIN_CSS, LOGOTIPO


@ui.page("/admin/login")
def admin_login():
    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
    )
    ui.add_head_html(f'<link rel="stylesheet" href="{ADMIN_CSS}">')

    with ui.element("div").classes("login-wrap"):
        with ui.element("div").classes("login-card"):
            ui.image(LOGOTIPO).style(
                "width:70px;height:70px;object-fit:contain;"
                "margin:0 auto 16px;display:block;"
            )
            ui.html('<div class="login-title">Panel EcoLuna</div>')
            ui.html('<div class="login-sub">Accede con tu cuenta de operador</div>')

            user_input = (
                ui.input("Usuario").props("outlined dense").classes("w-full mb-3")
            )
            pass_input = (
                ui.input("Contraseña")
                .props("outlined dense type=password")
                .classes("w-full mb-5")
            )

            def intentar_login() -> None:
                u = (user_input.value or "").strip()
                p = (pass_input.value or "").strip()
                if login(u, p):
                    ui.navigate.to("/admin")
                else:
                    ui.notify(
                        "Usuario o contraseña incorrectos.",
                        type="negative",
                    )
                    pass_input.value = ""

            ui.button("Ingresar", on_click=intentar_login).props(
                "color=primary"
            ).classes("w-full text-lg font-bold py-3")
