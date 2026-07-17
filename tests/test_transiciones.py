"""Tests de la máquina de estados de Orden.

Cubre las 6 transiciones válidas del flujo principal y al menos 4 combinaciones
inválidas representativas.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pytest

from app.core.estados import EstadoOrden, Modalidad
from app.core.orden import Orden
from app.core.transiciones import (
    Evento,
    TransicionInvalida,
    aplicar,
    transiciones_permitidas,
)


def _nueva(estado: EstadoOrden) -> Orden:
    from dataclasses import replace

    base = Orden.nueva(
        servicio_codigo="autolavado",
        nombre_cliente="Test",
        modalidad=Modalidad.AUTOSERVICIO_MONEDAS,
    )
    return replace(base, estado=estado)


# ── Transiciones válidas ──────────────────────────────────────────────────────


def test_pendiente_peso_a_procesando_pago():
    o = _nueva(EstadoOrden.PENDIENTE_PESO)
    nueva = aplicar(o, Evento.PESO_APROBADO)
    assert nueva.estado is EstadoOrden.PROCESANDO_PAGO
    assert nueva.updated_at >= o.updated_at


def test_procesando_pago_a_pendiente_por_monedas():
    o = _nueva(EstadoOrden.PROCESANDO_PAGO)
    nueva = aplicar(o, Evento.PAGO_MONEDAS)
    assert nueva.estado is EstadoOrden.PENDIENTE


def test_procesando_pago_a_pendiente_pago_por_point():
    o = _nueva(EstadoOrden.PROCESANDO_PAGO)
    nueva = aplicar(o, Evento.INICIAR_POINT)
    assert nueva.estado is EstadoOrden.PENDIENTE_PAGO


def test_procesando_pago_a_pendiente_pago_por_mostrador():
    o = _nueva(EstadoOrden.PROCESANDO_PAGO)
    nueva = aplicar(o, Evento.COBRAR_MOSTRADOR)
    assert nueva.estado is EstadoOrden.PENDIENTE_PAGO


def test_pendiente_pago_a_pendiente_por_confirmacion():
    o = _nueva(EstadoOrden.PENDIENTE_PAGO)
    nueva = aplicar(o, Evento.PAGO_CONFIRMADO)
    assert nueva.estado is EstadoOrden.PENDIENTE


def test_pendiente_a_en_curso_asignar_maquina():
    o = _nueva(EstadoOrden.PENDIENTE)
    nueva = aplicar(o, Evento.ASIGNAR_MAQUINA)
    assert nueva.estado is EstadoOrden.EN_CURSO


def test_en_curso_a_finalizado():
    o = _nueva(EstadoOrden.EN_CURSO)
    nueva = aplicar(o, Evento.COMPLETAR)
    assert nueva.estado is EstadoOrden.FINALIZADO


def test_cancelar_desde_pendiente_peso():
    o = _nueva(EstadoOrden.PENDIENTE_PESO)
    nueva = aplicar(o, Evento.CANCELAR)
    assert nueva.estado is EstadoOrden.CANCELADO


def test_cancelar_desde_procesando_pago():
    o = _nueva(EstadoOrden.PROCESANDO_PAGO)
    nueva = aplicar(o, Evento.CANCELAR)
    assert nueva.estado is EstadoOrden.CANCELADO


def test_cancelar_desde_pendiente_pago():
    o = _nueva(EstadoOrden.PENDIENTE_PAGO)
    nueva = aplicar(o, Evento.CANCELAR)
    assert nueva.estado is EstadoOrden.CANCELADO


def test_cancelar_desde_pendiente():
    o = _nueva(EstadoOrden.PENDIENTE)
    nueva = aplicar(o, Evento.CANCELAR)
    assert nueva.estado is EstadoOrden.CANCELADO


def test_expirar_desde_pendiente_pago():
    o = _nueva(EstadoOrden.PENDIENTE_PAGO)
    nueva = aplicar(o, Evento.EXPIRAR)
    assert nueva.estado is EstadoOrden.CANCELADO


# ── Transiciones inválidas ────────────────────────────────────────────────────


def test_no_se_puede_completar_desde_pendiente():
    o = _nueva(EstadoOrden.PENDIENTE)
    with pytest.raises(TransicionInvalida):
        aplicar(o, Evento.COMPLETAR)


def test_no_se_puede_asignar_maquina_desde_en_curso():
    o = _nueva(EstadoOrden.EN_CURSO)
    with pytest.raises(TransicionInvalida):
        aplicar(o, Evento.ASIGNAR_MAQUINA)


def test_no_se_puede_pagar_dos_veces():
    o = _nueva(EstadoOrden.PENDIENTE)
    with pytest.raises(TransicionInvalida):
        aplicar(o, Evento.PAGO_MONEDAS)


def test_finalizado_es_terminal():
    o = _nueva(EstadoOrden.FINALIZADO)
    for ev in Evento:
        with pytest.raises(TransicionInvalida):
            aplicar(o, ev)


def test_cancelado_es_terminal():
    o = _nueva(EstadoOrden.CANCELADO)
    for ev in Evento:
        with pytest.raises(TransicionInvalida):
            aplicar(o, ev)


def test_no_se_puede_cancelar_en_curso():
    o = _nueva(EstadoOrden.EN_CURSO)
    with pytest.raises(TransicionInvalida):
        aplicar(o, Evento.CANCELAR)


def test_aplicar_devuelve_nueva_instancia_inmutable():
    o = _nueva(EstadoOrden.PENDIENTE_PESO)
    nueva = aplicar(o, Evento.PESO_APROBADO)
    assert o.estado is EstadoOrden.PENDIENTE_PESO
    assert nueva is not o


# ── Helper de UI ──────────────────────────────────────────────────────────────


def test_transiciones_permitidas_listado():
    assert transiciones_permitidas(EstadoOrden.PENDIENTE_PESO) == {
        Evento.PESO_APROBADO,
        Evento.CANCELAR,
    }
    assert transiciones_permitidas(EstadoOrden.FINALIZADO) == set()
    assert transiciones_permitidas(EstadoOrden.CANCELADO) == set()
