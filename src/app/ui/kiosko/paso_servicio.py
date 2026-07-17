"""Paso 0: Selección de servicio.

Muestra 2 vistas según el sub-estado del wizard:
- `Sub.NINGUNO`: tarjetas de los servicios principales (Lavar / Secado).
- `Sub.SUB_LAVAR`: sub-menú con la card de Autolavado y las cards de
  Personalizado.
"""

from nicegui import ui

from app.core.servicios import (
    cargar_servicios,
    servicios_autoservicio,
    servicios_personalizado,
)
from app.ui.compartido.estilos import badge_servicio, color_servicio
from app.ui.kiosko.wizard import Sub, WizardKiosko


def _format_precio(tipo_calculo: str, precio_fijo: int, tarifa_por_kg: float) -> str:
    if tipo_calculo == "por_kg":
        return f"${int(round(tarifa_por_kg))}/kg"
    return f"${int(precio_fijo or 0)}"


def render_paso_servicio(wizard: WizardKiosko, refresh) -> None:
    if wizard.sub is Sub.SUB_LAVAR:
        _render_sub_menu_lavar(wizard, refresh)
    else:
        _render_menu_principal(wizard, refresh)


def _render_menu_principal(wizard: WizardKiosko, refresh) -> None:
    autos = servicios_autoservicio()
    ui.html('<p class="instruccion">Selecciona el servicio que deseas utilizar</p>')
    with ui.element("div").style("display:flex; gap:28px; justify-content:center;"):
        # Tarjeta "Lavar" — abre el sub-menú
        with (
            ui.element("div")
            .classes("card-servicio")
            .on("click", lambda: refresh(wizard.mostrar_sub_lavar()))
        ):
            ui.html(
                '<img src="/media/washing-clothes_dark.png" '
                'style="width:100px;height:100px;">'
            )
            ui.html(
                '<span style="font-size:1.25rem;font-weight:700;color:#e2e8f0;">Lavar</span>'
            )
            ui.html(
                '<span style="font-size:1.2rem;font-weight:800;color:#3b82f6;">Ver opciones</span>'
            )
        # Tarjetas restantes (Secado, etc.) — selección directa
        for svc in autos[1:]:
            with (
                ui.element("div")
                .classes("card-servicio")
                .on(
                    "click",
                    lambda c=svc.codigo: refresh(wizard.seleccionar_servicio(c)),
                )
            ):
                ui.html(
                    f'<img src="/media/drying_dark.png" style="width:100px;height:100px;">'
                )
                ui.html(
                    f'<span style="font-size:1.25rem;font-weight:700;color:#e2e8f0;">{svc.nombre}</span>'
                )
                ui.html(
                    f'<span style="font-size:1.9rem;font-weight:800;color:#3b82f6;">'
                    f"{_format_precio(svc.tipo_calculo, svc.precio_fijo, svc.tarifa_por_kg)}</span>"
                )


def _render_sub_menu_lavar(wizard: WizardKiosko, refresh) -> None:
    autos = servicios_autoservicio()
    pers = servicios_personalizado()
    ui.html(
        '<p class="instruccion">Selecciona el tipo de servicio de '
        "<strong>Lavado</strong></p>"
    )
    with ui.element("div").style(
        "display:flex; gap:18px; flex-wrap:wrap; justify-content:center;"
    ):
        # Tarjeta de Autolavado (primer autoservicio)
        if autos:
            auto = autos[0]
            with (
                ui.element("div")
                .classes("card-servicio")
                .on(
                    "click",
                    lambda c=auto.codigo: refresh(wizard.seleccionar_servicio(c)),
                )
            ):
                ui.html(
                    '<img src="/media/washing-clothes_dark.png" '
                    'style="width:80px;height:80px;">'
                )
                ui.html(
                    f'<span style="font-size:1.15rem;font-weight:800;color:#e2e8f0;">{auto.nombre}</span>'
                )
                ui.html(
                    f'<span style="font-size:1.7rem;font-weight:800;color:#3b82f6;">'
                    f"{_format_precio(auto.tipo_calculo, auto.precio_fijo, auto.tarifa_por_kg)}</span>"
                )
                ui.html(
                    '<span style="font-size:0.78rem;color:#64748b;">'
                    "Insertas monedas tú mismo</span>"
                )
        # Tarjetas de Personalizado
        for svc in pers:
            with (
                ui.element("div")
                .classes("card-servicio card-personalizado")
                .on(
                    "click",
                    lambda c=svc.codigo: refresh(wizard.seleccionar_servicio(c)),
                )
            ):
                ui.image(svc.icono).style("width:64px;height:64px;object-fit:contain;")
                label = svc.nombre
                ui.html(
                    f'<span style="font-size:0.95rem;font-weight:800;color:#e2e8f0;">{label}</span>'
                )
                ui.html(
                    '<span style="font-size:1.0rem;font-weight:700;color:#a78bfa;">Personalizado</span>'
                )
                ui.html(
                    f'<span style="font-size:1.5rem;font-weight:800;color:#a78bfa;">'
                    f"{_format_precio(svc.tipo_calculo, svc.precio_fijo, svc.tarifa_por_kg)}</span>"
                )
                ui.html(
                    '<span style="font-size:0.78rem;color:#94a3b8;">'
                    "Pagar en mostrador</span>"
                )

    ui.button(
        "← Volver",
        on_click=lambda: refresh(wizard.ocultar_sub_lavar()),
    ).classes("btn-confirmar-nombre max-w-xs mx-auto mt-6").style("background:#334155;")
