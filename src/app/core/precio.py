"""Cálculo de precio polimórfico para Servicio y Segmentacion.

Acepta cualquiera de los dos dataclasses (ambos tienen `tipo_calculo`,
`precio_fijo` y `tarifa_por_kg`) y devuelve un entero redondeado.
"""

from typing import Protocol


class ItemCobrable(Protocol):
    tipo_calculo: str
    precio_fijo: int
    tarifa_por_kg: float


def calcular_precio(item: ItemCobrable, peso_kg: float = 0.0) -> int:
    tipo = getattr(item, "tipo_calculo", "fijo") or "fijo"
    if tipo == "fijo":
        return int(getattr(item, "precio_fijo", 0) or 0)
    if tipo == "por_kg":
        tarifa = float(getattr(item, "tarifa_por_kg", 0) or 0)
        return int(round(tarifa * max(0.0, float(peso_kg or 0))))
    if tipo == "por_duracion":
        return int(getattr(item, "precio_fijo", 0) or 0)
    return int(getattr(item, "precio_fijo", 0) or 0)


def formatear_precio(item: ItemCobrable, peso_kg: float = 0.0) -> str:
    """Texto para mostrar: '$45' o '$30/kg'."""
    tipo = getattr(item, "tipo_calculo", "fijo") or "fijo"
    if tipo == "por_kg":
        tarifa = float(getattr(item, "tarifa_por_kg", 0) or 0)
        return f"${int(round(tarifa))}/kg"
    return f"${calcular_precio(item, peso_kg)}"
