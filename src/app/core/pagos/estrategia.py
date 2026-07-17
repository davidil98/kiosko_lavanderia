"""ABC y tipos compartidos para los métodos de pago del kiosko.

`MetodoPago` es el Strategy pattern. `ContextoPago` agrupa lo que el método
necesita para renderizar e iniciar: el wizard, callbacks UI y la publicación
al bus. Los métodos NO tocan SQL, NO importan `requests`, NO importan GPIO.
Solo delegan a `repo/transacciones`, `adaptadores/mercado_pago/point` y
`eventos/bus`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Awaitable, Callable, Optional

from app.core.estados import MetodoPago as MetodoPagoEnum

if TYPE_CHECKING:
    from app.ui.kiosko.wizard import WizardKiosko


@dataclass
class ContextoPago:
    """Lo que un MetodoPago necesita para renderizar e iniciar.

    - `wizard`: estado del cliente (paso, servicio, peso, dinero, último id).
    - `on_cancelar`: callable UI (async) para volver al paso anterior.
    - `refresh`: callable UI (sync) para re-renderizar el kiosko tras un cambio.
    """

    wizard: "WizardKiosko"
    on_cancelar: Callable[[], Awaitable[None]]
    refresh: Callable[[], None]


class MetodoPagoStrategy(ABC):
    """Strategy para los métodos de pago del kiosko cliente.

    Cada subclase define:
    - `codigo`: `MetodoPagoEnum` (catálogo cerrado).
    - `nombre`, `icono`, `descripcion`: para la tarjeta de selección.
    - `render_panel(ctx)`: muestra el panel NiceGUI con los controles.
    - `iniciar(ctx)`: dispara el flujo de pago. NO espera la confirmación
      (Point usa polling; monedas es inmediato; mostrador es externo).
    """

    codigo: MetodoPagoEnum
    nombre: str
    icono: str
    descripcion: str

    @abstractmethod
    def render_panel(self, ctx: ContextoPago) -> None: ...

    async def iniciar(self, ctx: ContextoPago) -> None:
        """Dispara el pago. El default es no-op (los métodos override)."""
        return None


# Tipo para que la UI pueda declarar "una instancia de cualquier método"
MetodoPagoCualquiera = MetodoPagoStrategy
