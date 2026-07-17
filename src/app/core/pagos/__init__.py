"""Strategy de métodos de pago del kiosko cliente.

Reglas:
- Todos los métodos implementan `MetodoPagoStrategy` (de `estrategia.py`).
- Ningún método toca SQL directamente: delega en `repo/transacciones`.
- Ningún método hace HTTP a MP directamente: delega en
  `adaptadores/mercado_pago/point`.
- La UI solo llama a `render_panel` e `iniciar`; nunca construye
  `transacciones` ni `point` directamente.
"""

from app.core.pagos.estrategia import ContextoPago, MetodoPagoStrategy
from app.core.pagos.monedas import MetodoMonedas
from app.core.pagos.mostrador import MetodoMostrador
from app.core.pagos.point import MetodoPoint

__all__ = [
    "ContextoPago",
    "MetodoPagoStrategy",
    "MetodoMonedas",
    "MetodoMostrador",
    "MetodoPoint",
]


# Orden importante: `MetodoMonedas` primero (opción por defecto del cliente).
METODOS_PAGO_DISPONIBLES: list[MetodoPagoStrategy] = [
    MetodoMonedas(),
    MetodoPoint(),
    MetodoMostrador(),
]
