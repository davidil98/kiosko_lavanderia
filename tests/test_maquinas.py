"""Tests de los adaptadores de hardware (en test mode: sin GPIO real)."""

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
    from app.core import loader as core_loader
    from app.core import estado_maquinas as em
    from app.repo import maquinas as repo_maquinas

    db.usar_path_test(tmp_path / "hw.db")
    db.init_db()
    # Inyectar loader de equipos para los tests
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
    # Inyectar loaders de servicios y segmentaciones
    core_loader.instalar_como_defaults()
    # Popular estado_maquinas con todas las máquinas (libres al inicio)
    em.ESTADO.clear()
    for m in repo_maquinas._listar(solo_activas=False):
        em.registrar_maquina(m.codigo, m.nombre, m.tipo, m.modo)
    yield
    em.ESTADO.clear()
    db.usar_path_test(None)


def test_gpio_en_test_mode_no_toca_hardware():
    from app.adaptadores.hardware import gpio

    assert gpio.modo_test() is True
    # set_high/set_low no deben crashear
    gpio.set_high(17)
    gpio.set_low(17)
    gpio.init_gpio_lavadoras()
    gpio.limpiar_pines()


def test_equipos_proxy_carga_los_4_seeds():
    from app.core import maquinas as cm

    eqs = cm.cargar_equipos()
    codigos = set(eqs.keys())
    assert codigos == {
        "lavasecadora_1",
        "lavasecadora_2",
        "lavasecadora_3",
        "secadora_1",
    }
    e1 = eqs["lavasecadora_1"]
    assert e1["gpio"] == 17
    assert e1["modo"] == "pulso"
    assert e1["capacidad_kg"] == 5


def test_recargar_equipos_refleja_cambios():
    from app.core import maquinas as cm
    from app.repo import maquinas as repo

    initial = len(cm.cargar_equipos())
    asyncio.run(
        repo.crear(
            codigo="nueva",
            nombre="Nueva",
            tipo="lavado",
            capacidad_kg=7,
            gpio=24,
            modo="pulso",
            duracion_max_min=20,
        )
    )
    assert len(cm.cargar_equipos()) == initial  # cache no refrescado
    recargado = cm.recargar_equipos()
    assert len(recargado) == initial + 1
    assert "nueva" in recargado


def test_monedero_simular_recibe_valor():
    from app.adaptadores.hardware import monedero

    ingresos = []
    m = monedero.LectorMonedas(lambda v: ingresos.append(v))
    m.simular_moneda(1)
    m.simular_moneda(2)
    m.simular_moneda(5)
    m.simular_moneda(10)
    m.simular_moneda(99)  # inválido
    assert ingresos == [1, 2, 5, 10]


def test_monedero_no_reacciona_sin_pulsos():
    from app.adaptadores.hardware import monedero

    ingresos = []
    m = monedero.LectorMonedas(lambda v: ingresos.append(v))
    assert ingresos == []


def test_monedero_agrupacion_por_tiempo():
    """Si llegan N pulsos en menos de 300ms, se reportan como una moneda."""
    from app.adaptadores.hardware import monedero

    ingresos = []
    m = monedero.LectorMonedas(lambda v: ingresos.append(v))
    m._running = False  # evitar que la tarea quede corriendo
    m._registrar_pulso()
    m._registrar_pulso()
    import time

    m._ultimo_tiempo = time.time() - 1.0
    # Llamar a la lógica de agrupación una vez (no el loop)
    if m._pulsos > 0 and (time.time() - m._ultimo_tiempo) > monedero.DEBOUNCE_S:
        n = m._pulsos
        m._pulsos = 0
        if n in monedero.PULSOS_A_MONEDA:
            m._callback(monedero.PULSOS_A_MONEDA[n])
    assert ingresos == [1]


def test_activar_pulso_termina_sin_sostenida():
    from app.adaptadores.hardware import maquinas_pin

    asyncio.run(maquinas_pin.activar("lavasecadora_1"))
    assert maquinas_pin.sostenida_activa("lavasecadora_1") is None


def test_activar_sostenida_programa_auto_apagado():
    from app.adaptadores.hardware import maquinas_pin

    async def main():
        await maquinas_pin.activar("lavasecadora_3")  # modo sostenido
        info = maquinas_pin.sostenida_activa("lavasecadora_3")
        assert info is not None
        assert info["duracion_min"] == 25
        await maquinas_pin.apagar("lavasecadora_3")
        assert maquinas_pin.sostenida_activa("lavasecadora_3") is None

    asyncio.run(main())


def test_activar_sostenida_dos_veces_no_duplica():
    from app.adaptadores.hardware import maquinas_pin

    async def main():
        await maquinas_pin.activar("lavasecadora_3")
        await maquinas_pin.activar("lavasecadora_3")
        assert maquinas_pin.sostenida_activa("lavasecadora_3") is not None
        await maquinas_pin.apagar("lavasecadora_3")

    asyncio.run(main())


def test_activar_con_duracion_usa_minutos_del_operador():
    from app.adaptadores.hardware import maquinas_pin

    async def main():
        await maquinas_pin.activar_con_duracion("lavasecadora_3", 60)
        info = maquinas_pin.sostenida_activa("lavasecadora_3")
        assert info["duracion_min"] == 60
        await maquinas_pin.apagar("lavasecadora_3")

    asyncio.run(main())


def test_activar_maquina_inexistente_no_falla():
    from app.adaptadores.hardware import maquinas_pin

    asyncio.run(maquinas_pin.activar("fantasma"))


def test_tiempo_restante_sostenida_decrementa():
    from app.adaptadores.hardware import maquinas_pin

    async def main():
        await maquinas_pin.activar("lavasecadora_3")
        t1 = maquinas_pin.tiempo_restante_sostenida("lavasecadora_3")
        assert t1 > 0
        await maquinas_pin.apagar("lavasecadora_3")
        assert maquinas_pin.tiempo_restante_sostenida("lavasecadora_3") == 0

    asyncio.run(main())


def test_limpiar_cancela_tareas():
    """`limpiar()` (síncrono) cancela todas las sostenidas activas."""
    from app.adaptadores.hardware import maquinas_pin

    async def main():
        await maquinas_pin.activar("lavasecadora_3")
        assert maquinas_pin.sostenida_activa("lavasecadora_3") is not None
        maquinas_pin.limpiar()
        assert maquinas_pin.sostenida_activa("lavasecadora_3") is None

    asyncio.run(main())


def test_limpiar_sin_sostenidas_no_falla():
    from app.adaptadores.hardware import maquinas_pin

    maquinas_pin.limpiar()  # no debe crashear aunque no haya activas


def test_activar_sostenida_dos_veces_no_duplica():
    from app.adaptadores.hardware import maquinas_pin

    async def main():
        await maquinas_pin.activar("lavasecadora_3")
        await maquinas_pin.activar("lavasecadora_3")
        assert maquinas_pin.sostenida_activa("lavasecadora_3") is not None
        await maquinas_pin.apagar("lavasecadora_3")

    asyncio.run(main())


def test_activar_con_duracion_usa_minutos_del_operador():
    from app.adaptadores.hardware import maquinas_pin

    async def main():
        await maquinas_pin.activar_con_duracion("lavasecadora_3", 60)
        info = maquinas_pin.sostenida_activa("lavasecadora_3")
        assert info["duracion_min"] == 60
        await maquinas_pin.apagar("lavasecadora_3")

    asyncio.run(main())


def test_activar_maquina_inexistente_no_falla():
    from app.adaptadores.hardware import maquinas_pin

    asyncio.run(maquinas_pin.activar("fantasma"))


def test_tiempo_restante_sostenida_decrementa():
    from app.adaptadores.hardware import maquinas_pin

    async def main():
        await maquinas_pin.activar("lavasecadora_3")
        t1 = maquinas_pin.tiempo_restante_sostenida("lavasecadora_3")
        assert t1 > 0
        await maquinas_pin.apagar("lavasecadora_3")
        assert maquinas_pin.tiempo_restante_sostenida("lavasecadora_3") == 0

    asyncio.run(main())


def test_limpiar_cancela_tareas():
    """`limpiar()` (síncrono) cancela todas las sostenidas activas."""
    from app.adaptadores.hardware import maquinas_pin

    async def main():
        await maquinas_pin.activar("lavasecadora_3")
        assert maquinas_pin.sostenida_activa("lavasecadora_3") is not None
        maquinas_pin.limpiar()
        assert maquinas_pin.sostenida_activa("lavasecadora_3") is None

    asyncio.run(main())


def test_limpiar_sin_sostenidas_no_falla():
    from app.adaptadores.hardware import maquinas_pin

    maquinas_pin.limpiar()


def test_cargar_servicios_devuelve_4_seeds():
    from app.core.servicios import cargar_servicios, cargar_servicio_por_codigo

    servicios = cargar_servicios()
    assert len(servicios) == 4
    codigos = {s.codigo for s in servicios}
    assert codigos == {"autolavado", "secado", "pers_ropa", "pers_edredon"}
    autolavado = cargar_servicio_por_codigo("autolavado")
    assert autolavado.tipo_calculo == "fijo"
    assert autolavado.precio_base == 45
    pers = cargar_servicio_por_codigo("pers_ropa")
    assert pers.tipo_calculo == "por_kg"
    assert pers.precio_base == 30  # 1 kg


def test_limite_kg_efectivo_usa_campo_o_equipos():
    from app.core.servicios import cargar_servicio_por_codigo

    autolavado = cargar_servicio_por_codigo("autolavado")
    # autolavado tiene limite_kg=NULL → usa min de máquinas compatibles
    assert autolavado.limite_kg_efectivo == 5
    pers_ropa = cargar_servicio_por_codigo("pers_ropa")
    # pers_ropa tiene limite_kg=5 fijo
    assert pers_ropa.limite_kg_efectivo == 5


def test_cargar_segmentaciones_por_servicio():
    from app.core.servicios import cargar_servicio_por_codigo, cargar_segmentaciones

    pers_ropa = cargar_servicio_por_codigo("pers_ropa")
    segs = cargar_segmentaciones(servicio_id=pers_ropa.id)
    assert len(segs) == 3
    assert segs[0].codigo == "completo"
    assert segs[0].tipo_calculo == "por_kg"
    edredon = cargar_servicio_por_codigo("pers_edredon")
    segs_e = cargar_segmentaciones(servicio_id=edredon.id)
    assert len(segs_e) == 2


def test_servicios_autoservicio_y_personalizado_separan():
    from app.core.servicios import servicios_autoservicio, servicios_personalizado

    autos = servicios_autoservicio()
    pers = servicios_personalizado()
    assert {s.codigo for s in autos} == {"autolavado", "secado"}
    assert {s.codigo for s in pers} == {"pers_ropa", "pers_edredon"}
