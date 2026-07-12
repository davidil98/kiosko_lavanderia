from nicegui import ui
from models import (
    cargar_servicios,
    SERVICIOS_AUTO as _SERVICIOS_AUTO_LEGACY,
    SERVICIOS_PERSONALIZADO as _SERVICIOS_PERSONALIZADO_LEGACY,
    calcular_precio,
)
from services.notifications import state


def _auto():
    return _SERVICIOS_AUTO_LEGACY()


def _pers():
    return _SERVICIOS_PERSONALIZADO_LEGACY()


def render_paso_servicio(kiosko_ui_ref):
    if state.mostrando_sub_lavar:
        _render_sub_menu_lavar(kiosko_ui_ref)
    else:
        _render_menu_principal(kiosko_ui_ref)


def _format_precio(svc) -> str:
    if svc.tipo_calculo == "por_kg":
        return f"${int(round(svc.tarifa_por_kg))}/kg"
    return f"${int(svc.precio_fijo or svc.precio)}"


def _render_sub_menu_lavar(kiosko_ui_ref):
    autos = _auto()
    pers = _pers()
    ui.html(
        '<p class="instruccion">Selecciona el tipo de servicio de <strong>Lavado</strong></p>'
    )
    with ui.element("div").style(
        "display:flex; gap:18px; flex-wrap:wrap; justify-content:center;"
    ):
        # Tarjeta de Autoservicio (Autolavado)
        if autos:
            auto = autos[0]
            with (
                ui.element("div")
                .classes("card-servicio")
                .on(
                    "click",
                    lambda c=auto.codigo: state.seleccionar_servicio(c),
                )
            ):
                ui.html(
                    '<img src="/media/washing-clothes_dark.png" style="width:80px;height:80px;">'
                )
                ui.html(
                    f'<span style="font-size:1.15rem;font-weight:800;color:#e2e8f0;">{auto.nombre}</span>'
                )
                ui.html(
                    f'<span style="font-size:1.7rem;font-weight:800;color:#3b82f6;">{_format_precio(auto)}</span>'
                )
                ui.html(
                    '<span style="font-size:0.78rem;color:#64748b;">Insertas monedas tú mismo</span>'
                )

        # Tarjetas de Personalizado
        for svc in pers:
            with (
                ui.element("div")
                .classes("card-servicio card-personalizado")
                .on(
                    "click",
                    lambda c=svc.codigo: state.seleccionar_servicio(c),
                )
            ):
                ui.image(svc.icono).style("width:64px;height:64px;object-fit:contain;")
                label = svc.subtipo.capitalize() if svc.subtipo else svc.nombre
                ui.html(
                    f'<span style="font-size:0.95rem;font-weight:800;color:#e2e8f0;">{label}</span>'
                )
                ui.html(
                    '<span style="font-size:1.0rem;font-weight:700;color:#a78bfa;">Personalizado</span>'
                )
                ui.html(
                    f'<span style="font-size:1.5rem;font-weight:800;color:#a78bfa;">{_format_precio(svc)}</span>'
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
    ).classes("btn-confirmar-nombre max-w-xs mx-auto mt-6").style("background:#334155;")


def _render_menu_principal(kiosko_ui_ref):
    autos = _auto()
    ui.html('<p class="instruccion">Selecciona el servicio que deseas utilizar</p>')
    with ui.element("div").style("display:flex; gap:28px; justify-content:center;"):
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

        # Tarjeta de Secado (segundo autoservicio, si existe)
        for svc in autos[1:]:
            with (
                ui.element("div")
                .classes("card-servicio")
                .on(
                    "click",
                    lambda c=svc.codigo: state.seleccionar_servicio(c),
                )
            ):
                ui.html(
                    f'<img src="/media/drying_dark.png" style="width:100px;height:100px;">'
                )
                ui.html(
                    f'<span style="font-size:1.25rem;font-weight:700;color:#e2e8f0;">{svc.nombre}</span>'
                )
                ui.html(
                    f'<span style="font-size:1.9rem;font-weight:800;color:#3b82f6;">{_format_precio(svc)}</span>'
                )
