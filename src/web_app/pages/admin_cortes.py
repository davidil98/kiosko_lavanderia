import os
import asyncio
from datetime import datetime
from nicegui import ui
import nicegui as _ng

import database_web
from services.auth import (
    redirigir_si_no_autenticado,
    usuario_actual,
    es_superadmin,
)
from components.admin.header import render_admin_header


@ui.page("/admin/cortes")
async def admin_cortes():
    if redirigir_si_no_autenticado():
        return

    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
    )
    ui.add_head_html('<link rel="stylesheet" href="/static/admin.css">')

    page_client = _ng.context.client

    render_admin_header(
        icon_path="/media/icons/ticket.svg",
        title="Cortes de Caja",
    )

    with ui.element("div").props("id=admin-content"):
        await _render_pagina(page_client)


async def _render_pagina(page_client):
    @ui.refreshable
    async def vista_completa():
        corte = await database_web.obtener_corte_activo_async()
        if corte is None:
            _render_sin_caja(page_client)
        else:
            _render_caja_abierta(corte, page_client)
        ui.html('<div style="height:24px;"></div>')
        await _render_historial()

    await vista_completa()


def _render_sin_caja(page_client):
    ui.html(
        '<div style="background:#f1f5f9;border-radius:8px;padding:24px;'
        'text-align:center;margin-bottom:18px;">'
        '<img src="/media/icons/ticket.svg" style="width:48px;height:48px;opacity:0.5;margin-bottom:8px;">'
        '<div style="font-size:1.05rem;font-weight:700;color:#475569;margin-bottom:4px;">'
        "No hay caja abierta"
        "</div>"
        '<div style="font-size:0.85rem;color:#94a3b8;">'
        "Abre la caja al inicio del día para empezar a registrar movimientos."
        "</div>"
        "</div>"
    )
    if es_superadmin():
        with ui.row().classes("w-full justify-center"):
            ui.button(
                "🔓 Abrir caja",
                on_click=lambda: _abrir_dialog_abrir(page_client),
            ).props("color=primary")
    else:
        ui.html(
            '<div style="text-align:center;color:#94a3b8;font-size:0.85rem;">'
            "Solo el superadmin puede abrir la caja."
            "</div>"
        )


async def _render_caja_abierta(corte, page_client):
    """Caja abierta: resumen, movimientos, botón de cerrar."""

    @ui.refreshable
    async def resumen():
        corte_actual = await database_web.obtener_corte_activo_async()
        if not corte_actual:
            return
        movs = await database_web.listar_movimientos_async(corte_actual["id"])
        ingresos = sum(m["monto"] for m in movs if m["tipo"] == "ingreso")
        egresos = sum(m["monto"] for m in movs if m["tipo"] == "egreso")
        saldo_esperado = corte_actual["saldo_inicial"] + ingresos - egresos
        with (
            ui.element("div")
            .classes("orden-card")
            .style(
                "flex-direction:column;background:#f0fdf4;border-left:6px solid #16a34a;"
            )
        ):
            ui.html(
                f'<div style="font-size:0.78rem;font-weight:700;color:#16a34a;text-transform:uppercase;">'
                "Caja abierta"
                f"</div>"
                f'<div style="font-size:0.85rem;color:#475569;margin-top:4px;">'
                f"Abierta por <strong>{corte_actual['usuario_apertura']}</strong> "
                f"a las {corte_actual['hora_apertura']}"
                f"</div>"
            )
            with ui.element("div").style(
                "display:grid;grid-template-columns:repeat(4, 1fr);gap:12px;margin-top:14px;"
            ):
                _kpi_box(
                    "Saldo inicial", f"${corte_actual['saldo_inicial']}", "#3b82f6"
                )
                _kpi_box("Ingresos", f"${ingresos}", "#16a34a")
                _kpi_box("Egresos", f"${egresos}", "#ef4444")
                _kpi_box(
                    "Esperado",
                    f"${saldo_esperado}",
                    "#7c3aed" if saldo_esperado >= 0 else "#dc2626",
                )

    with ui.element("div").classes("orden-card").style("flex-direction:column;"):
        ui.html(
            '<div class="orden-numero" style="margin-bottom:6px;">Resumen de caja</div>'
        )
        await resumen()
        with ui.row().classes("w-full gap-2 mt-3 justify-end"):
            ui.button(
                "🔄 Refrescar",
                on_click=lambda: (resumen.refresh(), _render_tabla_movimientos_inner()),
            )
            if es_superadmin():
                ui.button(
                    "🔒 Cerrar caja",
                    on_click=lambda: _abrir_dialog_cerrar(corte, page_client),
                ).props("color=negative")

    ui.html('<div style="height:16px;"></div>')

    # Tabla de movimientos + botón de registrar
    @ui.refreshable
    async def tabla_movimientos():
        movs = await database_web.listar_movimientos_async(corte["id"])
        with ui.element("div").classes("orden-card").style("flex-direction:column;"):
            ui.html(
                '<div class="orden-numero" style="margin-bottom:8px;">'
                f"Movimientos ({len(movs)})"
                "</div>"
            )
            if not movs:
                ui.html(
                    '<div style="color:#94a3b8;font-size:0.85rem;padding:8px 0;">'
                    "Sin movimientos registrados. Pulsa '➕ Registrar movimiento' "
                    "para añadir el primero (ej. 'Cambio a cliente')."
                    "</div>"
                )
                return
            for m in movs:
                _render_fila_movimiento(m)

    with ui.element("div").classes("orden-card").style("flex-direction:column;"):
        with ui.row().classes("w-full justify-between items-center mb-2"):
            ui.html('<div class="orden-numero">Movimientos del turno</div>')
            ui.button(
                "➕ Registrar movimiento",
                on_click=lambda: _abrir_dialog_movimiento(corte, page_client),
            ).props("color=primary size=sm")
        await tabla_movimientos()

    def _render_tabla_movimientos_inner():
        tabla_movimientos.refresh()

    _render_tabla_movimientos_inner()


def _kpi_box(label, valor, color):
    ui.html(
        f'<div style="background:#fff;border:1px solid #e2e8f0;'
        f'border-radius:6px;padding:10px;text-align:center;">'
        f'<div style="font-size:0.7rem;color:#64748b;font-weight:600;'
        f'text-transform:uppercase;">{label}</div>'
        f'<div style="font-size:1.3rem;font-weight:800;color:{color};'
        f'margin-top:4px;">{valor}</div>'
        f"</div>"
    )


def _render_fila_movimiento(m):
    tipo_color = "#16a34a" if m["tipo"] == "ingreso" else "#ef4444"
    tipo_label = "Ingreso" if m["tipo"] == "ingreso" else "Egreso"
    tipo_signo = "+" if m["tipo"] == "ingreso" else "−"
    auto_badge = (
        ' <span style="background:#e0e7ff;color:#3730a3;'
        "font-size:0.65rem;padding:1px 6px;border-radius:4px;"
        'font-weight:600;margin-left:4px;">AUTO</span>'
        if m["auto"]
        else ""
    )
    notas_html = (
        f'<div style="font-size:0.72rem;color:#94a3b8;margin-top:2px;">'
        f"{m['notas']}</div>"
        if m["notas"]
        else ""
    )
    with ui.element("div").style(
        "padding:8px 0;border-bottom:1px solid #f1f5f9;"
        "display:flex;align-items:center;gap:12px;"
    ):
        ui.html(
            f'<div style="min-width:60px;font-size:0.75rem;color:#64748b;">'
            f"{m['fecha_hora'].split(' ')[1] if ' ' in m['fecha_hora'] else m['fecha_hora'][-8:]}"
            f"</div>"
            f'<div style="min-width:80px;">'
            f'<span style="background:{tipo_color}22;color:{tipo_color};'
            f"padding:2px 8px;border-radius:4px;font-size:0.7rem;"
            f'font-weight:700;">{tipo_label}</span>'
            f"</div>"
            f'<div style="min-width:90px;font-size:1rem;font-weight:800;'
            f'color:{tipo_color};text-align:right;">'
            f"{tipo_signo}${m['monto']}"
            f"</div>"
            f'<div style="flex:1;min-width:0;">'
            f'<div style="font-size:0.88rem;color:#1e293b;font-weight:600;">'
            f"{m['concepto']}{auto_badge}"
            f"</div>"
            f'<div style="font-size:0.72rem;color:#64748b;">por {m["usuario"]}</div>'
            f"{notas_html}"
            f"</div>"
        )


# ── Diálogos ────────────────────────────────────────────────────────────────


def _abrir_dialog_abrir(page_client):
    if not es_superadmin():
        with page_client:
            ui.notify(
                "Solo el superadmin puede abrir la caja.",
                type="negative",
                position="top",
            )
        return

    with ui.dialog() as dlg, ui.card().style("min-width:440px;"):
        ui.label("Abrir caja").classes("text-lg font-bold text-slate-800 mb-2")
        ui.html(
            '<p style="color:#475569;font-size:0.85rem;margin-bottom:10px;">'
            "Ingresa el efectivo que hay en la caja al iniciar el día. "
            "El sistema lo registrará como saldo inicial."
            "</p>"
        )
        saldo_in = (
            ui.input("Saldo inicial ($)", value="0")
            .props("type=number min=0")
            .classes("w-full")
        )
        pwd_in = (
            ui.input("Contraseña de bypass")
            .props("type=password")
            .classes("w-full mt-2")
        )

        async def _guardar():
            if pwd_in.value != os.getenv("BYPASS_PASSWORD", "admin123"):
                with page_client:
                    ui.notify(
                        "Contraseña incorrecta.",
                        type="negative",
                        position="top",
                    )
                return
            try:
                saldo = int(saldo_in.value or 0)
            except (TypeError, ValueError):
                with page_client:
                    ui.notify(
                        "Saldo inválido.",
                        type="negative",
                        position="top",
                    )
                return
            fecha = datetime.now().strftime("%Y-%m-%d")
            result = await database_web.abrir_corte_async(
                fecha, usuario_actual(), saldo
            )
            if not result["ok"]:
                with page_client:
                    ui.notify(
                        result.get("error", "Error abriendo caja."),
                        type="negative",
                        position="top",
                    )
                return
            with page_client:
                ui.notify(
                    f"Caja abierta con ${saldo} inicial.",
                    type="positive",
                    position="top",
                )
            dlg.close()
            ui.navigate.reload()

        with ui.row().classes("w-full justify-end mt-3 gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Abrir", on_click=_guardar).props("color=primary")

    dlg.open()


def _abrir_dialog_cerrar(corte, page_client):
    if not es_superadmin():
        with page_client:
            ui.notify(
                "Solo el superadmin puede cerrar la caja.",
                type="negative",
                position="top",
            )
        return

    with ui.dialog() as dlg, ui.card().style("min-width:480px;"):
        ui.label("Cerrar caja").classes("text-lg font-bold text-slate-800 mb-2")
        ui.html(
            f'<p style="color:#475569;font-size:0.85rem;margin-bottom:8px;">'
            f"Abierta por <strong>{corte['usuario_apertura']}</strong> a las "
            f"{corte['hora_apertura']}. Ingresá el efectivo que contaste físicamente."
            f"</p>"
        )
        saldo_real_in = (
            ui.input("Efectivo contado ($)", value="0")
            .props("type=number min=0")
            .classes("w-full")
        )
        notas_in = ui.input(
            "Notas (opcional)",
            placeholder="ej. Faltó $50, revisar cambio de la orden #12",
        ).classes("w-full")
        pwd_in = (
            ui.input("Contraseña de bypass")
            .props("type=password")
            .classes("w-full mt-2")
        )

        async def _guardar():
            if pwd_in.value != os.getenv("BYPASS_PASSWORD", "admin123"):
                with page_client:
                    ui.notify(
                        "Contraseña incorrecta.",
                        type="negative",
                        position="top",
                    )
                return
            try:
                saldo_real = int(saldo_real_in.value or 0)
            except (TypeError, ValueError):
                with page_client:
                    ui.notify(
                        "Saldo real inválido.",
                        type="negative",
                        position="top",
                    )
                return
            result = await database_web.cerrar_corte_async(
                corte["id"], usuario_actual(), saldo_real, notas_in.value.strip()
            )
            if not result["ok"]:
                with page_client:
                    ui.notify(
                        result.get("error", "Error cerrando caja."),
                        type="negative",
                        position="top",
                    )
                return
            diferencia = result["diferencia"]
            ui.notify(
                f"Caja cerrada. Diferencia: ${diferencia:+d}",
                type="positive" if diferencia >= 0 else "negative",
                position="top",
                timeout=8000,
            )
            dlg.close()
            ui.navigate.reload()

        with ui.row().classes("w-full justify-end mt-3 gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Cerrar caja", on_click=_guardar).props("color=negative")

    dlg.open()


def _abrir_dialog_movimiento(corte, page_client):
    """Disponible para todos los admins (no requiere BYPASS_PASSWORD,
    solo el botón de cerrar sí lo requiere)."""
    with ui.dialog() as dlg, ui.card().style("min-width:480px;"):
        ui.label("Registrar movimiento").classes(
            "text-lg font-bold text-slate-800 mb-2"
        )
        ui.html(
            f'<p style="color:#475569;font-size:0.85rem;margin-bottom:8px;">'
            f"Registra un ingreso o egreso de efectivo en la caja. "
            f"Para pagos en efectivo de personalizados, el sistema lo hace "
            f"automáticamente al confirmar el pago en el panel operativo."
            f"</p>"
        )
        tipo_in = ui.select(
            {
                "egreso": "Egreso (dinero sale de la caja)",
                "ingreso": "Ingreso (dinero entra a la caja)",
            },
            value="egreso",
            label="Tipo",
        ).classes("w-full")
        monto_in = (
            ui.input("Monto ($)", value="0")
            .props("type=number min=1")
            .classes("w-full")
        )
        concepto_in = ui.select(
            {
                "Cambio a cliente": "Cambio a cliente (devolviste más cambio del que debías)",
                "Retiro de caja": "Retiro de caja (sacaste efectivo para algo)",
                "Pago extra en mostrador": "Pago extra en mostrador (no es personalizado)",
                "Reposición de cambio": "Reposición de cambio (entraste monedas/billetes a la caja)",
                "Otro": "Otro (describe en notas)",
            },
            value="Cambio a cliente",
            label="Concepto",
        ).classes("w-full")
        notas_in = ui.input(
            "Notas (opcional)", placeholder="Detalle adicional"
        ).classes("w-full")

        async def _guardar():
            try:
                monto = int(monto_in.value or 0)
            except (TypeError, ValueError):
                with page_client:
                    ui.notify(
                        "Monto inválido.",
                        type="negative",
                        position="top",
                    )
                return
            if monto <= 0:
                with page_client:
                    ui.notify(
                        "El monto debe ser mayor a 0.",
                        type="negative",
                        position="top",
                    )
                return
            result = await database_web.registrar_movimiento_async(
                corte_id=corte["id"],
                tipo=tipo_in.value,
                monto=monto,
                concepto=concepto_in.value,
                usuario=usuario_actual(),
                notas=notas_in.value.strip(),
                auto=0,
            )
            if not result["ok"]:
                with page_client:
                    ui.notify(
                        result.get("error", "Error registrando."),
                        type="negative",
                        position="top",
                    )
                return
            with page_client:
                ui.notify(
                    f"Movimiento registrado: {'+' if tipo_in.value == 'ingreso' else '−'}${monto}",
                    type="positive",
                    position="top",
                )
            dlg.close()
            ui.navigate.reload()

        with ui.row().classes("w-full justify-end mt-3 gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Registrar", on_click=_guardar).props("color=primary")

    dlg.open()


async def _render_historial():
    cortes = await database_web.listar_cortes_async(limite=30)
    cerrados = [c for c in cortes if c["estado"] == "cerrado"]
    if not cerrados:
        return
    ui.html(
        '<div style="font-size:1.05rem;font-weight:800;color:#1e293b;'
        'margin-bottom:8px;">Historial de cortes cerrados</div>'
    )
    for c in cerrados:
        _render_fila_corte(c)


def _render_fila_corte(c):
    diferencia = c.get("diferencia") or 0
    color_dif = "#16a34a" if diferencia >= 0 else "#dc2626"
    signo = "+" if diferencia >= 0 else ""
    fecha_cierre = (
        (c.get("hora_cierre") or "").split(" ")[-1] if c.get("hora_cierre") else "—"
    )

    with ui.element("div").classes("orden-card").style("flex-direction:column;"):
        with ui.element("div").style(
            "display:flex;align-items:center;justify-content:space-between;"
        ):
            ui.html(
                f"<div>"
                f'<div style="font-weight:800;color:#1e293b;">Corte #{c["id"]} · {c["fecha"]}</div>'
                f'<div style="font-size:0.78rem;color:#64748b;">'
                f"Apertura: {c['usuario_apertura']} · "
                f"Cierre: {c.get('usuario_cierre') or '—'} a las {fecha_cierre}"
                f"</div>"
                f"</div>"
                f'<div style="text-align:right;">'
                f'<div style="font-size:0.7rem;color:#64748b;">Diferencia</div>'
                f'<div style="font-size:1.3rem;font-weight:800;color:{color_dif};">'
                f"{signo}${diferencia}"
                f"</div>"
                f"</div>"
            )
        with ui.element("div").style(
            "font-size:0.85rem;color:#475569;margin-top:8px;"
            "display:flex;gap:24px;flex-wrap:wrap;"
        ):
            ui.html(
                f'<div><span style="color:#94a3b8;">Inicial:</span> '
                f"<strong>${c['saldo_inicial']}</strong></div>"
                f'<div><span style="color:#94a3b8;">Esperado:</span> '
                f"<strong>${c['saldo_esperado'] or 0}</strong></div>"
                f'<div><span style="color:#94a3b8;">Contado:</span> '
                f"<strong>${c['saldo_real'] or 0}</strong></div>"
            )
        if c.get("notas"):
            ui.html(
                f'<div style="background:#fef3c7;color:#92400e;padding:6px 10px;'
                f'border-radius:4px;font-size:0.78rem;margin-top:6px;">'
                f"<strong>Notas:</strong> {c['notas']}</div>"
            )
