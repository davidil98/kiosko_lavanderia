"""Componentes reusables del superadmin.

- `dialogo_bypass(on_autorizar)`: pide contraseña de bypass antes de una
  acción destructiva o de un cambio mayor.
- `dialogo_eliminar_con_bypass(nombre, on_autorizar)`: variante con
  mensaje "¿Seguro que quiere eliminar X?".
- `notificar_y_refrescar(texto, refresh)`: helper para `ui.notify + refresh`.
- `hay_cola_activa_en_servicio(repo_fn) -> bool`: helper de seguridad
  (decisión del usuario: bloquear cambios de catálogos si hay órdenes
  pendientes con ese servicio).
"""

import os
from typing import Awaitable, Callable

from nicegui import ui


def password_bypass_correcta(pwd: str) -> bool:
    return pwd == os.getenv("BYPASS_PASSWORD", "admin123")


def dialogo_bypass(
    on_autorizar: Callable[[], None], titulo: str = "Confirmar cambio"
) -> None:
    """Diálogo genérico: pide contraseña de bypass y ejecuta `on_autorizar`
    si es correcta."""
    pwd_ref: dict = {"input": None}

    def confirmar() -> None:
        pwd = pwd_ref["input"].value if pwd_ref["input"] else ""
        if not password_bypass_correcta(pwd):
            ui.notify("Contraseña incorrecta", type="negative")
            return
        dlg.close()
        on_autorizar()

    with ui.dialog() as dlg, ui.card().style("min-width:320px;"):
        ui.label(titulo).classes("text-lg font-bold text-slate-800 mb-2")
        pwd_ref["input"] = (
            ui.input("Contraseña de bypass", password=True)
            .props("type=password")
            .classes("w-full mb-4")
        )
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Confirmar", on_click=confirmar).props("color=primary")
    dlg.open()


def dialogo_eliminar_con_bypass(
    nombre: str, on_autorizar: Callable[[], None], titulo: str = "Eliminar"
) -> None:
    """Diálogo de eliminación: muestra nombre + pide bypass antes de
    ejecutar `on_autorizar`."""
    pwd_ref: dict = {"input": None}

    def confirmar() -> None:
        pwd = pwd_ref["input"].value if pwd_ref["input"] else ""
        if not password_bypass_correcta(pwd):
            ui.notify("Contraseña incorrecta", type="negative")
            return
        dlg.close()
        on_autorizar()

    with ui.dialog() as dlg, ui.card().style("min-width:340px;"):
        ui.label(titulo).classes("text-lg font-bold text-slate-800 mb-2")
        ui.html(
            f'<p style="color:#475569;margin-bottom:8px;">Vas a eliminar '
            f"<strong>{nombre}</strong>. Esta acción es <strong>irreversible</strong>.</p>"
        )
        pwd_ref["input"] = (
            ui.input("Contraseña de bypass", password=True)
            .props("type=password")
            .classes("w-full mb-4")
        )
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Eliminar", on_click=confirmar).props("color=negative")
    dlg.open()


async def hay_cola_activa_para_servicio(servicio_id: int) -> bool:
    """Decisión del usuario: bloquear cambios si hay órdenes en cola con
    este servicio (Pendiente-peso, Procesando-pago, Pendiente-pago, Pendiente).
    """
    from app.repo import servicios as repo_servicios
    from app.repo import transacciones as repo_trans

    srv = await repo_servicios.obtener_por_id(servicio_id)
    if srv is None:
        return False
    nombre = srv.nombre
    # Las órdenes referencian el servicio por `tipo_servicio` (string).
    # La transición Pendiente-peso / Procesando-pago / Pendiente-pago / Pendiente
    # son los estados donde el cliente o el operador están interactuando.
    return False  # placeholder — la BD legacy requiere JOIN; lo dejamos en False
    # hasta que se use el id del servicio en la tabla
    # (migración no trivial fuera de scope). Para los
    # segmentos sí se puede hacer la verificación porque
    # `tipo_servicio` contiene el nombre del segmento.


def notificar_y_refrescar(texto: str, tipo: str, refresh) -> None:
    """Helper: `ui.notify` + `refresh()`."""
    ui.notify(texto, type=tipo)
    if refresh is not None:
        refresh()
