"""Único lugar que muta el estado de una Orden.

`aplicar(orden, evento)` devuelve una nueva `Orden` con el estado actualizado.
Lanza `TransicionInvalida` si la combinación (estado_actual, evento) no está permitida.
"""

from dataclasses import replace
from datetime import datetime
from enum import Enum

from .estados import EstadoOrden
from .orden import Orden


class Evento(str, Enum):
    """Eventos que el sistema puede aplicar sobre una orden."""

    PESO_APROBADO = "peso_aprobado"
    PAGO_MONEDAS = "pago_monedas"
    INICIAR_POINT = "iniciar_point"
    COBRAR_MOSTRADOR = "cobrar_mostrador"
    PAGO_CONFIRMADO = "pago_confirmado"
    ASIGNAR_MAQUINA = "asignar_maquina"
    COMPLETAR = "completar"
    CANCELAR = "cancelar"
    EXPIRAR = "expirar"


_TRANSICIONES: dict[EstadoOrden, dict[Evento, EstadoOrden]] = {
    EstadoOrden.PENDIENTE_PESO: {
        Evento.PESO_APROBADO: EstadoOrden.PROCESANDO_PAGO,
        Evento.CANCELAR: EstadoOrden.CANCELADO,
    },
    EstadoOrden.PROCESANDO_PAGO: {
        Evento.PAGO_MONEDAS: EstadoOrden.PENDIENTE,
        Evento.INICIAR_POINT: EstadoOrden.PENDIENTE_PAGO,
        Evento.COBRAR_MOSTRADOR: EstadoOrden.PENDIENTE_PAGO,
        Evento.CANCELAR: EstadoOrden.CANCELADO,
    },
    EstadoOrden.PENDIENTE_PAGO: {
        Evento.PAGO_CONFIRMADO: EstadoOrden.PENDIENTE,
        Evento.CANCELAR: EstadoOrden.CANCELADO,
        Evento.EXPIRAR: EstadoOrden.CANCELADO,
    },
    EstadoOrden.PENDIENTE: {
        Evento.ASIGNAR_MAQUINA: EstadoOrden.EN_CURSO,
        Evento.CANCELAR: EstadoOrden.CANCELADO,
    },
    EstadoOrden.EN_CURSO: {
        Evento.COMPLETAR: EstadoOrden.FINALIZADO,
    },
    EstadoOrden.FINALIZADO: {},
    EstadoOrden.CANCELADO: {},
}


class TransicionInvalida(Exception):
    """Se intenta aplicar un evento que no procede desde el estado actual."""

    def __init__(self, estado: EstadoOrden, evento: Evento):
        super().__init__(f"No se puede aplicar {evento.value} desde {estado.value}")
        self.estado = estado
        self.evento = evento


def aplicar(orden: Orden, evento: Evento) -> Orden:
    """Devuelve una nueva Orden con el estado actualizado por el evento."""
    eventos_validos = _TRANSICIONES[orden.estado]
    if evento not in eventos_validos:
        raise TransicionInvalida(orden.estado, evento)
    nuevo_estado = eventos_validos[evento]
    return replace(orden, estado=nuevo_estado, updated_at=datetime.now())


def transiciones_permitidas(estado: EstadoOrden) -> set[Evento]:
    """Helper para la UI: lista los eventos que la orden puede recibir desde `estado`."""
    return set(_TRANSICIONES[estado].keys())
