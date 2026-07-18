"""Componentes reutilizables del panel admin.

- `render_header()`: el header sticky con logo, título y chip de usuario.
- `boton_cerrar_sesion()`: botón flotante bottom-right para logout.
- `render_tarjeta_dashboard()`: tarjeta con icono, título, subtítulo y badge opcional.
- `tarjeta_orden()`: tarjeta de orden para los 3 paneles operativos.
- `render_seccion()`: header de sección con icono, título y contador.
"""

from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from nicegui import app, ui

from app.ui.compartido.estilos import (
    ADMIN_CSS,
    LOGOTIPO,
    badge_estado,
    badge_modalidad,
    badge_servicio,
)


@dataclass
class TarjetaDashboard:
    """Spec declarativa para una tarjeta del dashboard."""

    icono: str
    titulo: str
    subtitulo: str
    badge: Optional[str] = None
    badge_color: tuple = ("#1e40af", "#dbeafe")  # fg, bg
    href: str = ""
    superadmin_only: bool = False


@dataclass
class AccionTarjeta:
    """Acción clickeable en una tarjeta de orden."""

    label: str
    color: str  # "primary" | "positive" | "negative" | "warning" | "info"
    handler: Callable[[dict], Awaitable[None]]


def render_header(usuario: str) -> None:
    """Header sticky del panel admin. Visible en todas las páginas internas."""
    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
    )
    ui.add_head_html(f'<link rel="stylesheet" href="{ADMIN_CSS}">')

    with ui.element("div").props("id=admin-header"):
        with ui.element("div").props("id=admin-header-inner"):
            with ui.element("div").classes("logo-area"):
                ui.image(LOGOTIPO)
                with ui.element("div"):
                    ui.html('<div class="admin-title">Panel de Administración</div>')
                    ui.html('<div class="admin-subtitle">Lavandería EcoLuna</div>')
            _render_user_chip(usuario)


def _render_user_chip(usuario: str) -> None:
    with ui.element("div").classes("user-chip"):
        ui.html(
            '<img src="/media/icons/user.svg" '
            'style="width:16px;height:16px;vertical-align:middle;margin-right:4px;">'
            f"{usuario}"
        )


def boton_cerrar_sesion() -> None:
    """Botón flotante bottom-right con la acción de logout."""
    from app.ui.compartido.auth import logout

    def cerrar_sesion() -> None:
        logout()
        ui.navigate.to("/admin/login")

    with ui.page_sticky(position="bottom-right", x_offset=20, y_offset=20):
        ui.button("Cerrar sesión", on_click=cerrar_sesion).props("flat color=negative")


def render_tarjeta_dashboard(t: TarjetaDashboard, es_superadmin: bool) -> None:
    """Una tarjeta clickeable. Si `superadmin_only` y no es super, no se renderiza."""
    if t.superadmin_only and not es_superadmin:
        return
    badge_html = ""
    if t.badge:
        fg, bg = t.badge_color
        badge_html = (
            f'<span class="badge" style="background:{bg};color:{fg};'
            f'font-size:0.9rem;padding:4px 12px;">{t.badge}</span>'
        )

    def _go() -> None:
        if t.href:
            ui.navigate.to(t.href)

    with ui.element("div").classes("dash-card").on("click", _go):
        with ui.element("div").classes("dash-card-icon"):
            ui.image(t.icono).style("width:64px;height:64px;object-fit:contain;")
        ui.html(
            f'<div class="dash-card-title" style="display:flex;'
            f'align-items:center;justify-content:center;gap:8px;">'
            f"{t.titulo}{badge_html}</div>"
        )
        ui.html(f'<div class="dash-card-sub">{t.subtitulo}</div>')


# ── Tarjeta de orden (compartida por los 3 paneles operativos) ──────────


def tarjeta_orden(v: dict, acciones: list[AccionTarjeta]) -> None:
    """Renderiza una tarjeta para una orden.

    `v` es el dict que retorna `repo/transacciones.transaccion_dict()`.
    `acciones` es la lista de botones que aparecen a la derecha.
    """
    nombre = v.get("nombre_cliente") or "Sin nombre"
    peso = v.get("peso_kg", 0) or 0
    monto = v.get("monto_pagado", 0) or 0
    estado = v.get("estado", "")
    servicio = v.get("tipo_servicio") or ""
    modalidad = v.get("modalidad", "")

    color_borde = "#a855f7" if "personalizado" in modalidad else "#7e22ce"

    with (
        ui.element("div")
        .classes("orden-card")
        .style(f"border-left:4px solid {color_borde};")
    ):
        with ui.element("div").style("flex:1;min-width:0;"):
            ui.html(
                f'<div class="orden-numero">Orden #{v["id_transaccion"]}</div>'
                f"{badge_servicio(servicio)} "
                f"{badge_modalidad(modalidad)} "
                f"{badge_estado(estado)}"
            )
            ui.html(f'<div class="orden-nombre">{nombre}</div>')
            ui.html(
                f'<div class="orden-meta">'
                f"{v.get('fecha_hora', '')} · "
                f"Peso: <strong>{peso} kg</strong> · "
                f"Monto: <strong>${monto}</strong>"
                f"</div>"
            )
        with ui.element("div").style(
            "flex-shrink:0;display:flex;flex-direction:column;gap:8px;"
            "align-items:flex-end;"
        ):
            for acc in acciones:

                def _on_click(_e=None, vv=v, aa=acc) -> None:
                    import asyncio

                    asyncio.create_task(aa.handler(vv))

                ui.button(acc.label, on_click=_on_click).props(
                    f"color={acc.color}"
                ).classes("orden-accion")


def render_seccion(icon: str, titulo: str, items: list, render_item) -> None:
    """Header de sección (icono + título + badge con count) + items.

    `render_item` es un callable que recibe un dict de orden y debe
    renderizar la tarjeta. El wrapper se encarga del empty state.
    """
    with ui.element("div").style(
        "display:flex;align-items:center;gap:10px;margin-bottom:14px;"
    ):
        ui.image(f"/media/icons/{icon}.svg").style("width:24px;height:24px;")
        ui.html(
            f'<div style="font-size:1.15rem;font-weight:800;color:#1e293b;">'
            f"{titulo}"
            f'<span class="badge badge-en-proceso" style="margin-left:10px;">{len(items)}</span>'
            f"</div>"
        )
    if not items:
        with ui.element("div").style("text-align:center;padding:30px 0;color:#94a3b8;"):
            ui.html(
                '<img src="/media/icons/sleep.svg" style="width:48px;height:48px;opacity:0.4;">'
                '<p style="margin-top:8px;">Sin órdenes en esta sección</p>'
            )
        return
    for v in items:
        render_item(v)


# ── Auto-refresh inteligente (sin regresar al scroll) ─────────────────────


def auto_refresh_smart(
    refresh_callable,
    hash_callable: Callable[[], int],
    intervalo_s: float = 3.0,
) -> None:
    """Lanza un `ui.timer` que solo invoca `refresh_callable` cuando el
    hash de `hash_callable()` cambia. Así, si nada cambia, NO se reemplaza
    el DOM y el scroll del usuario se preserva.

    Args:
        refresh_callable: la función a llamar cuando hay cambios. Usualmente
            `contenido.refresh` de un `ui.refreshable`.
        hash_callable: una función sin argumentos que retorna un int/hash
            representando el estado actual (e.g. número de órdenes pendientes).
        intervalo_s: segundos entre checks.
    """
    estado_previo = {"hash": None, "ticks": 0, "refreshes": 0}

    def _tick():
        try:
            h = hash_callable()
        except Exception:
            return
        estado_previo["ticks"] += 1
        if estado_previo["hash"] is None:
            estado_previo["hash"] = h
            print(f"[auto_refresh_smart] primer tick: hash={h}, NO refresca")
            return  # No refrescar en el primer tick (ya se pintó al inicio)
        if h != estado_previo["hash"]:
            estado_previo["hash"] = h
            estado_previo["refreshes"] += 1
            print(
                f"[auto_refresh_smart] cambio detectado: hash={h}, refrescando (#{estado_previo['refreshes']})"
            )
            refresh_callable()
        # else: print(f"[auto_refresh_smart] sin cambios, no refresca")

    ui.timer(intervalo_s, _tick)
