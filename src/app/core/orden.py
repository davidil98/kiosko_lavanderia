"""Modelo de dominio: Orden.

Dataclass inmutable. Cualquier cambio (transición de estado, edición de peso,
asignación de máquina) produce una nueva instancia vía `dataclasses.replace()`.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .estados import EstadoOrden, Modalidad, MetodoPago, EtapaKanban


@dataclass(frozen=True)
class Orden:
    id: Optional[int]
    servicio_codigo: str
    segmentacion_id: Optional[int]
    modalidad: Modalidad
    peso_kg: Optional[float]
    peso_real_kg: Optional[float]
    monto: int
    metodo_pago: Optional[MetodoPago]
    estado: EstadoOrden
    etapa_kanban: Optional[EtapaKanban]
    maquina_codigo: Optional[str]
    nombre_cliente: str
    mp_order_id: Optional[str]
    folio_terminal: Optional[str]
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @staticmethod
    def nueva(
        *,
        servicio_codigo: str,
        nombre_cliente: str,
        modalidad: Modalidad = Modalidad.AUTOSERVICIO,
        segmentacion_id: Optional[int] = None,
    ) -> "Orden":
        """Factory para una orden en PENDIENTE_PESO antes de conocer el peso."""
        ahora = datetime.now()
        return Orden(
            id=None,
            servicio_codigo=servicio_codigo,
            segmentacion_id=segmentacion_id,
            modalidad=modalidad,
            peso_kg=None,
            peso_real_kg=None,
            monto=0,
            metodo_pago=None,
            estado=EstadoOrden.PENDIENTE_PESO,
            etapa_kanban=None,
            maquina_codigo=None,
            nombre_cliente=nombre_cliente,
            mp_order_id=None,
            folio_terminal=None,
            created_at=ahora,
            updated_at=ahora,
        )
