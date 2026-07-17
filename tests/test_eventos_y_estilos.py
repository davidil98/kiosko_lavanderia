"""Tests del bus de eventos y los dataclasses de tipos."""

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


# ── tipos.py ────────────────────────────────────────────────────────────────


def test_todos_los_tipos_esta_completo():
    from app.eventos import tipos

    assert tipos.TIPO_ORDEN_CREADA in tipos.TODOS_LOS_TIPOS
    assert tipos.TIPO_PAGO_CONFIRMADO in tipos.TODOS_LOS_TIPOS
    assert tipos.TIPO_ORDEN_CANCELADA in tipos.TODOS_LOS_TIPOS
    assert len(tipos.TODOS_LOS_TIPOS) == 9


def test_factory_orden_creada():
    from app.eventos import tipos

    ev = tipos.orden_creada(42, nombre="Test")
    assert ev.tipo == "orden.creada"
    assert ev.orden_id == 42
    assert ev.extra["nombre"] == "Test"
    assert ev.cuando is not None


def test_factory_pago_confirmado_lleva_folio():
    from app.eventos import tipos

    ev = tipos.pago_confirmado(7, folio="abc-123")
    assert ev.orden_id == 7
    assert ev.extra["folio"] == "abc-123"


def test_factory_pago_cancelado_lleva_motivo():
    from app.eventos import tipos

    ev = tipos.pago_cancelado(8, motivo="expired")
    assert ev.extra["motivo"] == "expired"


def test_evento_dominio_es_inmutable():
    from app.eventos import tipos

    ev = tipos.orden_creada(1)
    with pytest.raises(Exception):
        ev.orden_id = 2  # frozen dataclass


# ── bus.py ─────────────────────────────────────────────────────────────────


def test_subscribe_crea_queue():
    from app.eventos.bus import Bus

    b = Bus()
    q = b.subscribe("orden.creada")
    assert q.empty()
    assert "orden.creada" in b.stats()


def test_subscribe_acepta_tipo_adhoc():
    """El bus acepta cualquier string como tipo (no solo los oficiales)."""
    from app.eventos.bus import Bus

    b = Bus()
    q = b.subscribe("pago.confirmado")  # usado por el polling de MP
    assert q is not None


def test_publish_llega_al_suscriptor():
    from app.eventos.bus import Bus
    from app.eventos.tipos import orden_creada

    async def main():
        b = Bus()
        q = b.subscribe("orden.creada")
        b.publish(orden_creada(99))
        ev = await asyncio.wait_for(q.get(), timeout=1.0)
        assert ev.orden_id == 99

    asyncio.run(main())


def test_multi_suscriptor_todos_reciben():
    from app.eventos.bus import Bus
    from app.eventos.tipos import orden_creada

    async def main():
        b = Bus()
        q1 = b.subscribe("orden.creada")
        q2 = b.subscribe("orden.creada")
        b.publish(orden_creada(7))
        e1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        e2 = await asyncio.wait_for(q2.get(), timeout=1.0)
        assert e1.orden_id == e2.orden_id == 7

    asyncio.run(main())


def test_publish_devuelve_numero_de_receptores():
    from app.eventos.bus import Bus
    from app.eventos.tipos import orden_creada

    b = Bus()
    assert b.publish(orden_creada(1)) == 0
    b.subscribe("orden.creada")
    b.subscribe("orden.creada")
    b.subscribe("orden.creada")
    assert b.publish(orden_creada(1)) == 3


def test_publish_async_respeta_backpressure():
    from app.eventos.bus import Bus
    from app.eventos.tipos import orden_creada

    async def main():
        b = Bus()
        q = b.subscribe("orden.creada", maxsize=1)
        await b.publish_async(orden_creada(1))

        # La queue ya está llena. publish_async espera a que se consuma.
        async def consumidor():
            await asyncio.sleep(0.05)
            return await q.get()

        cons = asyncio.create_task(consumidor())
        await b.publish_async(orden_creada(2))  # debe desbloquear
        ev = await cons
        assert ev.orden_id == 1

    asyncio.run(main())


def test_publish_sync_con_queue_llena_no_bloquea():
    from app.eventos.bus import Bus
    from app.eventos.tipos import orden_creada

    b = Bus()
    q = b.subscribe("orden.creada", maxsize=1)
    assert b.publish(orden_creada(1)) == 1
    assert b.publish(orden_creada(2)) == 0  # queue llena → drop


def test_unsubscribe_deja_de_recibir():
    from app.eventos.bus import Bus
    from app.eventos.tipos import orden_creada

    b = Bus()
    q = b.subscribe("orden.creada")
    b.unsubscribe("orden.creada", q)
    assert b.publish(orden_creada(1)) == 0


def test_subscribe_all_devuelve_dict_por_tipo():
    from app.eventos.bus import Bus
    from app.eventos.tipos import TODOS_LOS_TIPOS

    b = Bus()
    queues = b.subscribe_all()
    assert set(queues.keys()) == TODOS_LOS_TIPOS
    assert all(q.empty() for q in queues.values())


def test_diferentes_tipos_no_se_mezclan():
    from app.eventos.bus import Bus
    from app.eventos.tipos import orden_creada, pago_confirmado

    async def main():
        b = Bus()
        q_creada = b.subscribe("orden.creada")
        q_pago = b.subscribe("pago.confirmado")
        assert b.stats() == {"orden.creada": 1, "pago.confirmado": 1}
        n1 = b.publish(orden_creada(5))
        n2 = b.publish(pago_confirmado(5, folio="x"))
        assert n1 == 1
        assert n2 == 1
        e1 = await asyncio.wait_for(q_creada.get(), timeout=1.0)
        e2 = await asyncio.wait_for(q_pago.get(), timeout=1.0)
        assert e1.tipo == "orden.creada"
        assert e2.tipo == "pago.confirmado"

    asyncio.run(main())


def test_close_bloquea_publishes():
    from app.eventos.bus import Bus
    from app.eventos.tipos import orden_creada

    b = Bus()
    b.subscribe("orden.creada")
    b.close()
    assert b.publish(orden_creada(1)) == 0


def test_singleton_bus_tiene_suscriptores_persistentes():
    """El bus global persiste entre llamadas (es un singleton del proceso)."""
    from app.eventos import bus
    from app.eventos import tipos

    bus.reset_para_tests()
    bus.bus.subscribe("orden.creada")
    bus.bus.publish(tipos.orden_creada(123))
    assert "orden.creada" in bus.bus.stats()


# ── ui/compartido/estilos.py (badges) ───────────────────────────────────────


def test_metodo_de_modalidad_descompone_correctamente():
    """Mapea cada Modalidad compuesta al MetodoPago que le corresponde."""
    from app.core.estados import Modalidad, MetodoPago
    from app.ui.compartido.estilos import _metodo_de_modalidad

    casos = {
        Modalidad.AUTOSERVICIO_MONEDAS: MetodoPago.MONEDAS,
        Modalidad.AUTOSERVICIO_POINT: MetodoPago.POINT,
        Modalidad.AUTOSERVICIO_MOSTRADOR: MetodoPago.MOSTRADOR,
        Modalidad.PERSONALIZADO_MONEDAS: MetodoPago.MONEDAS,
        Modalidad.PERSONALIZADO_POINT: MetodoPago.POINT,
        Modalidad.PERSONALIZADO_MOSTRADOR: MetodoPago.MOSTRADOR,
    }
    for modalidad, esperado in casos.items():
        assert _metodo_de_modalidad(modalidad) is esperado, (
            f"{modalidad.value} → esperaba {esperado.value}"
        )


def test_badge_modalidad_cubre_todos_los_enums():
    """Cada valor de Modalidad debe generar un badge HTML válido."""
    from app.core.estados import Modalidad
    from app.ui.compartido.estilos import badge_modalidad

    for m in Modalidad:
        html = badge_modalidad(m)
        assert html.startswith('<span class="orden-servicio-badge"')
        assert "background:" in html
        assert "color:" in html


def test_badge_modalidad_acepta_string_invalido_sin_crashear():
    from app.ui.compartido.estilos import badge_modalidad

    html = badge_modalidad("esto-no-es-una-modalidad")
    assert "esto-no-es-una-modalidad" in html


def test_badge_estado_incluye_legacy_y_nuevo():
    """Tanto 'En proceso' (legacy) como 'En-curso' (nuevo) deben tener color."""
    from app.ui.compartido.estilos import badge_estado

    assert "background:" in badge_estado("En proceso")
    assert "background:" in badge_estado("En-curso")
    assert "background:" in badge_estado("Pendiente")
    # Estado desconocido: fallback gris
    html = badge_estado("???")
    assert "#e2e8f0" in html  # color fallback


def test_badge_servicio_color_por_codigo():
    from app.ui.compartido.estilos import badge_servicio

    h1 = badge_servicio("autolavado")
    h2 = badge_servicio("secado")
    h3 = badge_servicio("desconocido")
    assert "Lavar" in h1
    assert "Secar" in h2
    assert h1 != h2  # colores diferentes


def test_badge_metodo_pago_distingue_point_de_terminal():
    from app.ui.compartido.estilos import badge_metodo_pago

    h1 = badge_metodo_pago("autoservicio-point")
    h2 = badge_metodo_pago("autoservicio-terminal")
    assert "Point" in h1
    assert "Terminal" in h2
    assert h1 != h2
