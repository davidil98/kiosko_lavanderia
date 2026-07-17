"""Tab Calculadora del superadmin. Permite simular el precio de un
servicio o segmentación a un peso dado."""

from nicegui import ui

from app.core.precio import calcular_precio, formatear_precio
from app.core.servicios import (
    cargar_segmentaciones,
    cargar_servicios,
)


def render() -> None:
    servicios = cargar_servicios(solo_activos=True)

    ui.html(
        '<h3 style="font-size:1.15rem;font-weight:700;color:#1e293b;'
        'margin-bottom:8px;">Simulador de precios</h3>'
        '<p style="color:#64748b;font-size:0.88rem;margin-bottom:18px;">'
        "Selecciona un servicio o segmentación y un peso para ver el "
        "precio final. Útil para resolver dudas sin abrir la caja."
        "</p>"
    )

    opciones_servicios = [(s.nombre, s) for s in servicios]

    refs: dict = {"servicio": None, "segmento": None, "peso": None, "resultado": None}

    def _calcular() -> None:
        if refs["servicio"].value is None:
            refs["resultado"].set_content(
                '<div style="color:#94a3b8;text-align:center;padding:18px;">'
                "Selecciona un servicio para empezar.</div>"
            )
            return
        item = refs["segmento"].value or refs["servicio"].value
        try:
            peso = float(refs["peso"].value or 0)
        except ValueError:
            peso = 0
        if peso <= 0 and item.tipo_calculo == "por_kg":
            refs["resultado"].set_content(
                '<div style="color:#f59e0b;text-align:center;padding:18px;">'
                "Ingresa un peso mayor a 0.</div>"
            )
            return
        precio = calcular_precio(item, peso)
        texto_precio = formatear_precio(item, peso)
        refs["resultado"].set_content(
            f'<div style="background:#1e293b;padding:24px;border-radius:8px;'
            f'text-align:center;margin-top:18px;">'
            f'<div style="color:#94a3b8;font-size:0.85rem;margin-bottom:4px;">'
            f"Precio calculado</div>"
            f'<div style="font-size:2.4rem;font-weight:800;color:#3b82f6;'
            f'margin-bottom:6px;">${precio}</div>'
            f'<div style="color:#64748b;font-size:0.78rem;">'
            f"Base: {texto_precio}"
            + (f" · Peso: {peso} kg" if item.tipo_calculo == "por_kg" else "")
            + f"</div></div>"
        )

    def on_servicio_change(e) -> None:
        srv = refs["servicio"].value
        if srv is None:
            refs["segmento"].options = {}
            refs["segmento"].value = None
            refs["segmento"].update()
        else:
            segs = cargar_segmentaciones(servicio_id=srv.id)
            refs["segmento"].options = {s.nombre: s for s in segs}
            refs["segmento"].value = None
            refs["segmento"].update()
        _calcular()

    refs["servicio"] = (
        ui.select(
            opciones_servicios,
            label="Servicio",
            value=None,
            on_change=on_servicio_change,
        )
        .props("outlined dense")
        .classes("w-full mb-2")
    )
    refs["segmento"] = (
        ui.select(
            {},
            label="Segmentación (opcional)",
            value=None,
            on_change=lambda e: _calcular(),
        )
        .props("outlined dense")
        .classes("w-full mb-2")
    )
    refs["peso"] = (
        ui.input(
            "Peso (kg)",
            value="0",
            on_change=lambda e: _calcular(),
        )
        .props("type=number min=0 step=0.1 outlined dense")
        .classes("w-full mb-2")
    )
    refs["resultado"] = ui.html(
        '<div style="color:#94a3b8;text-align:center;padding:18px;">'
        "Selecciona un servicio para empezar.</div>"
    )
