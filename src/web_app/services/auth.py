from nicegui import app, ui

USUARIOS = {
    "Moi": "admin123",
    "Capi": "socio123",
    "David": "admin456",
}

SUPERADMINS = {"Moi", "David"}


def esta_autenticado() -> bool:
    return app.storage.user.get("authenticated", False)


def usuario_actual() -> str:
    return app.storage.user.get("usuario", "")


def es_superadmin() -> bool:
    return usuario_actual() in SUPERADMINS


def redirigir_si_no_autenticado():
    if not esta_autenticado():
        ui.navigate.to("/admin")
        return True
    return False


def redirigir_si_no_superadmin():
    if not esta_autenticado():
        ui.navigate.to("/admin/login")
        return True
    if not es_superadmin():
        ui.navigate.to("/admin")
        return True
    return False
