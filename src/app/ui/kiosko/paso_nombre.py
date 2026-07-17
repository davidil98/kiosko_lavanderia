"""Paso 1: Ingreso del nombre del cliente.

Usa el teclado QWERTY reutilizable de `ui/compartido/teclado.py`. El nombre
se mantiene en el wizard (no en estado local de la página) para que
persista si el kiosko se re-renderiza.
"""

from nicegui import ui

from app.ui.compartido.teclado import TECLADO_BORRAR, render_teclado_qwerty
from app.ui.kiosko.wizard import WizardKiosko

MAX_NOMBRE = 12


def render_paso_nombre(wizard: WizardKiosko, refresh) -> None:
    with ui.element("div").props("id=nombre-panel").classes("mx-auto"):
        ui.label("Ingresa un nombre o apodo para tu orden").style(
            "font-size:1.3rem;color:#94a3b8;margin:0 0 8px;"
        )
        display = (
            ui.label(wizard.nombre or "\xa0")
            .props("id=nombre-display")
            .style("font-size:2rem;font-weight:700;color:#FFFFFF;")
        )

    def presionar(tecla: str) -> None:
        if tecla == TECLADO_BORRAR:
            nuevo = wizard.nombre[:-1]
        elif tecla == " ":
            nuevo = wizard.nombre + (" " if len(wizard.nombre) < MAX_NOMBRE else "")
        else:
            nuevo = wizard.nombre + (tecla if len(wizard.nombre) < MAX_NOMBRE else "")
        display.set_text(nuevo or "\xa0")
        refresh(wizard.with_nombre(nuevo))

    render_teclado_qwerty(presionar)

    def ir_a_pesar() -> None:
        if (wizard.nombre or "").strip() == "":
            ui.notify(
                "Por favor, ingresa al menos una letra.",
                type="warning",
                position="top",
            )
            return
        refresh(wizard.confirmar_nombre())

    ui.button("Continuar", on_click=ir_a_pesar).classes(
        "btn-confirmar-nombre max-w-lg mx-auto mt-4"
    )
