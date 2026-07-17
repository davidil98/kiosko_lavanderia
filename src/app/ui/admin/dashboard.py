"""Dashboard del panel admin (`@ui.page("/admin")`).

5 tarjetas que enlazan a:
- Operativo (aprobaciones + pagos en mostrador)
- Autoservicio (asignar máquina)
- Personalizado (kanban)
- Cortes de caja
- Superadmin (solo Moi/David)

Los contadores vienen de `repo/transacciones.contadores_pendientes()`.
"""

from nicegui import app, context, ui

from app.repo import transacciones
from app.ui.admin._componentes import (
    TarjetaDashboard,
    boton_cerrar_sesion,
    render_header,
    render_tarjeta_dashboard,
)
from app.ui.compartido.auth import (
    es_superadmin,
    esta_autenticado,
    usuario_actual,
)


@ui.page("/admin")
async def admin_dashboard():
    if not esta_autenticado():
        ui.navigate.to("/admin/login")
        return

    usuario = usuario_actual()
    super = es_superadmin()

    render_header(usuario)

    @ui.refreshable
    async def contenido() -> None:
        contadores = await transacciones.contadores_pendientes()
        pendiente_peso = contadores.get("Pendiente-peso", 0)
        pendiente_pago = contadores.get("Pendiente-pago", 0) + contadores.get(
            "Procesando-pago", 0
        )
        urgente_total = pendiente_peso + pendiente_pago
        asignar_auto = contadores.get("Pendiente", 0)
        en_proceso_auto = contadores.get("En proceso", 0)
        total_auto = asignar_auto + en_proceso_auto

        with ui.element("div").classes("dash-grid"):
            render_tarjeta_dashboard(
                TarjetaDashboard(
                    icono="/media/icons/inbox.svg",
                    titulo="Panel Operativo",
                    subtitulo=(
                        f"Aprobar pesos ({pendiente_peso}) · "
                        f"Confirmar pagos ({pendiente_pago})"
                    ),
                    badge=str(urgente_total) if urgente_total else None,
                    href="/admin/operativo",
                ),
                super,
            )
            render_tarjeta_dashboard(
                TarjetaDashboard(
                    icono="/media/icons/leaf.svg",
                    titulo="Autoservicio",
                    subtitulo=(
                        f"Asignar ({asignar_auto}) · En proceso ({en_proceso_auto})"
                    ),
                    badge=str(total_auto) if total_auto else None,
                    badge_color=("#92400e", "#fef3c7"),
                    href="/admin/autoservicio",
                ),
                super,
            )
            render_tarjeta_dashboard(
                TarjetaDashboard(
                    icono="/media/icons/shirt.svg",
                    titulo="Servicio Personalizado",
                    subtitulo="Tablero kanban de lavado, secado y doblado",
                    href="/admin/personalizado",
                ),
                super,
            )
            render_tarjeta_dashboard(
                TarjetaDashboard(
                    icono="/media/icons/ticket.svg",
                    titulo="Cortes de Caja",
                    subtitulo="Apertura, movimientos y cierre de caja",
                    href="/admin/cortes",
                ),
                super,
            )
            render_tarjeta_dashboard(
                TarjetaDashboard(
                    icono="/media/icons/gear.svg",
                    titulo="Superadmin",
                    subtitulo=(
                        "Configuración de servicios, segmentaciones y calculadora"
                    ),
                    href="/admin/superadmin",
                    superadmin_only=True,
                ),
                super,
            )

    # Header estático fuera del refreshable.
    with ui.element("div").props("id=admin-content"):
        ui.html(
            '<h2 style="font-size:1.5rem;font-weight:800;color:#1e293b;'
            'margin-bottom:6px;display:flex;align-items:center;gap:10px;">'
            '<img src="/media/icons/wave.svg" style="width:32px;height:32px;">'
            "Bienvenido</h2>"
        )
        ui.html(
            f'<p style="color:#64748b;margin-bottom:32px;">Selecciona el '
            f"módulo de trabajo, <strong>{usuario}</strong>.</p>"
        )
        with ui.element("div").props("id=dashboard-contenido"):
            await contenido()

    # El timer solo refresca las tarjetas (los contadores), no el header.
    ui.timer(5.0, contenido.refresh)
    boton_cerrar_sesion()
