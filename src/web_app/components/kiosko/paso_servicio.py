from nicegui import ui
from models import SERVICIOS_AUTO, SERVICIOS_PERSONALIZADO
from services.notifications import state


def render_paso_servicio(kiosko_ui_ref):
    if state.mostrando_sub_lavar:
        _render_sub_menu_lavar(kiosko_ui_ref)
    else:
        _render_menu_principal(kiosko_ui_ref)


def _render_sub_menu_lavar(kiosko_ui_ref):
    ui.html(
        '<p class="instruccion">Selecciona el tipo de servicio de <strong>Lavado</strong></p>'
    )
    with ui.element("div").style(
        "display:flex; gap:18px; flex-wrap:wrap; justify-content:center;"
    ):
        auto = SERVICIOS_AUTO[0]
        with (
            ui.element("div")
            .classes("card-servicio")
            .on(
                "click",
                lambda: state.seleccionar_servicio("Autolavado"),
            )
        ):
            ui.html(
                '<img src="/media/washing-clothes_dark.png" style="width:80px;height:80px;">'
            )
            ui.html(
                '<span style="font-size:1.15rem;font-weight:800;color:#e2e8f0;">Autolavado</span>'
            )
            ui.html(
                f'<span style="font-size:1.7rem;font-weight:800;color:#3b82f6;">${auto.precio}</span>'
            )
            ui.html(
                '<span style="font-size:0.78rem;color:#64748b;">Insertas monedas tú mismo</span>'
            )

        for svc in SERVICIOS_PERSONALIZADO:
            with (
                ui.element("div")
                .classes("card-servicio card-personalizado")
                .on(
                    "click",
                    lambda s=svc.nombre: (state.seleccionar_servicio(s)),
                )
            ):
                ui.image(svc.icono).style(
                    "width:64px;height:64px;object-fit:contain;"
                )
                ui.html(
                    f'<span style="font-size:0.95rem;font-weight:800;color:#e2e8f0;">{svc.subtipo.capitalize()}</span>'
                )
                ui.html(
                    '<span style="font-size:1.0rem;font-weight:700;color:#a78bfa;">Personalizado</span>'
                )
                ui.html(
                    f'<span style="font-size:1.5rem;font-weight:800;color:#a78bfa;">${svc.precio}</span>'
                )
                ui.html(
                    '<span style="font-size:0.78rem;color:#94a3b8;">Pagar en mostrador</span>'
                )

    ui.button(
        "\u2190 Volver",
        on_click=lambda: (
            setattr(state, "mostrando_sub_lavar", False),
            kiosko_ui_ref(),
        ),
    ).classes("btn-confirmar-nombre max-w-xs mx-auto mt-6").style(
        "background:#334155;"
    )


def _render_menu_principal(kiosko_ui_ref):
    ui.html(
        '<p class="instruccion">Selecciona el servicio que deseas utilizar</p>'
    )
    with ui.element("div").style(
        "display:flex; gap:28px; justify-content:center;"
    ):
        with (
            ui.element("div")
            .classes("card-servicio")
            .on(
                "click",
                lambda: (
                    setattr(state, "mostrando_sub_lavar", True),
                    kiosko_ui_ref(),
                ),
            )
        ):
            ui.html(
                '<img src="/media/washing-clothes_dark.png" style="width:100px;height:100px;">'
            )
            ui.html(
                '<span style="font-size:1.25rem;font-weight:700;color:#e2e8f0;">Lavar</span>'
            )
            ui.html(
                '<span style="font-size:1.2rem;font-weight:800;color:#3b82f6;">Ver opciones</span>'
            )

        secar = SERVICIOS_AUTO[1]
        with (
            ui.element("div")
            .classes("card-servicio")
            .on(
                "click",
                lambda: state.seleccionar_servicio("Secado"),
            )
        ):
            ui.html(
                '<img src="/media/drying_dark.png" style="width:100px;height:100px;">'
            )
            ui.html(
                f'<span style="font-size:1.25rem;font-weight:700;color:#e2e8f0;">{secar.nombre}</span>'
            )
            ui.html(
                f'<span style="font-size:1.9rem;font-weight:800;color:#3b82f6;">${secar.precio}</span>'
            )
