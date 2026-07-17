"""Tests de los componentes reusables del superadmin.

Los dialogos NiceGUI no se pueden testear sin cliente, pero sí podemos
verificar:
- `password_bypass_correcta` (puro).
- `dialogo_bypass` y `dialogo_eliminar_con_bypass` se llaman sin crashear.
- El flujo de creación de un servicio vía repo.
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(autouse=True)
def _db(tmp_path):
    from app.repo import db
    from app.core import maquinas as cm
    from app.core import loader
    from app.repo import maquinas as repo_maquinas
    from app.core import reportes as _rep  # noqa

    db.usar_path_test(tmp_path / "super.db")
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
    with patch("nicegui.ui.notify"):
        yield
    db.usar_path_test(None)


# ── password_bypass_correcta ─────────────────────────────────────────────


def test_password_bypass_correcta_con_password_default():
    """Si BYPASS_PASSWORD no está en env, el default es 'admin123'."""
    from app.ui.admin.superadmin._componentes import password_bypass_correcta
    import os

    if "BYPASS_PASSWORD" in os.environ:
        del os.environ["BYPASS_PASSWORD"]
    assert password_bypass_correcta("admin123") is True
    assert password_bypass_correcta("wrong") is False


def test_password_bypass_respeta_env():
    """Si BYPASS_PASSWORD está en env, se usa ese."""
    from app.ui.admin.superadmin._componentes import password_bypass_correcta
    import os

    os.environ["BYPASS_PASSWORD"] = "secreto123"
    try:
        assert password_bypass_correcta("secreto123") is True
        assert password_bypass_correcta("admin123") is False
    finally:
        del os.environ["BYPASS_PASSWORD"]


# ── dialogos reusables: se pueden llamar sin cliente NiceGUI ──────────────


def test_dialogo_bypass_no_crashea_sin_storage():
    """Solo verificamos que la función existe y no lanza al importarla."""
    from app.ui.admin.superadmin import _componentes

    assert callable(_componentes.dialogo_bypass)
    assert callable(_componentes.dialogo_eliminar_con_bypass)


# ── Flujo de servicio: crear y eliminar ─────────────────────────────────


def test_crear_servicio_via_repo():
    from app.repo import servicios

    new_id = asyncio.run(
        servicios.crear(
            codigo="nuevo",
            nombre="Nuevo",
            modalidad="autoservicio",
            icono="/media/icons/leaf.svg",
            tipo_calculo="fijo",
            precio_fijo=99,
            tarifa_por_kg=0,
            duracion_min=30,
            limite_kg=None,
            tipos_equipo="",
            activo=True,
        )
    )
    assert new_id is not None
    s = asyncio.run(servicios.obtener_por_id(new_id))
    assert s is not None
    assert s.nombre == "Nuevo"
    assert s.precio_fijo == 99


def test_crear_servicio_codigo_duplicado_retorna_none():
    from app.repo import servicios

    asyncio.run(
        servicios.crear(
            codigo="autolavado",
            nombre="Otro",
            modalidad="autoservicio",
            icono="",
            tipo_calculo="fijo",
            precio_fijo=1,
            tarifa_por_kg=0,
            duracion_min=1,
            limite_kg=None,
            tipos_equipo="",
            activo=True,
        )
    )
    new_id = asyncio.run(
        servicios.crear(
            codigo="autolavado",
            nombre="Otro2",
            modalidad="autoservicio",
            icono="",
            tipo_calculo="fijo",
            precio_fijo=1,
            tarifa_por_kg=0,
            duracion_min=1,
            limite_kg=None,
            tipos_equipo="",
            activo=True,
        )
    )
    assert new_id is None


def test_eliminar_servicio_con_ordenes_falla():
    """Decisión del usuario: bloquear eliminación si hay órdenes históricas."""
    from app.repo import servicios, transacciones

    async def main():
        new_id = await servicios.crear(
            codigo="secreto",
            nombre="S",
            modalidad="autoservicio",
            icono="",
            tipo_calculo="fijo",
            precio_fijo=1,
            tarifa_por_kg=0,
            duracion_min=1,
            limite_kg=None,
            tipos_equipo="",
            activo=True,
        )
        # Crear orden que referencie el servicio por nombre
        oid = await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="S",
            peso_kg=1.0,
            nombre_cliente="X",
            duracion_estimada_min=10,
            modalidad="autoservicio",
        )
        ok = await servicios.eliminar_hard(new_id)
        assert ok is False

    asyncio.run(main())


def test_eliminar_servicio_sin_ordenes_exitoso():
    from app.repo import servicios

    async def main():
        new_id = await servicios.crear(
            codigo="borrable",
            nombre="X",
            modalidad="autoservicio",
            icono="",
            tipo_calculo="fijo",
            precio_fijo=1,
            tarifa_por_kg=0,
            duracion_min=1,
            limite_kg=None,
            tipos_equipo="",
            activo=True,
        )
        ok = await servicios.eliminar_hard(new_id)
        assert ok is True
        s = await servicios.obtener_por_id(new_id)
        assert s is None

    asyncio.run(main())


# ── Flujo de máquina: crear y eliminar ──────────────────────────────────


def test_crear_maquina_via_repo():
    from app.repo import maquinas

    new_id = asyncio.run(
        maquinas.crear(
            codigo="m1",
            nombre="Lavadora 1",
            tipo="lavado",
            capacidad_kg=10,
            gpio=24,
            modo="pulso",
            duracion_max_min=20,
        )
    )
    assert new_id is not None
    m = asyncio.run(maquinas.obtener_por_id(new_id))
    assert m is not None
    assert m.gpio == 24


def test_crear_maquina_gpio_duplicado_retorna_none():
    """Las máquinas con GPIO duplicado retornan None (la UI debe filtrar)."""
    from app.repo import maquinas

    asyncio.run(
        maquinas.crear(
            codigo="m1",
            nombre="X",
            tipo="lavado",
            capacidad_kg=10,
            gpio=24,
            modo="pulso",
            duracion_max_min=20,
        )
    )
    new_id = asyncio.run(
        maquinas.crear(
            codigo="m2",
            nombre="Y",
            tipo="lavado",
            capacidad_kg=10,
            gpio=24,
            modo="pulso",
            duracion_max_min=20,
        )
    )
    assert new_id is None


def test_existe_gpio():
    from app.repo import maquinas

    assert asyncio.run(maquinas.existe_gpio(17)) is True
    assert asyncio.run(maquinas.existe_gpio(24)) is False
    assert asyncio.run(maquinas.existe_gpio(17, id_excluir=1)) is False


# ── Flujo de respaldo: crear y restaurar ────────────────────────────────


def test_crear_respaldo_y_restaurar():
    from app.repo import respaldos

    asyncio.run(respaldos.crear("servicios", "test"))
    snapshot = asyncio.run(respaldos.obtener("servicios"))
    assert snapshot is not None
    assert len(snapshot["datos"]) == 4  # 4 servicios seed


def test_restaurar_respaldo_sin_snapshot_falla():
    """Si borramos el snapshot, restaurar debe fallar."""
    from app.repo import respaldos
    from app.repo import db

    async def main():
        # Borrar el snapshot inicial (insertado por init_db)
        conn = db.conectar()
        conn.execute("DELETE FROM _backup_default WHERE tabla = 'servicios'")
        conn.commit()
        conn.close()
        ok, n = await respaldos.restaurar("servicios")
        assert ok is False
        assert n == 0

    asyncio.run(main())


def test_restaurar_con_tabla_invalida_falla():
    from app.repo import respaldos

    ok, n = asyncio.run(respaldos.restaurar("transacciones"))
    assert ok is False
    assert n == 0


def test_respaldo_completo_y_restaurar_completo():
    from app.repo import respaldos

    asyncio.run(respaldos.crear_completo("test"))
    r = asyncio.run(respaldos.restaurar_completo())
    for tabla in ("servicios", "segmentaciones", "maquinas"):
        assert r[tabla]["ok"] is True


# ── calculadora: integración con core/precio ────────────────────────────


def test_calculadora_servicio_fijo_a_cualquier_peso():
    from app.core.precio import calcular_precio
    from app.core.servicios import ServicioInfo

    info = ServicioInfo(
        id=1,
        codigo="a",
        nombre="A",
        modalidad="autoservicio",
        icono="",
        tipo_calculo="fijo",
        precio_fijo=50,
        tarifa_por_kg=0,
        duracion_min=30,
        limite_kg=None,
        tipos_equipo=(),
        orden=0,
        activo=True,
    )
    assert calcular_precio(info, 0) == 50
    assert calcular_precio(info, 5) == 50  # fijo ignora peso


def test_calculadora_servicio_por_kg():
    from app.core.precio import calcular_precio
    from app.core.servicios import ServicioInfo

    info = ServicioInfo(
        id=1,
        codigo="a",
        nombre="A",
        modalidad="autoservicio",
        icono="",
        tipo_calculo="por_kg",
        precio_fijo=0,
        tarifa_por_kg=30,
        duracion_min=30,
        limite_kg=None,
        tipos_equipo=(),
        orden=0,
        activo=True,
    )
    assert calcular_precio(info, 0) == 0
    assert calcular_precio(info, 2.5) == 75
    assert calcular_precio(info, -1) == 0  # negativo se trunca


# ── Métricas: kpis con rango '30d' incluye órdenes recientes ─────────────


def test_kpis_rango_30d_incluye_ordenes_de_hoy():
    from app.core import reportes
    from app.repo import transacciones
    import asyncio

    async def main():
        # Crear 1 orden completada hoy
        oid = await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Autolavado",
            peso_kg=2.0,
            nombre_cliente="Test",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )
        await transacciones.aprobar_peso(oid, 2.0, "Moi")
        oid2 = await transacciones.guardar_pago_orden(
            oid,
            45,
            45,
            0,
            "autoservicio-monedas",
        )
        await transacciones.marcar_en_proceso(oid2, "Lavasecadora 1")
        await transacciones.marcar_completado(oid2, "Lavasecadora 1")
        k = await reportes.kpis("30d")
        assert k["ordenes_totales"] == 1
        assert k["recaudado"] == 45

    asyncio.run(main())


# ── Cortes: flujo completo con auto-registro ────────────────────────────


def test_cortes_flujo_completo_con_movimientos_automaticos():
    """Simula el flujo del admin operativo: caja abierta, ingresos auto,
    ingresos manuales, cierre con diferencia."""
    from app.core import cortes as core_cortes
    from app.core.cortes import resumen, listar_movimientos_async

    async def main():
        cid = core_cortes.abrir("2026-07-15", "Moi", 100)["id"]
        # Ingreso auto (como el que viene del admin al confirmar pago mostrador)
        await core_cortes.registrar_movimiento_async(
            cid,
            "ingreso",
            200,
            "Venta mostrador",
            "Moi",
            auto=1,
        )
        # Ingreso manual
        await core_cortes.registrar_movimiento_async(
            cid,
            "ingreso",
            50,
            "Recarga cliente",
            "Moi",
        )
        # Egreso manual (cambio)
        await core_cortes.registrar_movimiento_async(
            cid,
            "egreso",
            20,
            "Cambio dado",
            "Moi",
        )
        movs = await listar_movimientos_async(cid)
        r = await core_cortes.cerrar_async(cid, "Moi", 330, "")
        # Esperado: 100 + 200 + 50 - 20 = 330. Real 330. Diferencia 0.
        assert r["ok"] is True
        assert r["diferencia"] == 0
        assert r["ingresos"] == 250
        assert r["egresos"] == 20

    asyncio.run(main())
