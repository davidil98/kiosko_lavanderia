from nicegui import ui
from models import PASOS
from services.notifications import state


def render_sidebar():
    with ui.element("div").props("id=sidebar"):
        ui.html('<div class="sidebar-title">Progreso</div>')
        for i, paso in enumerate(PASOS):
            if i < state.paso_actual:
                cls, num = "paso-item completado", "✓"
            elif i == state.paso_actual:
                cls, num = "paso-item activo", str(i + 1)
            else:
                cls, num = "paso-item", str(i + 1)
            ui.html(
                f'<div class="{cls}"><span class="num">{num}</span>{paso}</div>'
            )
