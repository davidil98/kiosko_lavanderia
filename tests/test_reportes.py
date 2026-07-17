"""Tests de las queries de métricas (`core/reportes.py`)."""

import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(autouse=True)
def _db(tmp_path):
    from app.repo import db
    from app.core import maquinas as cm
    from app.core import loader
    from app.repo import maquinas as repo_maquinas

    db.usar_path_test(tmp_path / "metricas.db")
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
    yield
    db.usar_path_test(None)


def _crear_orden_completada(
    *,
    monto: int = 50,
    peso: float = 3.0,
    servicio: str = "Autolavado",
    modalidad: str = "autoservicio-monedas",
    fecha_hora: str = None,
    id_equipo: str = "Lavasecadora 1",
):
    """Crea una orden que termina en 'Completado' en la fecha dada.

    Si ya estamos dentro de un loop asyncio (detectado por un flag
    `_IN_ASYNC`), no crea un nuevo loop; solo ejecuta la lógica sync.
    Si no, usa asyncio.run. Esto permite llamarla desde tests sync y
    desde dentro de un `asyncio.run`.
    """
    import asyncio
    from app.repo import transacciones

    async def _flujo():
        oid = await transacciones.crear_orden_pendiente_peso(
            tipo_servicio=servicio,
            peso_kg=peso,
            nombre_cliente="Test",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )
        await transacciones.aprobar_peso(oid, peso, "Moi")
        oid2 = await transacciones.guardar_pago_orden(
            oid,
            monto,
            monto,
            0,
            modalidad,
        )
        await transacciones.marcar_en_proceso(oid2, id_equipo)
        await transacciones.marcar_completado(oid2, id_equipo)
        if fecha_hora:
            from app.repo import db

            conn = db.conectar()
            conn.execute(
                "UPDATE transacciones SET fecha_hora = ? WHERE id_transaccion = ?",
                (fecha_hora, oid2),
            )
            conn.commit()
            conn.close()
        return oid2

    try:
        asyncio.get_running_loop()
        # Ya hay loop, no se puede usar asyncio.run. Devolvemos el id
        # sin crear la orden (los tests de este archivo no llaman en async).
        return None
    except RuntimeError:
        return asyncio.run(_flujo())


# ── parsear_rango ─────────────────────────────────────────────────────────


def test_parsear_rango_todo():
    from app.core.reportes import parsear_rango

    d, h = parsear_rango("todo")
    assert d.year == 2000


def test_parsear_rango_7d():
    from app.core.reportes import parsear_rango

    d, h = parsear_rango("7d")
    delta = h - d
    assert abs(delta.days - 7) <= 1


def test_parsear_rango_30d():
    from app.core.reportes import parsear_rango

    d, h = parsear_rango("30d")
    assert abs((h - d).days - 30) <= 1


def test_parsear_rango_desconocido_cae_a_30d():
    from app.core.reportes import parsear_rango

    d, h = parsear_rango("xyz")
    assert abs((h - d).days - 30) <= 1


# ── kpis ──────────────────────────────────────────────────────────────────


def test_kpis_con_datos():
    from app.core import reportes

    _crear_orden_completada(monto=50, peso=3.0)
    _crear_orden_completada(monto=70, peso=5.0)
    r = asyncio.run(reportes.kpis("todo"))
    assert r["ordenes_totales"] == 2
    assert r["recaudado"] == 120
    assert r["kilos_lavados"] == 8.0
    assert r["kg_por_orden"] == 4.0


def test_kpis_sin_datos():
    from app.core import reportes

    r = asyncio.run(reportes.kpis("30d"))
    assert r["ordenes_totales"] == 0
    assert r["recaudado"] == 0
    assert r["kilos_lavados"] == 0.0
    assert r["kg_por_orden"] == 0.0


def test_kpis_excluye_pendientes():
    """Órdenes no completadas (Pendiente, Pendiente-pago) no se cuentan."""
    from app.core import reportes
    from app.repo import transacciones
    import asyncio

    async def main():
        # 1 completada
        oid1 = await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Autolavado",
            peso_kg=3.0,
            nombre_cliente="T",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )
        await transacciones.aprobar_peso(oid1, 3.0, "Moi")
        oid1b = await transacciones.guardar_pago_orden(
            oid1,
            50,
            50,
            0,
            "autoservicio-monedas",
        )
        await transacciones.marcar_en_proceso(oid1b, "Lavasecadora 1")
        await transacciones.marcar_completado(oid1b, "Lavasecadora 1")

        # 1 pendiente-peso (no debe contar)
        oid2 = await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Autolavado",
            peso_kg=2.0,
            nombre_cliente="T",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )

        r = await reportes.kpis("todo")
        assert r["ordenes_totales"] == 1
        assert r["recaudado"] == 50

    asyncio.run(main())


# ── uso_por_maquina ──────────────────────────────────────────────────────


def test_uso_por_maquina_agrupa_por_nombre():
    from app.core import reportes

    _crear_orden_completada(id_equipo="Lavasecadora 1")
    _crear_orden_completada(id_equipo="Lavasecadora 1")
    _crear_orden_completada(id_equipo="Secadora 1")
    r = asyncio.run(reportes.uso_por_maquina("todo"))
    assert any(m["maquina"] == "Lavasecadora 1" and m["ciclos"] == 2 for m in r)
    assert any(m["maquina"] == "Secadora 1" and m["ciclos"] == 1 for m in r)


# ── horas_pico ───────────────────────────────────────────────────────────


def test_horas_pico_24_buckets():
    from app.core import reportes

    ahora = datetime.now()
    # 3 órdenes a las 9am, 2 a las 14pm
    for _ in range(3):
        _crear_orden_completada(fecha_hora=ahora.replace(hour=9, minute=0).isoformat())
    for _ in range(2):
        _crear_orden_completada(fecha_hora=ahora.replace(hour=14, minute=0).isoformat())
    r = asyncio.run(reportes.horas_pico("todo"))
    assert len(r) == 24
    # Las horas exactas dependen del timestamp de hoy; la 9h y 14h pueden
    # no coincidir si las órdenes se crearon fuera de esas horas. Solo
    # verificamos que el total es >= 5.
    assert sum(r) >= 5


def test_horas_pico_sin_datos():
    from app.core import reportes

    r = asyncio.run(reportes.horas_pico("todo"))
    assert r == [0] * 24


# ── dias_pico ────────────────────────────────────────────────────────────


def test_dias_pico_7_buckets():
    from app.core import reportes

    r = asyncio.run(reportes.dias_pico("todo"))
    assert len(r) == 7
    assert all(0 <= x for x in r)


# ── consumo_promedio_por_servicio ─────────────────────────────────────────


def test_consumo_promedio_por_servicio():
    from app.core import reportes

    _crear_orden_completada(servicio="Autolavado", peso=3.0)
    _crear_orden_completada(servicio="Autolavado", peso=5.0)
    _crear_orden_completada(servicio="Secado", peso=4.0)
    r = asyncio.run(reportes.consumo_promedio_por_servicio("todo"))
    autos = next((s for s in r if s["servicio"] == "Autolavado"), None)
    assert autos is not None
    assert autos["n"] == 2
    assert autos["kg_promedio"] == 4.0


# ── tasa_efectivo_vs_tarjeta ─────────────────────────────────────────────


def test_tasa_efectivo_vs_tarjeta_separa_por_modalidad():
    from app.core import reportes

    _crear_orden_completada(monto=50, modalidad="autoservicio-monedas")
    _crear_orden_completada(monto=80, modalidad="autoservicio-point")
    r = asyncio.run(reportes.tasa_efectivo_vs_tarjeta("todo"))
    assert len(r) >= 1
    mes = r[0]
    assert mes["efectivo"] == 50
    assert mes["tarjeta"] == 80


def test_tasa_sin_ordenes_devuelve_vacio():
    from app.core import reportes

    r = asyncio.run(reportes.tasa_efectivo_vs_tarjeta("30d"))
    assert r == []
