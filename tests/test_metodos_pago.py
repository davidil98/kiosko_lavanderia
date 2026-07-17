"""Tests del strategy de métodos de pago (sin renderizar NiceGUI)."""

import asyncio
import sys
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(autouse=True)
def _db_tmp(tmp_path):
    from app.repo import db
    from app.core import maquinas as cm
    from app.core import loader
    from app.repo import maquinas as repo_maquinas
    from unittest.mock import patch

    db.usar_path_test(tmp_path / "mp.db")
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
    # `ui.notify` necesita un slot NiceGUI activo; en tests lo desactivamos
    with patch("nicegui.ui.notify"):
        yield
    db.usar_path_test(None)


# ── Catálogo ────────────────────────────────────────────────────────────────


def test_catalogo_tiene_3_metodos():
    from app.core.pagos import METODOS_PAGO_DISPONIBLES

    assert len(METODOS_PAGO_DISPONIBLES) == 3


def test_codigos_son_unicos():
    from app.core.pagos import METODOS_PAGO_DISPONIBLES

    codigos = [m.codigo for m in METODOS_PAGO_DISPONIBLES]
    assert len(codigos) == len(set(codigos))


def test_orden_catalogo_es_monedas_primero():
    from app.core.pagos import METODOS_PAGO_DISPONIBLES
    from app.core.estados import MetodoPago

    assert METODOS_PAGO_DISPONIBLES[0].codigo is MetodoPago.MONEDAS


# ── ContextoPago ────────────────────────────────────────────────────────────


def test_contexto_pago_contiene_wizard_y_callbacks():
    from app.core.pagos.estrategia import ContextoPago
    from app.ui.kiosko.wizard import WizardKiosko

    w = WizardKiosko()
    ctx = ContextoPago(wizard=w, on_cancelar=lambda: None, refresh=lambda *a: None)
    assert ctx.wizard is w
    assert callable(ctx.on_cancelar)
    assert callable(ctx.refresh)


# ── MetodoMonedas (sin render) ──────────────────────────────────────────────


def test_monedas_hereda_de_strategy():
    from app.core.pagos.monedas import MetodoMonedas
    from app.core.pagos.estrategia import MetodoPagoStrategy
    from app.core.estados import MetodoPago

    m = MetodoMonedas()
    assert isinstance(m, MetodoPagoStrategy)
    assert m.codigo is MetodoPago.MONEDAS
    assert m.nombre == "Monedas"


# ── MetodoPoint ─────────────────────────────────────────────────────────────


def test_point_hereda_de_strategy():
    from app.core.pagos.point import MetodoPoint
    from app.core.pagos.estrategia import MetodoPagoStrategy
    from app.core.estados import MetodoPago

    m = MetodoPoint()
    assert isinstance(m, MetodoPagoStrategy)
    assert m.codigo is MetodoPago.POINT


# ── MetodoMostrador ──────────────────────────────────────────────────────────


def test_mostrador_hereda_de_strategy():
    from app.core.pagos.mostrador import MetodoMostrador
    from app.core.pagos.estrategia import MetodoPagoStrategy
    from app.core.estados import MetodoPago

    m = MetodoMostrador()
    assert isinstance(m, MetodoPagoStrategy)
    assert m.codigo is MetodoPago.MOSTRADOR


# ── Flujo end-to-end: MetodoMonedas confirma pago ──────────────────────────


def test_monedas_confirma_pago_publica_en_bus_y_persiste():
    from app.core.pagos.monedas import MetodoMonedas, _confirmar
    from app.core.pagos.estrategia import ContextoPago
    from app.core.estados import MetodoPago
    from app.eventos.bus import bus
    from app.eventos.tipos import TIPO_PAGO_CONFIRMADO
    from app.repo import transacciones
    from app.ui.kiosko.wizard import WizardKiosko

    async def main():
        # Crear orden en procesando-pago
        oid = await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Autolavado",
            peso_kg=3.0,
            nombre_cliente="Test",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )
        await transacciones.aprobar_peso(oid, 3.0, "Moi")
        w = (
            WizardKiosko()
            .seleccionar_servicio("autolavado")
            .confirmar_nombre()
            .capturar_peso(3.0)
        )
        from dataclasses import replace

        w = replace(w, metodo=MetodoPago.MONEDAS, ultimo_id_transaccion=oid, dinero=45)
        # Suscribir al bus antes de confirmar
        cola = bus.subscribe(TIPO_PAGO_CONFIRMADO)

        ctx = ContextoPago(wizard=w, on_cancelar=lambda: None, refresh=lambda *a: None)
        await _confirmar(ctx)

        ev = await asyncio.wait_for(cola.get(), timeout=1.0)
        # `pago_confirmado()` retorna un EventoDominio (dataclass)
        assert ev.orden_id == oid
        t = await transacciones.obtener_por_id(oid)
        assert t["estado"] == "Pendiente"

    asyncio.run(main())


def test_monedas_maneja_id_invalido_sin_crashear():
    """Si la fila ya no existe, _confirmar notifica y resetea el wizard."""
    from app.core.pagos.monedas import _confirmar
    from app.core.pagos.estrategia import ContextoPago
    from app.core.estados import MetodoPago
    from app.ui.kiosko.wizard import WizardKiosko
    from dataclasses import replace

    async def main():
        w = (
            WizardKiosko()
            .seleccionar_servicio("autolavado")
            .confirmar_nombre()
            .capturar_peso(3.0)
        )
        w = replace(
            w, metodo=MetodoPago.MONEDAS, ultimo_id_transaccion=99999, dinero=45
        )
        ctx = ContextoPago(wizard=w, on_cancelar=lambda: None, refresh=lambda *a: None)
        # No debe crashear aunque la fila no exista
        await _confirmar(ctx)

    asyncio.run(main())


# ── Flujo end-to-end: MetodoPoint ───────────────────────────────────────────


def test_point_delega_a_adaptador_y_marca_pendiente_pago():
    from app.core.pagos.point import _iniciar_cobro_point
    from app.core.pagos.estrategia import ContextoPago
    from app.core.estados import MetodoPago
    from app.repo import transacciones
    from app.ui.kiosko.wizard import WizardKiosko
    from dataclasses import replace

    async def main():
        # Crear orden en procesando-pago
        oid = await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Autolavado",
            peso_kg=3.0,
            nombre_cliente="Test",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )
        await transacciones.aprobar_peso(oid, 3.0, "Moi")
        w = (
            WizardKiosko()
            .seleccionar_servicio("autolavado")
            .confirmar_nombre()
            .capturar_peso(3.0)
        )
        w = replace(w, metodo=MetodoPago.POINT, ultimo_id_transaccion=oid)
        ctx = ContextoPago(wizard=w, on_cancelar=lambda: None, refresh=lambda *a: None)

        with patch(
            "app.core.pagos.point.asyncio.to_thread",
            return_value={"id": "mp_xyz_123"},
        ):
            await _iniciar_cobro_point(ctx)

        t = await transacciones.obtener_por_id(oid)
        assert t["estado"] == "Pendiente-pago"
        assert t["modalidad"] == "autoservicio-point"
        assert t["mp_order_id"] == "mp_xyz_123"

    asyncio.run(main())


def test_point_error_de_red_no_modifica_la_orden():
    from app.core.pagos.point import _iniciar_cobro_point
    from app.core.pagos.estrategia import ContextoPago
    from app.core.estados import MetodoPago
    from app.repo import transacciones
    from app.ui.kiosko.wizard import WizardKiosko
    from dataclasses import replace

    async def main():
        oid = await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Autolavado",
            peso_kg=3.0,
            nombre_cliente="Test",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )
        await transacciones.aprobar_peso(oid, 3.0, "Moi")
        w = (
            WizardKiosko()
            .seleccionar_servicio("autolavado")
            .confirmar_nombre()
            .capturar_peso(3.0)
        )
        w = replace(w, metodo=MetodoPago.POINT, ultimo_id_transaccion=oid)
        ctx = ContextoPago(wizard=w, on_cancelar=lambda: None, refresh=lambda *a: None)

        with patch(
            "app.core.pagos.point.asyncio.to_thread",
            return_value={},  # MP devolvió error / sin id
        ):
            await _iniciar_cobro_point(ctx)

        t = await transacciones.obtener_por_id(oid)
        # El estado NO debe cambiar
        assert t["estado"] == "Procesando-pago"

    asyncio.run(main())


# ── Flujo end-to-end: MetodoMostrador ──────────────────────────────────────


def test_mostrador_marca_pendiente_pago_y_espera_admin():
    from app.core.pagos.mostrador import _solicitar_pago_mostrador
    from app.core.pagos.estrategia import ContextoPago
    from app.core.estados import MetodoPago
    from app.repo import transacciones
    from app.ui.kiosko.wizard import WizardKiosko
    from dataclasses import replace

    async def main():
        oid = await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Pers. Ropa",
            peso_kg=2.0,
            nombre_cliente="Test",
            duracion_estimada_min=60,
            modalidad="personalizado",
        )
        await transacciones.aprobar_peso(oid, 2.0, "Moi")
        w = (
            WizardKiosko()
            .seleccionar_servicio("pers_ropa")
            .confirmar_nombre()
            .capturar_peso(2.0)
        )
        w = replace(w, metodo=MetodoPago.MOSTRADOR, ultimo_id_transaccion=oid)
        ctx = ContextoPago(wizard=w, on_cancelar=lambda: None, refresh=lambda *a: None)

        await _solicitar_pago_mostrador(ctx)

        t = await transacciones.obtener_por_id(oid)
        assert t["estado"] == "Pendiente-pago"
        assert t["modalidad"] == "personalizado-mostrador"

    asyncio.run(main())
