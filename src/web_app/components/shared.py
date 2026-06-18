from nicegui import ui
from services.auth import usuario_actual


def render_user_chip(dialogo_cambio=None):
    u = usuario_actual()
    if dialogo_cambio:
        with ui.element("div").classes("user-chip").on("click", dialogo_cambio.open):
            ui.html(
                f'<img src="/media/icons/user.svg" style="width:16px;height:16px;vertical-align:middle;margin-right:4px;">'
                f'{u} <span style="opacity:0.5;margin-left:4px;">▼</span>'
            )
    else:
        with ui.element("div").classes("user-chip"):
            ui.html(
                f'<img src="/media/icons/user.svg" style="width:16px;height:16px;vertical-align:middle;margin-right:4px;">'
                f"{u}"
            )


def badge_servicio(tipo):
    cls = (
        "badge-lavar" if "Lavar" in tipo or "Autolavado" in tipo else "badge-secar"
    )
    return f'<span class="orden-servicio-badge {cls}">{tipo}</span>'


def badge_metodo_pago(modalidad):
    if not modalidad:
        return ""
    m = modalidad
    if "terminal" in m:
        color_bg, color_fg = "#fce7f3", "#be185d"
        label = "Terminal"
    elif "monedas" in m:
        color_bg, color_fg = "#d1fae5", "#065f46"
        label = "Efectivo"
    elif "pendiente-pago" in m or "mostrador" in m:
        color_bg, color_fg = "#dcfce7", "#166534"
        label = "Efectivo mostrador"
    else:
        color_bg, color_fg = "#e2e8f0", "#475569"
        label = "Otro"
    return f'<span class="orden-servicio-badge" style="background:{color_bg};color:{color_fg};">{label}</span>'


def render_seccion(icon, titulo, badge_cls, items, render_fn):
    ui.html(
        f"""
        <div class="seccion-header">
            <img src="/media/icons/{icon}.svg" style="width:18px;height:18px;vertical-align:middle;margin-right:6px;">
            {titulo}
            <span class="badge {badge_cls}">{len(items)}</span>
        </div>
    """
    )
    if not items:
        ui.html(
            '<div class="empty-state">'
            '<img src="/media/icons/sleep.svg" style="width:48px;height:48px;opacity:0.5;">'
            f"<p>Sin órdenes en esta sección</p></div>"
        )
    else:
        for v in items:
            render_fn(v)
