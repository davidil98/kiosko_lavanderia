from nicegui import ui
from services.notifications import state


def render_paso_nombre(kiosko_ui_ref):
    state.nombre_cliente = ""
    with ui.element("div").props("id=nombre-panel").classes("mx-auto"):
        ui.label("Ingresa un nombre o apodo para tu orden").style(
            "font-size:1.3rem;color:#94a3b8;margin:0 0 8px;"
        )
        display_nombre = (
            ui.label("\xa0")
            .props("id=nombre-display")
            .style("font-size:2rem;font-weight:700;color:#FFFFFF;")
        )

    def presionar_tecla(tecla):
        if tecla == "\u232b":
            state.nombre_cliente = state.nombre_cliente[:-1]
        else:
            if len(state.nombre_cliente) < 12:
                state.nombre_cliente += tecla
        display_nombre.set_text(
            state.nombre_cliente if state.nombre_cliente else "\xa0"
        )

    filas = [
        ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
        ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
        ["Z", "X", "C", "V", "B", "N", "M", "\u232b"],
    ]
    with ui.column().classes(
        "w-full max-w-lg mx-auto items-center gap-1 mt-4 p-2 bg-slate-900 rounded-xl"
    ):
        for fila in filas:
            with ui.row().classes("w-full justify-center flex-nowrap gap-1"):
                for tecla in fila:
                    color_btn = "bg-red-900" if tecla == "\u232b" else "bg-slate-700"
                    ui.button(
                        tecla,
                        on_click=lambda t=tecla: presionar_tecla(t),
                    ).classes(
                        f"w-10 h-14 text-xl font-bold rounded-lg {color_btn} text-white shadow-md px-1 py-1"
                    )
        with ui.row().classes("w-full justify-center mt-1"):
            ui.button(
                "ESPACIO", on_click=lambda: presionar_tecla(" ")
            ).classes(
                "w-3/4 h-14 text-xl font-bold bg-slate-700 text-white rounded-lg shadow-md px-0"
            )

    def ir_a_pesar():
        if state.nombre_cliente.strip() == "":
            ui.notify(
                "Por favor, ingresa al menos una letra.",
                type="warning",
                position="top",
            )
            return
        state.paso_actual = 2
        kiosko_ui_ref()

    ui.button("Continuar", on_click=ir_a_pesar).classes(
        "btn-confirmar-nombre max-w-lg mx-auto mt-4"
    )
