"""Tab Métricas del superadmin. KPIs + 5 gráficos Highcharts.

Rangos disponibles: todo, 7d, 30d, 90d, 1y.
Solo se consideran órdenes con estado 'Completado' o 'En proceso'
(según `core/reportes.parsear_rango` + `obtener_completadas_entre`).
"""

import json

from nicegui import ui
from nicegui_highcharts import highchart

from app.core import reportes


RANGOS = [
    ("todo", "Todo"),
    ("7d", "Últimos 7 días"),
    ("30d", "Últimos 30 días"),
    ("90d", "Últimos 90 días"),
    ("1y", "Último año"),
]


def render() -> None:
    rango_ref: dict = {"value": "30d"}

    ui.html(
        '<h3 style="font-size:1.15rem;font-weight:700;color:#1e293b;'
        'margin-bottom:8px;">Métricas del kiosko</h3>'
        '<p style="color:#64748b;font-size:0.88rem;margin-bottom:18px;">'
        "Resumen de órdenes completadas o en proceso en el rango seleccionado. "
        "Los datos vienen de <code>core/reportes.py</code>."
        "</p>"
    )

    def on_rango_change(e) -> None:
        contenido.refresh()

    ui.select(
        dict(RANGOS),
        value="30d",
        label="Rango",
        on_change=on_rango_change,
    ).props("outlined dense").classes("w-full max-w-sm mb-4").bind_value(
        rango_ref, "value"
    )

    @ui.refreshable
    async def contenido() -> None:
        rango = rango_ref["value"]
        k = await reportes.kpis(rango)
        await _render_kpis(k)
        await _render_charts(rango)


async def _render_kpis(k: dict) -> None:
    with ui.element("div").style(
        "display:grid;grid-template-columns:repeat(4, 1fr);gap:12px;margin-bottom:18px;"
    ):
        for label, valor, color in [
            ("Órdenes totales", str(k["ordenes_totales"]), "#1e40af"),
            ("Recaudado", f"${k['recaudado']}", "#16a34a"),
            ("Kilos lavados", f"{k['kilos_lavados']} kg", "#a855f7"),
            ("Kg/orden promedio", f"{k['kg_por_orden']} kg", "#f59e0b"),
        ]:
            with ui.element("div").style(
                "background:white;padding:14px;border-radius:6px;"
                f"border-left:3px solid {color};"
            ):
                ui.html(
                    f'<div style="font-size:0.7rem;color:#94a3b8;'
                    f'text-transform:uppercase;letter-spacing:0.5px;">{label}</div>'
                    f'<div style="font-size:1.4rem;font-weight:800;color:{color};">'
                    f"{valor}</div>"
                )


async def _render_charts(rango: str) -> None:
    uso = await reportes.uso_por_maquina(rango)
    horas = await reportes.horas_pico(rango)
    dias = await reportes.dias_pico(rango)
    promedio = await reportes.consumo_promedio_por_servicio(rango)
    tarjeta = await reportes.tasa_efectivo_vs_tarjeta(rango)

    # 1) Uso por máquina (columnas)
    if uso:
        highchart.options_dict(
            chart={"type": "column"},
            title={"text": "Uso por máquina"},
            xAxis={"categories": [u["maquina"] for u in uso], "title": {"text": ""}},
            yAxis={"title": {"text": "Ciclos"}, "min": 0},
            series=[{"name": "Ciclos", "data": [u["ciclos"] for u in uso]}],
        ).classes("w-full mb-4").style("height:300px;")

    # 2) Horas pico (línea)
    if horas and any(horas):
        highchart.options_dict(
            chart={"type": "line"},
            title={"text": "Horas pico (24h)"},
            xAxis={"categories": [f"{h}h" for h in range(24)], "title": {"text": ""}},
            yAxis={"title": {"text": "Órdenes"}, "min": 0},
            series=[{"name": "Órdenes", "data": horas}],
        ).classes("w-full mb-4").style("height:300px;")

    # 3) Días pico (columnas)
    if dias and any(dias):
        nombres_dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        highchart.options_dict(
            chart={"type": "column"},
            title={"text": "Días pico (semana)"},
            xAxis={"categories": nombres_dias, "title": {"text": ""}},
            yAxis={"title": {"text": "Órdenes"}, "min": 0},
            series=[{"name": "Órdenes", "data": dias}],
        ).classes("w-full mb-4").style("height:300px;")

    # 4) Consumo promedio por servicio (barras horizontales)
    if promedio:
        highchart.options_dict(
            chart={"type": "bar"},
            title={"text": "Consumo promedio por servicio (kg)"},
            xAxis={
                "categories": [p["servicio"] for p in promedio],
                "title": {"text": ""},
            },
            yAxis={"title": {"text": "Kg promedio"}},
            series=[
                {
                    "name": "Kg promedio",
                    "data": [p["kg_promedio"] for p in promedio],
                }
            ],
        ).classes("w-full mb-4").style("height:300px;")

    # 5) Tasa efectivo vs tarjeta (columnas agrupadas)
    if tarjeta:
        highchart.options_dict(
            chart={"type": "column"},
            title={"text": "Efectivo vs Tarjeta (mensual)"},
            xAxis={"categories": [t["mes"] for t in tarjeta], "title": {"text": ""}},
            yAxis={"title": {"text": "Monto ($)"}, "min": 0},
            series=[
                {"name": "Efectivo", "data": [t["efectivo"] for t in tarjeta]},
                {"name": "Tarjeta", "data": [t["tarjeta"] for t in tarjeta]},
            ],
        ).classes("w-full mb-4").style("height:300px;")
