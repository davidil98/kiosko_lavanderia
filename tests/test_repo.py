"""Tests de la capa de persistencia (repo/).

Cada test usa una DB temporal en tmp_path para no tocar la BD de producción.
"""

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(autouse=True)
def _db_tmp(tmp_path, monkeypatch):
    """Redirige la DB a un archivo temporal durante cada test."""
    from app.repo import db

    db_path = tmp_path / "test.db"
    db.usar_path_test(db_path)
    db.init_db()
    yield
    db.usar_path_test(None)


# ── db: seeds e idempotencia ─────────────────────────────────────────────────


def test_init_db_crea_las_7_tablas():
    from app.repo import db

    conn = db.conectar()
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    tablas = {r["name"] for r in rows}
    esperadas = {
        "transacciones",
        "servicios",
        "segmentaciones",
        "maquinas",
        "_backup_default",
        "cortes_caja",
        "movimientos_caja",
    }
    assert esperadas.issubset(tablas)
    conn.close()


def test_init_db_es_idempotente():
    from app.repo import db

    db.init_db()
    db.init_db()
    db.init_db()
    conn = db.conectar()
    n = conn.execute("SELECT COUNT(*) AS c FROM servicios").fetchone()["c"]
    conn.close()
    assert n == 4  # 4 servicios sembrados


def test_seeds_iniciales():
    from app.repo import db

    conn = db.conectar()
    assert conn.execute("SELECT COUNT(*) AS c FROM servicios").fetchone()["c"] == 4
    assert conn.execute("SELECT COUNT(*) AS c FROM segmentaciones").fetchone()["c"] == 5
    assert conn.execute("SELECT COUNT(*) AS c FROM maquinas").fetchone()["c"] == 4
    assert (
        conn.execute("SELECT COUNT(*) AS c FROM _backup_default").fetchone()["c"] == 3
    )
    conn.close()


def test_migraciones_son_aditivas():
    """Un ALTER TABLE no debe fallar aunque la columna ya exista."""
    from app.repo import db

    db.init_db()  # 2da vez: las columnas ya están
    conn = db.conectar()
    cols = {
        r["name"] for r in conn.execute("PRAGMA table_info(transacciones)").fetchall()
    }
    for esperada in (
        "peso_kg",
        "notas",
        "etapa_kanban",
        "modalidad",
        "numero_transaccion_terminal",
        "validado_por",
        "mp_order_id",
    ):
        assert esperada in cols
    conn.close()


# ── transacciones ────────────────────────────────────────────────────────────


def test_flujo_pendiente_peso_a_pago_en_monedas():
    from app.repo import transacciones

    async def main():
        oid = await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Autolavado",
            peso_kg=3.5,
            nombre_cliente="Ana",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )
        assert oid > 0
        await transacciones.aprobar_peso(oid, 3.6, "Moi")
        t = await transacciones.obtener_por_id(oid)
        assert t["estado"] == "Procesando-pago"
        assert t["peso_kg"] == 3.6
        new_id = await transacciones.guardar_pago_orden(
            oid, 45, 50, 5, "autoservicio-monedas"
        )
        assert new_id == oid
        t = await transacciones.obtener_por_id(oid)
        assert t["estado"] == "Pendiente"
        assert t["dinero_ingresado"] == 50
        assert t["cambio_devuelto"] == 5

    asyncio.run(main())


def test_flujo_pendiente_peso_a_pago_en_point():
    from app.repo import transacciones

    async def main():
        oid = await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Autolavado",
            peso_kg=3.0,
            nombre_cliente="Beto",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )
        await transacciones.aprobar_peso(oid, 3.1, "Moi")
        new_id = await transacciones.marcar_pendiente_pago(
            oid, 45, "autoservicio-point", "mp_999"
        )
        assert new_id == oid
        t = await transacciones.obtener_por_id(oid)
        assert t["estado"] == "Pendiente-pago"
        assert t["mp_order_id"] == "mp_999"
        await transacciones.aprobar_pago_terminal(oid, "12345", "point-polling")
        t = await transacciones.obtener_por_id(oid)
        assert t["estado"] == "Pendiente"
        assert t["numero_transaccion_terminal"] == "12345"

    asyncio.run(main())


def test_rechazar_peso_elimina_la_orden():
    from app.repo import transacciones

    async def main():
        oid = await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Secado",
            peso_kg=2.0,
            nombre_cliente="Caro",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )
        await transacciones.rechazar_peso(oid)
        t = await transacciones.obtener_por_id(oid)
        assert t is None

    asyncio.run(main())


def test_marcar_en_proceso_y_completado():
    from app.repo import transacciones

    async def main():
        oid = await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Autolavado",
            peso_kg=4.0,
            nombre_cliente="Dario",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )
        await transacciones.aprobar_peso(oid, 4.0, "Moi")
        await transacciones.guardar_pago_orden(oid, 45, 45, 0, "autoservicio-monedas")
        await transacciones.marcar_en_proceso(oid, "Lavasecadora 1")
        t = await transacciones.obtener_por_id(oid)
        assert t["estado"] == "En proceso"
        assert t["id_equipo"] == "Lavasecadora 1"
        assert t["inicio_servicio"] is not None
        await transacciones.marcar_completado(oid, "Lavasecadora 1")
        t = await transacciones.obtener_por_id(oid)
        assert t["estado"] == "Completado"

    asyncio.run(main())


def test_cancelar_pago_pendiente_elimina():
    from app.repo import transacciones

    async def main():
        oid = await transacciones.crear_orden_pendiente_pago(
            tipo_servicio="Autolavado",
            peso_kg=3.0,
            monto=45,
            nombre_cliente="Eli",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )
        await transacciones.cancelar_pago_pendiente(oid)
        t = await transacciones.obtener_por_id(oid)
        assert t is None

    asyncio.run(main())


def test_listar_personalizadas_y_etapa_kanban():
    from app.repo import transacciones

    async def main():
        await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Pers. Ropa",
            peso_kg=5.0,
            nombre_cliente="Fer",
            duracion_estimada_min=60,
            modalidad="personalizado",
        )
        oid2 = await transacciones.crear_orden_pendiente_pago(
            tipo_servicio="Pers. Ropa",
            peso_kg=4.0,
            monto=120,
            nombre_cliente="Gaby",
            duracion_estimada_min=60,
            modalidad="personalizado",
        )
        pers = await transacciones.listar_personalizadas()
        assert len(pers) == 2
        await transacciones.actualizar_etapa_kanban(oid2, "Alistando")
        t = await transacciones.obtener_por_id(oid2)
        assert t["etapa_kanban"] == "Alistando"
        assert t["estado"] == "En proceso"

    asyncio.run(main())


def test_contadores_pendientes_y_point():
    from app.repo import transacciones

    async def main():
        for i in range(3):
            await transacciones.crear_orden_pendiente_peso(
                tipo_servicio="Autolavado",
                peso_kg=3.0,
                nombre_cliente=f"C{i}",
                duracion_estimada_min=45,
                modalidad="autoservicio",
            )
        point_id = await transacciones.crear_orden_pendiente_pago(
            tipo_servicio="Autolavado",
            peso_kg=3.0,
            monto=45,
            nombre_cliente="ConPoint",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )
        await transacciones.guardar_mp_order_id(point_id, "mp_abc")
        cnt = await transacciones.contadores_pendientes()
        assert cnt.get("Pendiente-peso", 0) == 3
        assert cnt.get("Pendiente-pago", 0) == 1
        pts = await transacciones.listar_point_pendientes()
        assert len(pts) == 1
        assert pts[0]["mp_order_id"] == "mp_abc"

    asyncio.run(main())


# ── servicios / segmentaciones / maquinas ───────────────────────────────────


def test_crud_servicios():
    from app.repo import servicios

    async def main():
        lista = await servicios.listar()
        assert len(lista) == 4
        autolavado = await servicios.obtener_por_codigo("autolavado")
        assert autolavado is not None
        assert autolavado.nombre == "Autolavado"
        assert autolavado.precio_fijo == 45

        new_id = await servicios.crear(
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
        assert new_id is not None
        dup = await servicios.crear(
            codigo="nuevo",
            nombre="Dup",
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
        assert dup is None  # codigo duplicado

        await servicios.actualizar(
            new_id,
            nombre="Editado",
            tipo_calculo="fijo",
            precio_fijo=88,
            tarifa_por_kg=0,
            duracion_min=20,
            limite_kg=None,
            tipos_equipo="",
            activo=True,
        )
        s = await servicios.obtener_por_id(new_id)
        assert s.nombre == "Editado"
        assert s.precio_fijo == 88

    asyncio.run(main())


def test_eliminar_servicio_con_ordenes_falla():
    from app.repo import servicios, transacciones

    async def main():
        # Crear orden que referencie "Autolavado"
        await transacciones.crear_orden_pendiente_peso(
            tipo_servicio="Autolavado",
            peso_kg=3.0,
            nombre_cliente="ConOrden",
            duracion_estimada_min=45,
            modalidad="autoservicio",
        )
        autolavado = await servicios.obtener_por_codigo("autolavado")
        ok = await servicios.eliminar_hard(autolavado.id)
        assert ok is False  # hay órdenes referenciando

    asyncio.run(main())


def test_crud_segmentaciones_y_listar_por_servicio():
    from app.repo import servicios, segmentaciones

    async def main():
        pers_ropa = await servicios.obtener_por_codigo("pers_ropa")
        segs = await segmentaciones.listar(servicio_id=pers_ropa.id)
        nombres = {s.nombre for s in segs}
        assert "Lava + Seca + Dobla" in nombres
        assert "Solo Lava + Exprime" in nombres
        todas = await segmentaciones.listar()
        assert len(todas) == 5
        s1 = await segmentaciones.obtener_por_id(segs[0].id)
        assert s1 is not None

    asyncio.run(main())


def test_crud_maquinas_y_existe_gpio():
    from app.repo import maquinas

    async def main():
        lista = await maquinas.listar()
        assert len(lista) == 4
        m1 = await maquinas.obtener_por_codigo("lavasecadora_1")
        assert m1.gpio == 17
        assert m1.modo == "pulso"
        new_id = await maquinas.crear(
            codigo="test",
            nombre="Test",
            tipo="lavado",
            capacidad_kg=5,
            gpio=24,
            modo="pulso",
            duracion_max_min=25,
        )
        assert new_id is not None
        # La BD no tiene UNIQUE en gpio; la regla de unicidad la aplica la UI
        # usando `existe_gpio()` antes de crear. Aquí verificamos esa API:
        assert await maquinas.existe_gpio(24) is True
        assert await maquinas.existe_gpio(24, id_excluir=new_id) is False
        assert await maquinas.existe_gpio(17) is True
        assert await maquinas.existe_gpio(17, id_excluir=m1.id) is False
        assert await maquinas.existe_gpio(99) is False

    asyncio.run(main())


# ── cortes de caja ───────────────────────────────────────────────────────────


def test_aprir_cerrar_y_movimiento():
    from app.repo import cortes

    async def main():
        # No debe haber caja abierta
        assert await cortes.obtener_activo() is None
        r = await cortes.abrir("2026-07-12", "Moi", 100)
        assert r["ok"] is True
        cid = r["id"]
        # Intentar abrir otra debe fallar
        r2 = await cortes.abrir("2026-07-12", "Moi", 200)
        assert r2["ok"] is False
        # Registrar movimiento
        m = await cortes.registrar_movimiento(
            cid, "ingreso", 50, "Venta mostrador", "Moi"
        )
        assert m["ok"] is True
        m2 = await cortes.registrar_movimiento(cid, "egreso", 20, "Cambio dado", "Moi")
        assert m2["ok"] is True
        movs = await cortes.listar_movimientos(cid)
        assert len(movs) == 2
        # Cerrar
        c = await cortes.cerrar(cid, "Moi", 130, "")
        assert c["ok"] is True
        assert c["saldo_esperado"] == 130  # 100 + 50 - 20
        assert c["diferencia"] == 0
        # Tras cerrar no debe haber caja activa
        assert await cortes.obtener_activo() is None

    asyncio.run(main())


def test_listar_cortes_incluye_cerrados():
    from app.repo import cortes

    async def main():
        r = await cortes.abrir("2026-07-12", "Moi", 0)
        cid = r["id"]
        await cortes.cerrar(cid, "Moi", 0, "test")
        historial = await cortes.listar()
        assert any(c["id"] == cid and c["estado"] == "cerrado" for c in historial)

    asyncio.run(main())


# ── respaldos ────────────────────────────────────────────────────────────────


def test_respaldo_inicial_tiene_3_tablas():
    from app.repo import respaldos

    async def main():
        lista = await respaldos.listar()
        tablas = {b["tabla"] for b in lista}
        assert tablas == {"servicios", "segmentaciones", "maquinas"}

    asyncio.run(main())


def test_crear_y_restaurar_respaldo():
    """El snapshot persiste el estado al momento de crear() y restaurar() lo aplica."""
    from app.repo import servicios, respaldos

    async def main():
        # Estado original
        s = await servicios.obtener_por_codigo("autolavado")
        nombre_original = s.nombre
        precio_original = s.precio_fijo

        # Crear respaldo con el estado original
        n = await respaldos.crear("servicios", "snapshot pre-cambio")
        assert n == 4

        # Modificar
        await servicios.actualizar(
            s.id,
            nombre="MODIFICADO",
            tipo_calculo="fijo",
            precio_fijo=999,
            tarifa_por_kg=0,
            duracion_min=45,
            limite_kg=None,
            tipos_equipo="mixto,lavado",
            activo=True,
        )
        modificado = await servicios.obtener_por_codigo("autolavado")
        assert modificado.nombre == "MODIFICADO"
        assert modificado.precio_fijo == 999

        # Restaurar
        ok, filas = await respaldos.restaurar("servicios")
        assert ok is True
        assert filas == 4
        restaurado = await servicios.obtener_por_codigo("autolavado")
        assert restaurado.nombre == nombre_original
        assert restaurado.precio_fijo == precio_original

    asyncio.run(main())


def test_restaurar_tabla_invalida_falla():
    from app.repo import respaldos

    async def main():
        ok, n = await respaldos.restaurar("transacciones")  # no está en válidas
        assert ok is False
        assert n == 0

    asyncio.run(main())


def test_respaldo_completo():
    from app.repo import respaldos

    async def main():
        resultado = await respaldos.crear_completo("full")
        assert set(resultado.keys()) == {"servicios", "segmentaciones", "maquinas"}
        r = await respaldos.restaurar_completo()
        for tabla in ("servicios", "segmentaciones", "maquinas"):
            assert r[tabla]["ok"] is True

    asyncio.run(main())


# ── Consistencia enum ↔ strings en SQL ───────────────────────────────────────


def test_strings_del_enum_coinciden_con_queries():
    """Los strings de `EstadoOrden.value` que usa `repo/transacciones.py`
    deben coincidir exactamente con los literales en las queries SQL.
    Si el día de mañana alguien renombra un valor del enum, este test rompe."""
    from app.core.estados import EstadoOrden

    esperados = {
        EstadoOrden.PENDIENTE_PESO.value: "Pendiente-peso",
        EstadoOrden.PROCESANDO_PAGO.value: "Procesando-pago",
        EstadoOrden.PENDIENTE_PAGO.value: "Pendiente-pago",
        EstadoOrden.PENDIENTE.value: "Pendiente",
    }
    for actual, esperado in esperados.items():
        assert actual == esperado, (
            f"Drift en enum vs SQL: {actual!r} != {esperado!r}. "
            f"Actualiza `repo/transacciones.py` o el enum."
        )


def test_legacy_en_proceso_y_completado_estan_en_uso():
    """Documenta que la BD pre-v2 usa "En proceso" / "Completado".
    El día que se decida migrar esos datos, este test debe actualizarse."""
    from app.repo import transacciones

    assert transacciones._EN_PROCESO == "En proceso"
    assert transacciones._COMPLETADO == "Completado"
