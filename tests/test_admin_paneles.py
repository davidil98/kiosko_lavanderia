"""Tests de los handlers de los 3 paneles operativos.

Los handlers son funciones async en `app/ui/admin/*.py` que:
1. Reciben un dict de orden.
2. Modifican la BD via `repo/transacciones` (o `core/transiciones`).
3. Publican eventos en el bus.

No renderizamos NiceGUI aquí; validamos la lógica de negocio de los
handlers y la integración con el bus.
"""

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(autouse=True)
def _db_tmp(tmp_path):
    from app.repo import db
    from app.core import maquinas as cm
    from app.core import loader
    from app.repo import maquinas as repo_maquinas
    from unittest.mock import MagicMock, patch

    db.usar_path_test(tmp_path / "admin.db")
    db.init_db()
    cm.set_cargador(
        lambda: {
            m.codigo: cm.Equipo(
                codigo=m.codigo,
                nombre=m.nombre,
                tipo=m.tipo,
                capacidad_kg=m.capacidad_kg,
                gpio=m.gpio,
                modo=m.modo,
                duracion_max_min=m.duracion_max_min,
            )
            for m in repo_maquinas._listar(solo_activas=True)
        }
    )
    loader.instalar_como_defaults()
    # El bus es singleton; lo recreamos via reset_para_tests y luego
    # actualizamos el símbolo en todos los módulos que lo importaron.
    from app.eventos import bus as _bus

    _bus.reset_para_tests()
    import app.eventos.bus as _bb
    import app.ui.admin.operativo as _op
    import app.ui.admin.autoservicio as _as
    import app.ui.admin.personalizado as _pe

    _op.bus = _bus.bus
    _as.bus = _bus.bus
    _pe.bus = _bus.bus
    # Los handlers llaman a usuario_actual() y ui.notify, que necesitan
    # un cliente NiceGUI. Mockeamos ambos.
    mock_storage = {"authenticated": True, "usuario": "Moi"}
    mock_app = MagicMock()
    mock_app.storage.user = mock_storage
    with patch("nicegui.ui.notify"), patch("app.ui.compartido.auth.app", mock_app):
        yield
    db.usar_path_test(None)


# ── Operativo: aprobar / rechazar peso ─────────────────────────────────────


def test_aprobar_paso_cambia_estado_y_publica_evento():
    from app.eventos.bus import bus
    from app.eventos.tipos import TIPO_PAGO_CONFIRMADO, TIPO_PESO_APROBADO
    from app.repo import transacciones
    from app.ui.admin.operativo import _aprobar_peso, _confirmar_pago_mostrador

    async def main():
        oid = await transacciones.crear_orden_pendiente_pago(
            tipo_servicio="Pers. Ropa",
            peso_kg=2.0,
            monto=60,
            nombre_cliente="Test",
            duracion_estimada_min=60,
            modalidad="personalizado",
        )
        orden = await transacciones.obtener_por_id(oid)
        cola = bus.subscribe(TIPO_PAGO_CONFIRMADO)

        await _confirmar_pago_mostrador(orden)

        t = await transacciones.obtener_por_id(oid)
        assert t["estado"] == "Pendiente"
        ev = await asyncio.wait_for(cola.get(), timeout=1.0)
        assert ev.orden_id == oid
        assert ev.extra["metodo"] == "mostrador"

    asyncio.run(main())


def test_cancelar_pago_elimina_y_publica_dos_eventos():
    from app.eventos.bus import bus
    from app.eventos.tipos import TIPO_ORDEN_CANCELADA, TIPO_PAGO_CANCELADO
    from app.repo import transacciones
    from app.ui.admin.operativo import _cancelar_pago

    async def main():
        from app.eventos import bus as _b

        oid = await transacciones.crear_orden_pendiente_pago(
            tipo_servicio="Pers. Ropa",
            peso_kg=2.0,
            monto=60,
            nombre_cliente="Test",
            duracion_estimada_min=60,
            modalidad="personalizado",
        )
        orden = await transacciones.obtener_por_id(oid)
        cola1 = bus.subscribe(TIPO_PAGO_CANCELADO)
        cola2 = bus.subscribe(TIPO_ORDEN_CANCELADA)
        while not cola1.empty():
            cola1.get_nowait()
        while not cola2.empty():
            cola2.get_nowait()
        await _cancelar_pago(orden)

        assert await transacciones.obtener_por_id(oid) is None
        ev1 = await asyncio.wait_for(cola1.get(), timeout=1.0)
        ev2 = await asyncio.wait_for(cola2.get(), timeout=1.0)
        assert ev1.orden_id == oid
        assert ev2.orden_id == oid

    asyncio.run(main())


# ── Autoservicio: asignar y completar ──────────────────────────────────────


def test_listar_para_asignar_autoservicio_filtra_por_modalidad():
    from app.core.estados import EstadoOrden
    from app.repo import transacciones

    async def main():
        oid = await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Autolavado",
            peso_kg=3.0,
            nombre_cliente="Ana",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )
        await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Pers. Ropa",
            peso_kg=2.0,
            nombre_cliente="Pers",
            duracion_estimada_min=60,
            modalidad="personalizado",
        )
        await transacciones.crear_orden_pendiente_pago(
            tipo_servicio="Pers. Ropa",
            peso_kg=2.0,
            monto=60,
            nombre_cliente="Pers2",
            duracion_estimada_min=60,
            modalidad="personalizado",
        )
        lista = await transacciones.listar_para_asignar_autoservicio()
        # Solo autoservicio en Pendiente / En proceso
        for o in lista:
            assert o["modalidad"].startswith("autoservicio") or o["modalidad"] == ""

    asyncio.run(main())


def test_marcar_en_proceso_y_completado_flujo_autoservicio():
    from app.repo import transacciones

    async def main():
        oid = await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Autolavado",
            peso_kg=3.0,
            nombre_cliente="Auto",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )
        await transacciones.aprobar_peso(oid, 3.0, "Moi")
        oid2 = await transacciones.guardar_pago_orden(
            oid,
            45,
            45,
            0,
            "autoservicio-monedas",
        )
        await transacciones.marcar_en_proceso(oid2, "Lavasecadora 1")
        t = await transacciones.obtener_por_id(oid2)
        assert t["estado"] == "En proceso"
        assert t["id_equipo"] == "Lavasecadora 1"
        await transacciones.marcar_completado(oid2, "Lavasecadora 1")
        t = await transacciones.obtener_por_id(oid2)
        assert t["estado"] == "Completado"

    asyncio.run(main())


# ── Personalizado: avance de etapas ────────────────────────────────────────


def test_avanzar_etapas_kanban():
    from app.core.estados import EtapaKanban
    from app.repo import transacciones

    async def main():
        oid = await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Pers. Ropa",
            peso_kg=2.0,
            nombre_cliente="Pers",
            duracion_estimada_min=60,
            modalidad="personalizado",
        )
        # Inicia en Recibido (default)
        t = await transacciones.obtener_por_id(oid)
        assert t["etapa_kanban"] == "Recibido"

        await transacciones.actualizar_etapa_kanban(oid, EtapaKanban.ALISTANDO.value)
        t = await transacciones.obtener_por_id(oid)
        assert t["etapa_kanban"] == "Alistando"
        assert t["estado"] == "En proceso"

        await transacciones.actualizar_etapa_kanban(
            oid, EtapaKanban.LISTO_ENTREGA.value
        )
        t = await transacciones.obtener_por_id(oid)
        assert t["etapa_kanban"] == "Listo para Entrega"
        assert t["estado"] == "En proceso"

        await transacciones.actualizar_etapa_kanban(oid, "Entregado")
        t = await transacciones.obtener_por_id(oid)
        assert t["etapa_kanban"] == "Entregado"
        assert t["estado"] == "Completado"

    asyncio.run(main())


def test_listar_personalizadas_devuelve_solo_personalizadas():
    from app.repo import transacciones

    async def main():
        await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Autolavado",
            peso_kg=3.0,
            nombre_cliente="Auto",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )
        await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Pers. Ropa",
            peso_kg=2.0,
            nombre_cliente="Pers",
            duracion_estimada_min=60,
            modalidad="personalizado",
        )
        await transacciones.crear_orden_pendiente_pago(
            tipo_servicio="Pers. Edredón",
            peso_kg=3.0,
            monto=150,
            nombre_cliente="Pers2",
            duracion_estimada_min=90,
            modalidad="personalizado",
        )
        pers = await transacciones.listar_personalizadas()
        assert len(pers) == 2
        for o in pers:
            assert o["modalidad"].startswith("personalizado")

    asyncio.run(main())


# ── Integración: el bus entrega eventos al kiosko cuando admin aprueba ─────


def test_evento_peso_aprobado_es_recibido_por_kiosko():
    """Simula el flujo: kiosko crea orden pendiente-peso → admin aprueba
    → evento llega al kiosko via bus."""
    from app.eventos.bus import bus
    from app.eventos.tipos import TIPO_PESO_APROBADO
    from app.repo import transacciones
    from app.ui.admin.operativo import _aprobar_peso

    async def main():
        from app.eventos import bus as _b

        oid = await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Autolavado",
            peso_kg=3.0,
            nombre_cliente="Ana",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )
        # El kiosko se suscribe al bus
        cola_kiosko = bus.subscribe(TIPO_PESO_APROBADO)
        while not cola_kiosko.empty():
            cola_kiosko.get_nowait()
        orden = await transacciones.obtener_por_id(oid)
        await _aprobar_peso(orden)

        ev = await asyncio.wait_for(cola_kiosko.get(), timeout=1.0)
        assert ev.orden_id == oid
        # El kiosko ahora debe mostrar métodos de pago
        t = await transacciones.obtener_por_id(oid)
        assert t["estado"] == "Procesando-pago"

    asyncio.run(main())
