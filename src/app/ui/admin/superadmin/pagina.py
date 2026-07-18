"""Página de Superadministrador (`@ui.page("/admin/superadmin")`).

6 tabs:
- Servicios y Tarifas (CRUD)
- Segmentaciones (CRUD)
- Máquinas (CRUD)
- Calculadora (simulador de precios)
- Métricas (KPIs + 5 gráficos Highcharts)
- Respaldo (crear/restaurar snapshots)

Solo accesible para Moi y David.
"""

from nicegui import ui

from app.ui.admin._componentes import boton_cerrar_sesion, render_header
from app.ui.admin.superadmin import (
    calculadora,
    maquinas,
    metricas,
    respaldo,
    segmentaciones,
    servicios,
)
from app.ui.compartido.auth import (
    redirigir_si_no_autenticado,
    redirigir_si_no_superadmin,
    usuario_actual,
)


@ui.page("/admin/superadmin")
async def admin_superadmin():
    if redirigir_si_no_autenticado() or redirigir_si_no_superadmin():
        return

    render_header(usuario_actual())

    with ui.element("div").props("id=admin-content"):
        ui.html(
            '<h2 style="font-size:1.5rem;font-weight:800;color:#1e293b;'
            'margin-bottom:6px;display:flex;align-items:center;gap:10px;">'
            '<img src="/media/icons/gear.svg" style="width:32px;height:32px;">'
            "Superadministrador</h2>"
        )
        ui.html(
            '<div style="background:#fef3c7;border-left:4px solid #f59e0b;'
            "padding:10px 14px;margin-bottom:18px;border-radius:6px;"
            'color:#92400e;font-size:0.85rem;">'
            "<strong>Importante:</strong> Los cambios en servicios, "
            "segmentaciones y máquinas requieren contraseña de bypass. "
            "El kiosko y el panel admin leen la lista en cada render, "
            "por lo que no requieren reinicio."
            "</div>"
        )

        with ui.tabs().classes("w-full") as tabs:
            tab_servicios = ui.tab("Servicios")
            tab_segmentos = ui.tab("Segmentaciones")
            tab_maquinas = ui.tab("Máquinas")
            tab_calculadora = ui.tab("Calculadora")
            tab_metricas = ui.tab("Métricas")
            tab_respaldo = ui.tab("Respaldo")

        # Cada tab es un ui.refreshable con su propio `refresh`.
        # Los handlers (servicios, maquinas, etc.) reciben ese `refresh` por
        # closure y lo invocan tras una mutación.
        @ui.refreshable
        def tab_servicios_content() -> None:
            servicios.render(tab_servicios_content.refresh)

        @ui.refreshable
        def tab_segmentos_content() -> None:
            segmentaciones.render(tab_segmentos_content.refresh)

        @ui.refreshable
        def tab_maquinas_content() -> None:
            maquinas.render(tab_maquinas_content.refresh)

        @ui.refreshable
        def tab_calculadora_content() -> None:
            calculadora.render()

        @ui.refreshable
        def tab_metricas_content() -> None:
            metricas.render()

        @ui.refreshable
        def tab_respaldo_content() -> None:
            respaldo.render(tab_respaldo_content.refresh)

        with ui.tab_panels(tabs, value=tab_servicios).classes("w-full"):
            with ui.tab_panel(tab_servicios):
                tab_servicios_content()
            with ui.tab_panel(tab_segmentos):
                tab_segmentos_content()
            with ui.tab_panel(tab_maquinas):
                tab_maquinas_content()
            with ui.tab_panel(tab_calculadora):
                tab_calculadora_content()
            with ui.tab_panel(tab_metricas):
                tab_metricas_content()
            with ui.tab_panel(tab_respaldo):
                tab_respaldo_content()

    boton_cerrar_sesion()
