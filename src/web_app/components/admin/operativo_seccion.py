import asyncio
from nicegui import ui
from components.shared import badge_servicio


def render_esperando_peso(v, on_aprobar, on_rechazar):
    """Tarjeta para orden pendiente de validación de peso."""
    nombre = v.get("nombre_cliente") or "Sin nombre"
    peso = v.get("peso_kg", 0) or 0
    modalidad = v.get("modalidad", "")
    es_pers = "personalizado" in modalidad
    color = "#a855f7" if es_pers else "#7e22ce"
    modalidad_badge = (
        '<span class="orden-servicio-badge" style="background:#ede9fe;color:#6d28d9;">Personalizado</span>'
        if es_pers
        else ""
    )

    with (
        ui.element("div")
        .classes("orden-card")
        .style(f"border-left:4px solid {color};")
    ):
        with ui.element("div").style("flex:1;min-width:0;"):
            ui.html(
                f'<div class="orden-numero">Orden #{v["id_transaccion"]}</div>'
                f"{badge_servicio(v['tipo_servicio'])} "
                f"{modalidad_badge} "
                f'<span class="orden-servicio-badge" style="background:#f3e8ff;color:#7e22ce;">Validar peso</span>'
            )
            ui.html(f'<div class="orden-nombre">{nombre}</div>')
            ui.html(
                f'<div class="orden-meta">{v["fecha_hora"]} · Peso registrado: <strong>{peso} kg</strong></div>'
            )
        with ui.element("div").style(
            "flex-shrink:0;display:flex;flex-direction:column;gap:8px;align-items:flex-end;"
        ):
            ui.label("✓ Aprobar").classes("btn-maquina btn-iniciar").on(
                "click",
                lambda e, venta=v: asyncio.create_task(on_aprobar(venta)),
            )
            ui.label("✕ Rechazar").classes("btn-maquina btn-pausar").on(
                "click",
                lambda e, venta=v: asyncio.create_task(on_rechazar(venta)),
            )


def render_procesando_pago(v, on_confirmar, on_cancelar):
    """Tarjeta para orden con pago pendiente (mostrador o terminal)."""
    nombre = v.get("nombre_cliente") or "Sin nombre"
    peso = v.get("peso_kg", 0) or 0
    monto = v.get("monto_pagado", 0) or 0
    modalidad = v.get("modalidad", "")
    es_pendiente_pago = v["estado"] == "Pendiente-pago"

    if "pendiente-pago" in modalidad or "mostrador" in modalidad:
        label = "Efectivo mostrador"
        color = "#16a34a"
    elif "terminal" in modalidad:
        label = "Terminal"
        color = "#f59e0b"
    else:
        label = "En pago"
        color = "#3b82f6"

    folio_input = None
    with (
        ui.element("div")
        .classes("orden-card")
        .style(f"border-left:4px solid {color};")
    ):
        with ui.element("div").style("flex:1;min-width:0;"):
            ui.html(
                f'<div class="orden-numero">Orden #{v["id_transaccion"]}</div>'
                f"{badge_servicio(v['tipo_servicio'])} "
                f'<span class="orden-servicio-badge" style="background:{color}22;color:{color};">{label}</span>'
            )
            ui.html(f'<div class="orden-nombre">{nombre}</div>')
            ui.html(
                f'<div class="orden-meta">{v["fecha_hora"]} · {peso} kg · Monto: <strong>${monto}</strong></div>'
            )
            if es_pendiente_pago:
                folio_input = (
                    ui.input("Folio de transacción (opcional)")
                    .props("outlined dense")
                    .classes("mb-2")
                )
        with ui.element("div").style(
            "flex-shrink:0;display:flex;flex-direction:column;gap:8px;align-items:flex-end;"
        ):
            if es_pendiente_pago:
                ui.label("✓ Confirmar pago").classes("btn-maquina btn-iniciar").on(
                    "click",
                    lambda e, venta=v, inp=folio_input: asyncio.create_task(
                        on_confirmar(venta, inp)
                    ),
                )
                ui.label("✕ Cancelar").classes("btn-maquina btn-pausar").on(
                    "click",
                    lambda e, venta=v: asyncio.create_task(on_cancelar(venta)),
                )
            elif v["estado"] == "Procesando-pago":
                ui.html(
                    '<div style="font-size:0.82rem;color:#64748b;">Esperando pago en kiosko...</div>'
                )
