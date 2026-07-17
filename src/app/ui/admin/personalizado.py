"""Panel personalizado (`@ui.page("/admin/personalizado")`).

Kanban de 3 columnas (Recibido / Alistando / Listo para Entrega) para
las órdenes con modalidad `personalizado`.
"""

from datetime import datetime

from nicegui import ui

from app.core.estados import EtapaKanban
from app.eventos.bus import bus
from app.eventos.tipos import EventoDominio, TIPO_ORDEN_CANCELADA
from app.repo import transacciones
from app.ui.admin._componentes import (
    AccionTarjeta,
    boton_cerrar_sesion,
    render_header,
    tarjeta_orden,
)
from app.ui.compartido.auth import redirigir_si_no_autenticado, usuario_actual

ETAPAS = [
    (EtapaKanban.RECIBIDO, "inbox", "Recibido"),
    (EtapaKanban.ALISTANDO, "gear", "Alistando"),
    (EtapaKanban.LISTO_ENTREGA, "check", "Listo para Entrega"),
]


@ui.page("/admin/personalizado")
async def admin_personalizado():
    if redirigir_si_no_autenticado():
        return
    usuario = usuario_actual()
    render_header(usuario)

    @ui.refreshable
    async def contenido() -> None:
        ordenes = await transacciones.listar_personalizadas()
        por_etapa: dict[EtapaKanban, list] = {e: [] for e, _, _ in ETAPAS}
        # default → RECIBIDO si la fila no tiene etapa asignada
        for o in ordenes:
            try:
                etapa = (
                    EtapaKanban(o.get("etapa_kanban"))
                    if o.get("etapa_kanban")
                    else EtapaKanban.RECIBIDO
                )
            except ValueError:
                etapa = EtapaKanban.RECIBIDO
            por_etapa.setdefault(etapa, []).append(o)

        with ui.element("div").props("id=admin-content"):
            ui.html(
                '<h2 style="font-size:1.5rem;font-weight:800;color:#1e293b;'
                'margin-bottom:6px;display:flex;align-items:center;gap:10px;">'
                '<img src="/media/icons/shirt.svg" style="width:32px;height:32px;">'
                "Servicio Personalizado</h2>"
            )
            ui.html(
                f'<p style="color:#64748b;margin-bottom:24px;">'
                f"Mueve las órdenes por las 3 etapas. Operador: <strong>{usuario}</strong>.</p>"
            )

            with ui.element("div").style(
                "display:grid;grid-template-columns:repeat(3, 1fr);gap:18px;"
            ):
                for etapa, icono, titulo in ETAPAS:
                    with ui.element("div").classes("kanban-col"):
                        ui.html(
                            f'<div class="kanban-col-header">'
                            f'<img src="/media/icons/{icono}.svg" '
                            f'style="width:20px;height:20px;vertical-align:middle;margin-right:6px;">'
                            f"{titulo}"
                            f'<span class="badge" style="margin-left:auto;">{len(por_etapa[etapa])}</span>'
                            f"</div>"
                        )
                        for o in por_etapa[etapa]:
                            _render_kanban_card(o)

    await contenido()
    ui.timer(3.0, contenido.refresh)

    boton_cerrar_sesion()


def _render_kanban_card(o: dict) -> None:
    """Una tarjeta del kanban con su acción 'avanzar etapa'."""
    etapa_actual = o.get("etapa_kanban")
    try:
        etapa = EtapaKanban(etapa_actual) if etapa_actual else EtapaKanban.RECIBIDO
    except ValueError:
        etapa = EtapaKanban.RECIBIDO

    # Determinar la siguiente etapa
    idx = next((i for i, (e, _, _) in enumerate(ETAPAS) if e is etapa), 0)
    if idx < len(ETAPAS) - 1:
        siguiente = ETAPAS[idx + 1][0]
        label_accion = f"→ {ETAPAS[idx + 1][2]}"
        color_accion = "primary"
        handler = _hacer_actualizar_etapa(siguiente)
    else:
        # Última etapa: marcar como entregado (cancela la orden)
        label_accion = "✓ Entregar"
        color_accion = "positive"
        handler = _hacer_cancelar()

    tarjeta_orden(
        o,
        [
            AccionTarjeta(label=label_accion, color=color_accion, handler=handler),
        ],
    )


def _hacer_actualizar_etapa(siguiente: EtapaKanban):
    """Crea un handler async que avanza la orden a la etapa siguiente."""

    async def handler(o: dict) -> None:
        oid = o["id_transaccion"]
        await transacciones.actualizar_etapa_kanban(oid, siguiente.value)
        ui.notify(f"Etapa actualizada a {siguiente.value}", type="positive")

    return handler


def _hacer_cancelar():
    async def handler(o: dict) -> None:
        oid = o["id_transaccion"]
        await transacciones.actualizar_etapa_kanban(oid, "Entregado")
        bus.publish(
            EventoDominio(
                tipo=TIPO_ORDEN_CANCELADA,
                orden_id=oid,
                extra={"motivo": "entregado"},
                cuando=datetime.now(),
            )
        )
        ui.notify(f"Orden #{oid} entregada", type="positive")

    return handler
