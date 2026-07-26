"""Tipos de eventos de dominio que circulan por el bus.

Cada evento es un dataclass inmutable con un `tipo` (string corto que el bus
usa para enrutar) y los datos relevantes. Los productores (core, repo,
adaptadores) emiten. Los consumidores (ui) se suscriben por `tipo`.

Convención de nombres: `orden.*` agrupa eventos del ciclo de vida de la
orden. `pago.*` agrupa notificaciones del flujo de pago (Point/terminal/QR),
sin prefijo `orden.` para que el kiosko cliente pueda suscribirse solo al
canal de pagos sin re-renderizar la pantalla de selección de servicio.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


TIPO_ORDEN_CREADA = "orden.creada"
TIPO_PESO_APROBADO = "orden.peso_aprobado"
TIPO_PESO_RECHAZADO = "orden.peso_rechazado"
TIPO_PAGO_CONFIRMADO = "pago.confirmado"
TIPO_PAGO_CANCELADO = "pago.cancelado"
TIPO_MAQUINA_ASIGNADA = "orden.maquina_asignada"
TIPO_CICLO_INICIADO = "orden.ciclo_iniciado"
TIPO_ORDEN_FINALIZADA = "orden.finalizada"
TIPO_ORDEN_CANCELADA = "orden.cancelada"
TIPO_MAQUINA_LIBERADA = "maquina.liberada"
TIPO_MAQUINA_PAUSADA = "maquina.pausada"
TIPO_MAQUINA_REANUDADA = "maquina.reanudada"
TIPO_ETAPA_KANBAN_CAMBIADA = "kanban.etapa_cambiada"


@dataclass(frozen=True)
class EventoDominio:
    tipo: str
    orden_id: int
    extra: dict
    cuando: datetime


def orden_creada(orden_id: int, **extra) -> EventoDominio:
    return EventoDominio(TIPO_ORDEN_CREADA, orden_id, dict(extra), datetime.now())


def peso_aprobado(orden_id: int, peso_kg: float, **extra) -> EventoDominio:
    return EventoDominio(
        TIPO_PESO_APROBADO, orden_id, {"peso_kg": peso_kg, **extra}, datetime.now()
    )


def peso_rechazado(orden_id: int, **extra) -> EventoDominio:
    return EventoDominio(TIPO_PESO_RECHAZADO, orden_id, dict(extra), datetime.now())


def pago_confirmado(orden_id: int, folio: str = "", **extra) -> EventoDominio:
    return EventoDominio(
        TIPO_PAGO_CONFIRMADO, orden_id, {"folio": folio, **extra}, datetime.now()
    )


def pago_cancelado(orden_id: int, motivo: str = "expired", **extra) -> EventoDominio:
    return EventoDominio(
        TIPO_PAGO_CANCELADO, orden_id, {"motivo": motivo, **extra}, datetime.now()
    )


def maquina_asignada(orden_id: int, maquina: str, **extra) -> EventoDominio:
    return EventoDominio(
        TIPO_MAQUINA_ASIGNADA, orden_id, {"maquina": maquina, **extra}, datetime.now()
    )


def ciclo_iniciado(orden_id: int, **extra) -> EventoDominio:
    return EventoDominio(TIPO_CICLO_INICIADO, orden_id, dict(extra), datetime.now())


def orden_finalizada(orden_id: int, **extra) -> EventoDominio:
    return EventoDominio(TIPO_ORDEN_FINALIZADA, orden_id, dict(extra), datetime.now())


def orden_cancelada(orden_id: int, **extra) -> EventoDominio:
    return EventoDominio(TIPO_ORDEN_CANCELADA, orden_id, dict(extra), datetime.now())


def maquina_liberada(orden_id: int, codigo: str, **extra) -> EventoDominio:
    return EventoDominio(
        TIPO_MAQUINA_LIBERADA, orden_id, {"codigo": codigo, **extra}, datetime.now()
    )


def maquina_pausada(orden_id: int, codigo: str, **extra) -> EventoDominio:
    return EventoDominio(
        TIPO_MAQUINA_PAUSADA, orden_id, {"codigo": codigo, **extra}, datetime.now()
    )


def maquina_reanudada(orden_id: int, codigo: str, **extra) -> EventoDominio:
    return EventoDominio(
        TIPO_MAQUINA_REANUDADA, orden_id, {"codigo": codigo, **extra}, datetime.now()
    )


def etapa_kanban_cambiada(orden_id: int, nueva_etapa: str, **extra) -> EventoDominio:
    return EventoDominio(
        TIPO_ETAPA_KANBAN_CAMBIADA,
        orden_id,
        {"nueva_etapa": nueva_etapa, **extra},
        datetime.now(),
    )


TODOS_LOS_TIPOS = frozenset(
    {
        TIPO_ORDEN_CREADA,
        TIPO_PESO_APROBADO,
        TIPO_PESO_RECHAZADO,
        TIPO_PAGO_CONFIRMADO,
        TIPO_PAGO_CANCELADO,
        TIPO_MAQUINA_ASIGNADA,
        TIPO_CICLO_INICIADO,
        TIPO_ORDEN_FINALIZADA,
        TIPO_ORDEN_CANCELADA,
        TIPO_MAQUINA_LIBERADA,
        TIPO_MAQUINA_PAUSADA,
        TIPO_MAQUINA_REANUDADA,
        TIPO_ETAPA_KANBAN_CAMBIADA,
    }
)
