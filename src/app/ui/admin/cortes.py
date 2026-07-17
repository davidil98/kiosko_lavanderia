"""Página de Cortes de Caja (`@ui.page("/admin/cortes")`).

Estados posibles:
- Sin caja activa: mensaje + botón "Abrir caja" (superadmin).
- Caja abierta: KPIs (ingresos, egresos, esperado) + lista de movimientos
  + botones "Registrar movimiento" y "Cerrar caja".
- Caja cerrada: solo el historial.

Es la vista más simple del admin: por decisión del usuario, sin búsqueda ni
filtros; toda la información de la caja activa se ve en una sola pantalla.
"""

import asyncio
import os
from datetime import datetime

from nicegui import ui

from app.core import cortes as core_cortes
from app.ui.admin._componentes import boton_cerrar_sesion, render_header
from app.ui.compartido.auth import es_superadmin, redirigir_si_no_autenticado


@ui.page("/admin/cortes")
async def admin_cortes():
    if redirigir_si_no_autenticado():
        return
    render_header("Operador")

    @ui.refreshable
    async def contenido() -> None:
        corte = await core_cortes.obtener_activo_async()
        if corte is None:
            _render_sin_caja()
        else:
            await _render_caja_abierta(corte)
        ui.html('<div style="height:24px;"></div>')
        await _render_historial()

    # Header estático fuera del refreshable.
    with ui.element("div").props("id=admin-content"):
        ui.html(
            '<h2 style="font-size:1.5rem;font-weight:800;color:#1e293b;'
            'margin-bottom:6px;display:flex;align-items:center;gap:10px;">'
            '<img src="/media/icons/ticket.svg" style="width:32px;height:32px;">'
            "Cortes de Caja</h2>"
        )
        with ui.element("div").props("id=cortes-contenido"):
            await contenido()

    ui.timer(3.0, contenido.refresh)
    boton_cerrar_sesion()


# ── Sin caja abierta ──────────────────────────────────────────────────────


def _render_sin_caja() -> None:
    with ui.element("div").style(
        "background:#f1f5f9;border-radius:8px;padding:24px;"
        "text-align:center;margin-bottom:18px;"
    ):
        ui.image("/media/icons/ticket.svg").style(
            "width:48px;height:48px;opacity:0.5;margin-bottom:8px;"
        )
        ui.html(
            '<div style="font-size:1.05rem;font-weight:700;color:#475569;'
            'margin-bottom:4px;">No hay caja abierta</div>'
            '<div style="font-size:0.85rem;color:#94a3b8;">'
            "Abre la caja al inicio del día para empezar a registrar movimientos."
            "</div>"
        )
    if es_superadmin():
        with ui.row().classes("w-full justify-center"):
            ui.button("🔓 Abrir caja", on_click=_abrir_dialog).props("color=primary")
    else:
        ui.html(
            '<div style="text-align:center;color:#94a3b8;font-size:0.85rem;">'
            "Solo el superadmin puede abrir la caja."
            "</div>"
        )


# ── Caja abierta ──────────────────────────────────────────────────────────


async def _render_caja_abierta(corte: dict) -> None:
    movimientos = await core_cortes.listar_movimientos_async(corte["id"])
    resumen = core_cortes.resumen(corte, movimientos)

    with ui.element("div").style(
        "background:#f1f5f9;border-radius:8px;padding:18px;margin-bottom:18px;"
    ):
        ui.html(
            f'<div style="font-size:1rem;font-weight:700;color:#1e293b;'
            f'margin-bottom:6px;">Caja abierta · #{corte["id"]} · '
            f"{corte['fecha']} {corte['hora_apertura']}</div>"
            f'<div style="font-size:0.82rem;color:#64748b;">'
            f"Abierta por <strong>{corte['usuario_apertura']}</strong>"
            f"</div>"
        )
        with ui.element("div").style(
            "display:grid;grid-template-columns:repeat(4, 1fr);gap:12px;margin-top:14px;"
        ):
            _kpi("Saldo inicial", f"${resumen['saldo_inicial']}", "#64748b")
            _kpi("Ingresos", f"${resumen['ingresos']}", "#16a34a")
            _kpi("Egresos", f"${resumen['egresos']}", "#dc2626")
            _kpi("Esperado", f"${resumen['esperado']}", "#1e40af")
        with ui.row().classes("w-full justify-end mt-4 gap-2"):
            ui.button(
                "+ Registrar movimiento",
                on_click=lambda c=corte: _abrir_dialog_movimiento(c),
            ).props("color=primary")
            if es_superadmin():
                ui.button(
                    "🔒 Cerrar caja",
                    on_click=lambda c=corte: _abrir_dialog_cerrar(c),
                ).props("color=negative")

    # Movimientos
    ui.html(
        f'<h3 style="font-size:1.1rem;font-weight:700;color:#1e293b;'
        f'margin-bottom:8px;">Movimientos ({len(movimientos)})</h3>'
    )
    if not movimientos:
        ui.html(
            '<div style="text-align:center;color:#94a3b8;padding:16px;">'
            "Sin movimientos aún. Registra el primero con el botón de arriba."
            "</div>"
        )
    else:
        with ui.element("div").style("display:flex;flex-direction:column;gap:6px;"):
            for m in movimientos:
                _render_fila_movimiento(m)


def _kpi(label: str, valor: str, color: str) -> None:
    with ui.element("div").style(
        "background:white;padding:12px;border-radius:6px;border-left:3px solid "
        f"{color};"
    ):
        ui.html(
            f'<div style="font-size:0.7rem;color:#94a3b8;text-transform:uppercase;'
            f'letter-spacing:0.5px;">{label}</div>'
            f'<div style="font-size:1.2rem;font-weight:800;color:{color};">{valor}</div>'
        )


def _render_fila_movimiento(m) -> None:
    """Acepta tanto un dict como un dataclass `MovimientoCaja`."""

    def _get(key: str, default=""):
        if isinstance(m, dict):
            return m.get(key, default)
        return getattr(m, key, default)

    color = "#16a34a" if _get("tipo") == "ingreso" else "#dc2626"
    icono = "↓" if _get("tipo") == "ingreso" else "↑"
    ui.html(
        f'<div style="background:white;padding:10px 14px;border-radius:6px;'
        f'display:flex;align-items:center;gap:12px;border-left:3px solid {color};">'
        f'<span style="color:{color};font-size:1.2rem;font-weight:700;">{icono}</span>'
        f'<div style="flex:1;">'
        f'<div style="font-weight:600;color:#1e293b;">{_get("concepto")}</div>'
        f'<div style="font-size:0.78rem;color:#94a3b8;">'
        f"{_get('fecha_hora')} · {_get('usuario')}"
        + (f" · {_get('notas')}" if _get("notas") else "")
        + f"</div></div>"
        f'<div style="font-weight:800;color:{color};">${_get("monto")}</div>'
        f"</div>"
    )


# ── Historial de cortes cerrados ──────────────────────────────────────────


async def _render_historial() -> None:
    cerrados = await core_cortes.listar_cerrados_async(30)
    if not cerrados:
        return
    ui.html(
        f'<h3 style="font-size:1.1rem;font-weight:700;color:#1e293b;'
        f'margin-top:24px;margin-bottom:8px;">Historial ({len(cerrados)})</h3>'
    )
    with ui.element("div").style("display:flex;flex-direction:column;gap:4px;"):
        for c in cerrados:
            dif = c.get("diferencia") or 0
            dif_color = (
                "#16a34a" if dif == 0 else ("#f59e0b" if abs(dif) < 50 else "#dc2626")
            )
            ui.html(
                f'<div style="background:white;padding:8px 12px;border-radius:6px;'
                f'display:flex;align-items:center;gap:10px;font-size:0.88rem;">'
                f'<strong style="color:#1e293b;">#{c["id"]}</strong>'
                f'<span style="color:#64748b;">{c["fecha"]}</span>'
                f'<span style="color:#475569;">{c["usuario_apertura"]}'
                + (f" → {c['usuario_cierre']}" if c.get("usuario_cierre") else "")
                + "</span>"
                f'<span style="margin-left:auto;color:#94a3b8;">'
                f"Inicial ${c['saldo_inicial']} · Real ${c.get('saldo_real', 0)}"
                f"</span>"
                f'<span style="color:{dif_color};font-weight:700;">'
                f"Δ ${dif:+d}"
                f"</span>"
                f"</div>"
            )


# ── Diálogos ──────────────────────────────────────────────────────────────


def _abrir_dialog() -> None:
    pwd_ref: dict = {"input": None}
    fecha_ref: dict = {"input": None}
    inicial_ref: dict = {"input": None}

    async def confirmar() -> None:
        pwd = pwd_ref["input"].value if pwd_ref["input"] else ""
        if pwd != os.getenv("BYPASS_PASSWORD", "admin123"):
            ui.notify("Contraseña incorrecta", type="negative")
            return
        fecha = (
            fecha_ref["input"].value
            if fecha_ref["input"]
            else datetime.now().strftime("%Y-%m-%d")
        )
        try:
            saldo = int(float(inicial_ref["input"].value or 0))
        except ValueError:
            ui.notify("Saldo inicial inválido", type="negative")
            return
        r = core_cortes.abrir(fecha, "Moi", saldo)
        if r["ok"]:
            ui.notify(f"Caja abierta con saldo inicial ${saldo}", type="positive")
            dlg.close()
        else:
            ui.notify(r.get("error", "Error abriendo caja"), type="negative")

    with ui.dialog() as dlg, ui.card().style("min-width:340px;"):
        ui.label("Abrir caja").classes("text-lg font-bold text-slate-800 mb-2")
        fecha_ref["input"] = ui.input(
            "Fecha", value=datetime.now().strftime("%Y-%m-%d")
        ).classes("w-full mb-2")
        inicial_ref["input"] = (
            ui.input("Saldo inicial ($)", value="0")
            .props("type=number min=0")
            .classes("w-full mb-2")
        )
        pwd_ref["input"] = (
            ui.input("Contraseña de bypass", password=True)
            .props("type=password")
            .classes("w-full mb-4")
        )
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Abrir caja", on_click=confirmar).props("color=primary")
    dlg.open()


def _abrir_dialog_movimiento(corte: dict) -> None:
    tipo_ref: dict = {"select": None}
    monto_ref: dict = {"input": None}
    concepto_ref: dict = {"input": None}
    notas_ref: dict = {"input": None}

    async def confirmar() -> None:
        tipo = tipo_ref["select"].value if tipo_ref["select"] else "ingreso"
        try:
            monto = int(float(monto_ref["input"].value or 0))
        except ValueError:
            ui.notify("Monto inválido", type="negative")
            return
        concepto = (
            (concepto_ref["input"].value or "").strip() if concepto_ref["input"] else ""
        )
        notas = (notas_ref["input"].value or "").strip() if notas_ref["input"] else ""
        r = await core_cortes.registrar_movimiento_async(
            corte["id"],
            tipo,
            monto,
            concepto,
            "Operador",
            notas,
        )
        if r["ok"]:
            ui.notify("Movimiento registrado", type="positive")
            dlg.close()
        else:
            ui.notify(r.get("error", "Error"), type="negative")

    with ui.dialog() as dlg, ui.card().style("min-width:340px;"):
        ui.label(f"Registrar movimiento · Caja #{corte['id']}").classes(
            "text-lg font-bold text-slate-800 mb-2"
        )
        tipo_ref["select"] = ui.select(
            {"ingreso": "Ingreso", "egreso": "Egreso"},
            value="ingreso",
            label="Tipo",
        ).classes("w-full mb-2")
        monto_ref["input"] = (
            ui.input("Monto ($)", value="0")
            .props("type=number min=1")
            .classes("w-full mb-2")
        )
        concepto_ref["input"] = ui.input(
            "Concepto *", placeholder="Venta mostrador, Cambio, etc."
        ).classes("w-full mb-2")
        notas_ref["input"] = ui.input(
            "Notas (opcional)", placeholder="Detalle adicional"
        ).classes("w-full mb-4")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Registrar", on_click=confirmar).props("color=primary")
    dlg.open()


def _abrir_dialog_cerrar(corte: dict) -> None:
    real_ref: dict = {"input": None}
    notas_ref: dict = {"input": None}
    pwd_ref: dict = {"input": None}

    async def confirmar() -> None:
        pwd = pwd_ref["input"].value if pwd_ref["input"] else ""
        if pwd != os.getenv("BYPASS_PASSWORD", "admin123"):
            ui.notify("Contraseña incorrecta", type="negative")
            return
        try:
            real = int(float(real_ref["input"].value or 0))
        except ValueError:
            ui.notify("Saldo real inválido", type="negative")
            return
        notas = (notas_ref["input"].value or "").strip() if notas_ref["input"] else ""
        r = await core_cortes.cerrar_async(corte["id"], "Moi", real, notas)
        if r["ok"]:
            dif = r.get("diferencia", 0)
            ui.notify(
                f"Caja cerrada · diferencia: ${dif:+d}",
                type="positive",
            )
            dlg.close()
        else:
            ui.notify(r.get("error", "Error"), type="negative")

    with ui.dialog() as dlg, ui.card().style("min-width:340px;"):
        ui.label(f"Cerrar caja · #{corte['id']}").classes(
            "text-lg font-bold text-slate-800 mb-2"
        )
        ui.html(
            '<div style="font-size:0.85rem;color:#64748b;margin-bottom:12px;">'
            "El sistema calcula el esperado = saldo inicial + ingresos - egresos. "
            "La diferencia se guarda en el historial."
            "</div>"
        )
        real_ref["input"] = (
            ui.input("Saldo real contado ($)", value="0")
            .props("type=number min=0")
            .classes("w-full mb-2")
        )
        notas_ref["input"] = ui.input(
            "Notas / comentarios", placeholder="Sin novedad, etc."
        ).classes("w-full mb-2")
        pwd_ref["input"] = (
            ui.input("Contraseña de bypass", password=True)
            .props("type=password")
            .classes("w-full mb-4")
        )
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Cerrar caja", on_click=confirmar).props("color=negative")
    dlg.open()
