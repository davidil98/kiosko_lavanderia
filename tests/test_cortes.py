"""Tests de la lógica de cortes de caja (`core/cortes.py`)."""

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(autouse=True)
def _db(tmp_path):
    from app.repo import db

    db.usar_path_test(tmp_path / "cortes.db")
    db.init_db()
    yield
    db.usar_path_test(None)


# ── abrir / cerrar / registrar movimiento ────────────────────────────────


def test_abrir_corte_exitoso():
    from app.core.cortes import abrir

    r = abrir("2026-07-15", "Moi", 100)
    assert r["ok"] is True
    assert r["id"] is not None
    assert r["id"] > 0


def test_abrir_saldo_inicial_negativo_falla():
    from app.core.cortes import abrir

    r = abrir("2026-07-15", "Moi", -10)
    assert r["ok"] is False


def test_abrir_dos_veces_falla():
    """Solo puede haber un corte abierto a la vez."""
    from app.core.cortes import abrir

    r1 = abrir("2026-07-15", "Moi", 0)
    assert r1["ok"] is True
    r2 = abrir("2026-07-15", "Moi", 50)
    assert r2["ok"] is False


def test_registrar_ingreso_y_egreso():
    from app.core.cortes import abrir, registrar_movimiento

    corte = abrir("2026-07-15", "Moi", 100)
    r1 = registrar_movimiento(corte["id"], "ingreso", 50, "Venta 1", "Moi")
    assert r1["ok"] is True
    r2 = registrar_movimiento(corte["id"], "egreso", 20, "Cambio dado", "Moi")
    assert r2["ok"] is True


def test_registrar_monto_invalido_falla():
    from app.core.cortes import abrir, registrar_movimiento

    corte = abrir("2026-07-15", "Moi", 100)
    r = registrar_movimiento(corte["id"], "ingreso", 0, "Venta", "Moi")
    assert r["ok"] is False
    r2 = registrar_movimiento(corte["id"], "ingreso", -5, "Venta", "Moi")
    assert r2["ok"] is False


def test_registrar_tipo_invalido_falla():
    from app.core.cortes import abrir, registrar_movimiento

    corte = abrir("2026-07-15", "Moi", 100)
    r = registrar_movimiento(corte["id"], "otro", 50, "X", "Moi")
    assert r["ok"] is False


def test_registrar_concepto_vacio_falla():
    from app.core.cortes import abrir, registrar_movimiento

    corte = abrir("2026-07-15", "Moi", 100)
    r = registrar_movimiento(corte["id"], "ingreso", 50, "  ", "Moi")
    assert r["ok"] is False


def test_cerrar_calcula_esperado_y_diferencia():
    from app.core.cortes import abrir, cerrar, registrar_movimiento

    cid = abrir("2026-07-15", "Moi", 100)["id"]
    registrar_movimiento(cid, "ingreso", 50, "Venta 1", "Moi")
    registrar_movimiento(cid, "ingreso", 30, "Venta 2", "Moi")
    registrar_movimiento(cid, "egreso", 20, "Cambio", "Moi")
    # Esperado = 100 + 50 + 30 - 20 = 160
    r = cerrar(cid, "Moi", 160, "Sin novedad")
    assert r["ok"] is True
    assert r["saldo_esperado"] == 160
    assert r["diferencia"] == 0
    assert r["ingresos"] == 80
    assert r["egresos"] == 20


def test_cerrar_con_diferencia_positiva():
    """Sobró más dinero del esperado (sobrante)."""
    from app.core.cortes import abrir, cerrar, registrar_movimiento

    cid = abrir("2026-07-15", "Moi", 100)["id"]
    registrar_movimiento(cid, "ingreso", 50, "Venta", "Moi")
    # Esperado = 150, real = 160, diferencia = +10
    r = cerrar(cid, "Moi", 160, "")
    assert r["saldo_esperado"] == 150
    assert r["diferencia"] == 10


def test_cerrar_con_diferencia_negativa():
    """Faltó dinero (faltante)."""
    from app.core.cortes import abrir, cerrar, registrar_movimiento

    cid = abrir("2026-07-15", "Moi", 100)["id"]
    registrar_movimiento(cid, "ingreso", 50, "Venta", "Moi")
    # Esperado = 150, real = 145, diferencia = -5
    r = cerrar(cid, "Moi", 145, "Faltante")
    assert r["diferencia"] == -5


def test_cerrar_con_saldo_inicial_negativo_falla():
    from app.core.cortes import abrir, cerrar

    cid = abrir("2026-07-15", "Moi", 100)["id"]
    r = cerrar(cid, "Moi", -10, "")
    assert r["ok"] is False


def test_cerrar_ya_cerrado_falla():
    from app.core.cortes import abrir, cerrar

    cid = abrir("2026-07-15", "Moi", 100)["id"]
    cerrar(cid, "Moi", 100, "")
    r2 = cerrar(cid, "Moi", 100, "")
    assert r2["ok"] is False


# ── resumen (helper de UI) ─────────────────────────────────────────────────


def test_resumen_con_corte_vacio():
    from app.core.cortes import abrir, resumen

    cid = abrir("2026-07-15", "Moi", 100)
    # Necesitamos el dict completo, no solo el id
    from app.repo import cortes as repo

    corte = repo._listar(limite=1)[0]
    r = resumen(corte, [])
    assert r["saldo_inicial"] == 100
    assert r["ingresos"] == 0
    assert r["egresos"] == 0
    assert r["esperado"] == 100
    assert r["saldo_real"] is None
    assert r["diferencia"] is None


def test_resumen_tras_cerrar():
    from app.core.cortes import abrir, cerrar, resumen, registrar_movimiento
    from app.repo import cortes as repo

    cid = abrir("2026-07-15", "Moi", 50)["id"]
    registrar_movimiento(cid, "ingreso", 200, "Ventas", "Moi")
    registrar_movimiento(cid, "egreso", 30, "Cambio", "Moi")
    cerrar(cid, "Moi", 215, "Sobró 5")
    corte = repo._listar(limite=1)[0]
    movs = repo._listar_movimientos(cid)
    r = resumen(corte, movs)
    assert r["saldo_inicial"] == 50
    assert r["ingresos"] == 200
    assert r["egresos"] == 30
    assert r["esperado"] == 220
    assert r["saldo_real"] == 215
    assert r["diferencia"] == -5


# ── Listar cortes cerrados ───────────────────────────────────────────────


def test_listar_cerrados_ordenados_reciente_a_viejo():
    from app.core.cortes import abrir, cerrar, listar_cerrados_async
    import asyncio

    async def main():
        # Abrir y cerrar 3 cajas
        for i, (s_ini, s_real) in enumerate([(50, 55), (0, 0), (100, 90)]):
            cid = abrir(f"2026-07-{15 + i}", "Moi", s_ini)["id"]
            cerrar(cid, "Moi", s_real, "")
        cerradas = await listar_cerrados_async(10)
        assert len(cerradas) == 3
        # La más reciente es la última creada
        assert cerradas[0]["fecha"] == "2026-07-17"

    asyncio.run(main())


def test_obtener_activo_devuelve_none_si_no_hay_caja():
    from app.core.cortes import obtener_activo_async
    import asyncio

    async def main():
        c = await obtener_activo_async()
        assert c is None

    asyncio.run(main())


def test_obtener_activo_devuelve_el_correto():
    from app.core.cortes import abrir, obtener_activo_async
    import asyncio

    async def main():
        cid = abrir("2026-07-15", "Moi", 100)["id"]
        c = await obtener_activo_async()
        assert c is not None
        assert c["id"] == cid
        assert c["saldo_inicial"] == 100

    asyncio.run(main())


def test_movimiento_automatico():
    """Pagos en efectivo del admin operativo se auto-registran con `auto=1`."""
    from app.core.cortes import abrir, registrar_movimiento

    cid = abrir("2026-07-15", "Moi", 0)["id"]
    r = registrar_movimiento(
        cid,
        "ingreso",
        100,
        "Venta mostrador",
        "Moi",
        auto=1,
    )
    assert r["ok"] is True
    assert r["id"] is not None
