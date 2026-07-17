"""Constantes de UI compartida: paths a CSS, snippets HTML, helpers de badges.

Las páginas importan las constantes de aquí en lugar de hardcodear strings.
Los CSS viven en `static/` y se sirven vía `/static/...` (configurado en `main.py`).
"""

from pathlib import Path

from app.core.estados import EstadoOrden, MetodoPago, Modalidad

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"

ADMIN_CSS = "/static/admin.css"
KIOSKO_CSS = "/static/kiosko.css"
LOGOTIPO = "/media/logo_slogan.png"
FAVICON = "/media/icons/leaf.svg"


COLORES_METODO: dict[MetodoPago, tuple[str, str, str]] = {
    MetodoPago.MONEDAS: ("#d1fae5", "#065f46", "Efectivo"),
    MetodoPago.POINT: ("#dbeafe", "#1e40af", "Point"),
    MetodoPago.MOSTRADOR: ("#dcfce7", "#166534", "Mostrador"),
}


def color_servicio(servicio_codigo: str) -> tuple[str, str, str]:
    """Devuelve (bg, fg, label) para badge de servicio."""
    if servicio_codigo in ("autolavado", "Lavar", "Lavado"):
        return ("#dbeafe", "#1e40af", "Lavar")
    if servicio_codigo in ("secado", "Secar", "Secado"):
        return ("#fce7f3", "#be185d", "Secar")
    if "edredon" in servicio_codigo.lower():
        return ("#e9d5ff", "#6b21a8", "Edredón")
    if "ropa" in servicio_codigo.lower():
        return ("#fed7aa", "#9a3412", "Ropa")
    return ("#e2e8f0", "#475569", servicio_codigo or "?")


def _metodo_de_modalidad(m: Modalidad) -> MetodoPago:
    """Extrae el `MetodoPago` de una `Modalidad` compuesta (sin f-strings)."""
    if m is Modalidad.AUTOSERVICIO or m is Modalidad.PERSONALIZADO:
        return MetodoPago.MONEDAS  # default razonable
    if m is Modalidad.BYPASS:
        return MetodoPago.MONEDAS
    # Mapeo explícito; el enum no tiene `de(metodo)` inverso
    for metodo in MetodoPago:
        try:
            if Modalidad.de(m.base, metodo) is m:
                return metodo
        except Exception:
            pass
    return MetodoPago.MONEDAS


def badge_modalidad(m: Modalidad | str) -> str:
    """HTML span con color de fondo según modalidad."""
    if isinstance(m, str):
        try:
            m = Modalidad(m)
        except ValueError:
            return f'<span class="orden-servicio-badge" style="background:#e2e8f0;color:#475569;">{m}</span>'
    if m is Modalidad.BYPASS:
        return '<span class="orden-servicio-badge" style="background:#fef3c7;color:#92400e;">Cortesía</span>'
    bg, fg, label = COLORES_METODO[_metodo_de_modalidad(m)]
    return f'<span class="orden-servicio-badge" style="background:{bg};color:{fg};">{label}</span>'


def badge_metodo_pago(metodo: str) -> str:
    """HTML span con color según método de pago (string libre, no enum).

    Acepta los valores legacy de la BD (que aún no migraron al enum).
    """
    m = (metodo or "").lower()
    if "point" in m:
        return f'<span class="orden-servicio-badge" style="background:{COLORES_METODO[MetodoPago.POINT][0]};color:{COLORES_METODO[MetodoPago.POINT][1]};">Point</span>'
    if "terminal" in m:
        return '<span class="orden-servicio-badge" style="background:#fce7f3;color:#be185d;">Terminal</span>'
    if "monedas" in m:
        return f'<span class="orden-servicio-badge" style="background:{COLORES_METODO[MetodoPago.MONEDAS][0]};color:{COLORES_METODO[MetodoPago.MONEDAS][1]};">Efectivo</span>'
    if "mostrador" in m:
        return f'<span class="orden-servicio-badge" style="background:{COLORES_METODO[MetodoPago.MOSTRADOR][0]};color:{COLORES_METODO[MetodoPago.MOSTRADOR][1]};">Mostrador</span>'
    return f'<span class="orden-servicio-badge" style="background:#e2e8f0;color:#475569;">{metodo or "?"}</span>'


def badge_servicio(servicio_codigo: str) -> str:
    """HTML span con color según código de servicio."""
    bg, fg, label = color_servicio(servicio_codigo or "")
    return f'<span class="orden-servicio-badge" style="background:{bg};color:{fg};">{label}</span>'


_COLORES_ESTADO = {
    EstadoOrden.PENDIENTE_PESO.value: ("#fef3c7", "#92400e"),
    EstadoOrden.PROCESANDO_PAGO.value: ("#dbeafe", "#1e40af"),
    EstadoOrden.PENDIENTE_PAGO.value: ("#fed7aa", "#9a3412"),
    EstadoOrden.PENDIENTE.value: ("#d1fae5", "#065f46"),
    EstadoOrden.EN_CURSO.value: ("#bfdbfe", "#1e3a8a"),
    EstadoOrden.FINALIZADO.value: ("#e9d5ff", "#6b21a8"),
    EstadoOrden.CANCELADO.value: ("#fecaca", "#991b1b"),
    # Legacy (datos preexistentes en la BD)
    "En proceso": ("#bfdbfe", "#1e3a8a"),
    "Completado": ("#e9d5ff", "#6b21a8"),
}


def badge_estado(estado: str) -> str:
    """HTML span con color según estado de la orden."""
    bg, fg = _COLORES_ESTADO.get(estado, ("#e2e8f0", "#475569"))
    return f'<span class="orden-servicio-badge" style="background:{bg};color:{fg};">{estado}</span>'
