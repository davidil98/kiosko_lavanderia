"""Teclado QWERTY en pantalla, reutilizable por `paso_nombre` (y futuro bypass).

El teclado es **stateless**: recibe una función `on_tecla(tecla)` y delega
toda mutación al caller. La página que lo usa mantiene el texto en su
propio estado (label, wizard, etc.).
"""

from nicegui import ui

TECLADO_BORRAR = "⌫"
TECLADO_ESPACIO = "ESPACIO"

FILAS = [
    ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
    ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
    ["Z", "X", "C", "V", "B", "N", "M", TECLADO_BORRAR],
]


def render_teclado_qwerty(on_tecla) -> None:
    """Renderiza un teclado QWERTY completo. `on_tecla(tecla)` se invoca
    al presionar cada tecla (incluyendo `⌫` y ` `)."""
    with ui.column().classes(
        "w-full max-w-lg mx-auto items-center gap-1 mt-4 p-2 bg-slate-900 rounded-xl"
    ):
        for fila in FILAS:
            with ui.row().classes("w-full justify-center flex-nowrap gap-1"):
                for tecla in fila:
                    color = "bg-red-900" if tecla == TECLADO_BORRAR else "bg-slate-700"
                    ui.button(
                        tecla,
                        on_click=lambda t=tecla: on_tecla(t),
                    ).classes(
                        f"w-10 h-14 text-xl font-bold rounded-lg {color} "
                        "text-white shadow-md px-1 py-1"
                    )
        with ui.row().classes("w-full justify-center mt-1"):
            ui.button(
                TECLADO_ESPACIO,
                on_click=lambda: on_tecla(" "),
            ).classes(
                "w-3/4 h-14 text-xl font-bold bg-slate-700 text-white "
                "rounded-lg shadow-md px-0"
            )
