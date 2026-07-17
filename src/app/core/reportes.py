"""Reportes y métricas del kiosko.

Capa de dominio sobre `repo/transacciones.py`. Las queries SQL se ejecutan
en el repo y esta capa las convierte a datetimes, formatea números y
proporciona helpers de UI (filtros de fecha, formateo).
"""

from collections import Counter
from datetime import datetime, timedelta
from typing import Optional

from app.repo import transacciones as repo


# ── Helpers de fechas ─────────────────────────────────────────────────────


def parsear_rango(rango: str) -> tuple[datetime, datetime]:
    """Convierte un string 'todo' | '7d' | '30d' | '90d' | '1y' en (desde, hasta)."""
    ahora = datetime.now()
    if rango == "todo":
        desde = datetime(2000, 1, 1)
    elif rango == "7d":
        desde = ahora - timedelta(days=7)
    elif rango == "30d":
        desde = ahora - timedelta(days=30)
    elif rango == "90d":
        desde = ahora - timedelta(days=90)
    elif rango == "1y":
        desde = ahora - timedelta(days=365)
    else:
        desde = ahora - timedelta(days=30)
    return desde, ahora


# ── KPIs ──────────────────────────────────────────────────────────────────


async def kpis(rango: str = "30d") -> dict:
    """Resumen de números clave del rango."""
    desde, _ = parsear_rango(rango)
    ordenes = await repo.obtener_completadas_entre(desde)  # ver más abajo
    if not ordenes:
        return {
            "ordenes_totales": 0,
            "recaudado": 0,
            "kilos_lavados": 0.0,
            "kg_por_orden": 0.0,
        }
    total = len(ordenes)
    recaudado = sum(o.get("monto_pagado", 0) or 0 for o in ordenes)
    kilos = sum(o.get("peso_kg", 0) or 0 for o in ordenes)
    return {
        "ordenes_totales": total,
        "recaudado": recaudado,
        "kilos_lavados": round(kilos, 2),
        "kg_por_orden": round(kilos / total, 2) if total else 0.0,
    }


# ── Gráficos ──────────────────────────────────────────────────────────────


async def uso_por_maquina(rango: str = "30d") -> list[dict]:
    """Cantidad de ciclos por máquina."""
    desde, _ = parsear_rango(rango)
    ordenes = await repo.obtener_completadas_entre(desde)
    conteo = Counter(o["id_equipo"] for o in ordenes if o.get("id_equipo"))
    return [{"maquina": m, "ciclos": c} for m, c in conteo.most_common()]


async def horas_pico(rango: str = "30d") -> list[int]:
    """24 buckets con el número de órdenes por hora del día."""
    desde, _ = parsear_rango(rango)
    ordenes = await repo.obtener_completadas_entre(desde)
    buckets = [0] * 24
    for o in ordenes:
        fh = o.get("fecha_hora") or ""
        if not fh:
            continue
        try:
            h = datetime.fromisoformat(fh).hour
        except ValueError:
            continue
        buckets[h] += 1
    return buckets


async def dias_pico(rango: str = "30d") -> list[int]:
    """7 buckets con el número de órdenes por día de la semana (0=lunes)."""
    desde, _ = parsear_rango(rango)
    ordenes = await repo.obtener_completadas_entre(desde)
    buckets = [0] * 7
    for o in ordenes:
        fh = o.get("fecha_hora") or ""
        if not fh:
            continue
        try:
            d = datetime.fromisoformat(fh).weekday()
        except ValueError:
            continue
        buckets[d] += 1
    return buckets


async def consumo_promedio_por_servicio(rango: str = "30d") -> list[dict]:
    """Promedio de kg y monto por servicio."""
    desde, _ = parsear_rango(rango)
    ordenes = await repo.obtener_completadas_entre(desde)
    by_servicio: dict[str, dict] = {}
    for o in ordenes:
        s = o.get("tipo_servicio") or "Sin servicio"
        if s not in by_servicio:
            by_servicio[s] = {"servicio": s, "kg_total": 0.0, "monto_total": 0, "n": 0}
        by_servicio[s]["kg_total"] += o.get("peso_kg", 0) or 0
        by_servicio[s]["monto_total"] += o.get("monto_pagado", 0) or 0
        by_servicio[s]["n"] += 1
    out = []
    for s in by_servicio.values():
        s["kg_promedio"] = round(s["kg_total"] / s["n"], 2) if s["n"] else 0
        s["monto_promedio"] = s["monto_total"] // s["n"] if s["n"] else 0
        out.append(s)
    return sorted(out, key=lambda x: x["kg_total"], reverse=True)


async def tasa_efectivo_vs_tarjeta(rango: str = "30d") -> list[dict]:
    """Pagos mensuales: efectivo (monedas/mostrador) vs tarjeta (point/terminal)."""
    desde, _ = parsear_rango(rango)
    ordenes = await repo.obtener_completadas_entre(desde)
    by_mes: dict[str, dict] = {}
    for o in ordenes:
        fh = o.get("fecha_hora") or ""
        if not fh:
            continue
        try:
            dt = datetime.fromisoformat(fh)
        except ValueError:
            continue
        mes = dt.strftime("%Y-%m")
        modalidad = (o.get("modalidad") or "").lower()
        if mes not in by_mes:
            by_mes[mes] = {"mes": mes, "efectivo": 0, "tarjeta": 0}
        if "point" in modalidad or "terminal" in modalidad:
            by_mes[mes]["tarjeta"] += o.get("monto_pagado", 0) or 0
        else:
            by_mes[mes]["efectivo"] += o.get("monto_pagado", 0) or 0
    return sorted(by_mes.values(), key=lambda x: x["mes"])
