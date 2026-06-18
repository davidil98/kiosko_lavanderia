from nicegui import ui, app
from services.auth import USUARIOS


@ui.page("/admin/login")
def admin_login():
    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
    )
    ui.add_head_html('<link rel="stylesheet" href="/static/admin.css">')

    with ui.element("div").classes("login-wrap"):
        with ui.element("div").classes("login-card"):
            ui.image("/media/logo_slogan.png").style(
                "width:70px;height:70px;object-fit:contain;margin:0 auto 16px;display:block;"
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

            def intentar_login():
                u = user_input.value.strip()
                p = pass_input.value.strip()
                if u in USUARIOS and USUARIOS[u] == p:
                    app.storage.user["authenticated"] = True
                    app.storage.user["usuario"] = u
                    ui.navigate.to("/admin")
                else:
                    ui.notify("Usuario o contraseña incorrectos.", type="negative")
                    pass_input.value = ""

            ui.button("Ingresar", on_click=intentar_login).props(
                "color=primary"
            ).classes("w-full text-lg font-bold py-3")
