"""Autenticación y autorización de administradores (vía `app.storage.user`).

USUARIOS y SUPERADMINS son catálogos cerrados del sistema (no se modifican
desde la UI). Las contraseñas se comparan en claro: este es un kiosko local
sin exposición a internet. Si en el futuro se conecta por Tailscale, hay que
migrar a hash + token.
"""

from nicegui import app, ui

USUARIOS = {
    "Moi": "admin123",
    "Capi": "socio123",
    "David": "admin456",
}

SUPERADMINS = {"Moi", "David"}


def esta_autenticado() -> bool:
    return bool(app.storage.user.get("authenticated", False))


def usuario_actual() -> str:
    return str(app.storage.user.get("usuario", "") or "")


def es_superadmin() -> bool:
    return usuario_actual() in SUPERADMINS


def login(usuario: str, contrasena: str) -> bool:
    """Devuelve True si las credenciales son válidas. Setea storage si OK."""
    usuario = (usuario or "").strip()
    contrasena = (contrasena or "").strip()
    esperado = USUARIOS.get(usuario)
    if not esperado or esperado != contrasena:
        return False
    app.storage.user["authenticated"] = True
    app.storage.user["usuario"] = usuario
    return True


def logout() -> None:
    app.storage.user.clear()


def redirigir_si_no_autenticado():
    if not esta_autenticado():
        ui.navigate.to("/admin/login")
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
