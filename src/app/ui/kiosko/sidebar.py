"""Sidebar de progreso del kiosko cliente.

Muestra 5 pasos (1-5) con check, número o vacío según el estado.
"""

from nicegui import ui

from app.ui.kiosko.wizard import Paso, Sub, WizardKiosko, nombre_paso


def render_sidebar(wizard: WizardKiosko) -> None:
    orden_pasos = [Paso.SERVICIO, Paso.NOMBRE, Paso.PESO, Paso.PAGO, Paso.EXITO]
    with ui.element("div").props("id=sidebar"):
        ui.html('<div class="sidebar-title">Progreso</div>')
        for i, paso in enumerate(orden_pasos):
            if _paso_completado(wizard, paso):
                cls, num = "paso-item completado", "✓"
            elif _paso_activo(wizard, paso):
                cls, num = "paso-item activo", str(i + 1)
            else:
                cls, num = "paso-item", str(i + 1)
            ui.html(
                f'<div class="{cls}"><span class="num">{num}</span>'
                f"{nombre_paso(paso)}</div>"
            )


def _paso_completado(wizard: WizardKiosko, paso: Paso) -> bool:
    orden = [Paso.SERVICIO, Paso.NOMBRE, Paso.PESO, Paso.PAGO, Paso.EXITO]
    idx_actual = orden.index(wizard.paso)
    idx_paso = orden.index(paso)
    return idx_paso < idx_actual


def _paso_activo(wizard: WizardKiosko, paso: Paso) -> bool:
    if wizard.paso is paso:
        return True
    # Sub-estados: el paso PESO se considera activo si estamos en SEGMENTACIONES
    if paso is Paso.PESO and wizard.sub is Sub.SEGMENTACIONES:
        return True
    return False
