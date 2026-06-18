import asyncio
from nicegui import ui
from models import KioskoState

# ── Estado único compartido ──
state = KioskoState()

_admin_refresh_callbacks: set = set()
_admin_clients: dict = {}
_kiosko_clients: dict = {}
_kiosko_ui_ref = None


def registrar_callback_admin(cb):
    _admin_refresh_callbacks.add(cb)


def remover_callback_admin(cb):
    _admin_refresh_callbacks.discard(cb)


def notificar_admin():
    for cb in list(_admin_refresh_callbacks):
        try:
            res = cb()
            if asyncio.iscoroutine(res):
                asyncio.create_task(res)
        except Exception:
            pass


state.notificar_admin = notificar_admin


def set_kiosko_ui_ref(ref):
    global _kiosko_ui_ref
    _kiosko_ui_ref = ref


def get_kiosko_ui_ref():
    return _kiosko_ui_ref


def registrar_kiosko_client(client):
    _kiosko_clients[client.id] = client


def remover_kiosko_client(client):
    _kiosko_clients.pop(client.id, None)


def notificar_kiosko(mensaje: str = "", tipo: str = "positive"):
    if _kiosko_ui_ref:
        try:
            _kiosko_ui_ref()
        except Exception:
            pass
    if mensaje:
        for client in list(_kiosko_clients.values()):
            try:
                with client:
                    ui.notify(mensaje, type=tipo, position="top")
            except Exception:
                pass


def registrar_admin_client(client) -> str:
    _admin_clients[client.id] = client
    return client.id


def remover_admin_client(client_id: str):
    _admin_clients.pop(client_id, None)


def get_admin_client(client_id: str):
    return _admin_clients.get(client_id)
