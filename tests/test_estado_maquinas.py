"""Tests unitarios para `core.estado_maquinas`.

Valida la API pública sin tocar GPIO ni BD real.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(autouse=True)
def _reset_estado():
    """Limpia el estado global entre tests."""
    from app.core import estado_maquinas as em

    em.ESTADO.clear()
    yield
    em.ESTADO.clear()


def test_registrar_maquina_crea_libre():
    from app.core.estado_maquinas import ESTADO, registrar_maquina

    registrar_maquina("lav_1", "Lavasecadora 1", "mixto", "pulso")
    assert "lav_1" in ESTADO
    assert ESTADO["lav_1"].ocupada is False
    assert ESTADO["lav_1"].modo == "pulso"


def test_registrar_maquina_actualiza_sin_resetar_estado():
    from app.core.estado_maquinas import registrar_maquina

    registrar_maquina("lav_1", "Nombre viejo", "lavado", "pulso")
    registrar_maquina("lav_1", "Nombre nuevo", "mixto", "sostenido")
    from app.core.estado_maquinas import ESTADO

    assert ESTADO["lav_1"].nombre == "Nombre nuevo"
    assert ESTADO["lav_1"].tipo == "mixto"


def test_asignar_marca_como_ocupada():
    from app.core.estado_maquinas import (
        asignar,
        esta_disponible,
        obtener,
        registrar_maquina,
    )

    registrar_maquina("lav_1", "L1", "mixto", "pulso")
    assert esta_disponible("lav_1") is True
    asignar("lav_1", 42, "Juan", "Lavar", 0)
    assert esta_disponible("lav_1") is False
    em = obtener("lav_1")
    assert em.orden_id == 42
    assert em.nombre_cliente == "Juan"
    assert em.servicio == "Lavar"


def test_asignar_dos_veces_misma_orden_es_idempotente():
    from app.core.estado_maquinas import asignar, registrar_maquina

    registrar_maquina("lav_1", "L1", "mixto", "pulso")
    asignar("lav_1", 42, "Juan", "Lavar", 0)
    asignar("lav_1", 42, "Juan", "Lavar", 0)  # no debe lanzar
    from app.core.estado_maquinas import obtener

    assert obtener("lav_1").orden_id == 42


def test_asignar_dos_ordenes_distintas_lanza_runtime_error():
    from app.core.estado_maquinas import asignar, registrar_maquina

    registrar_maquina("lav_1", "L1", "mixto", "pulso")
    asignar("lav_1", 42, "A", "x", 0)
    with pytest.raises(RuntimeError):
        asignar("lav_1", 99, "B", "y", 0)


def test_liberar_devuelve_orden_id_y_resetea():
    from app.core.estado_maquinas import (
        asignar,
        esta_disponible,
        liberar,
        registrar_maquina,
    )

    registrar_maquina("lav_1", "L1", "mixto", "pulso")
    asignar("lav_1", 42, "A", "x", 0)
    orden_id = liberar("lav_1")
    assert orden_id == 42
    assert esta_disponible("lav_1") is True


def test_liberar_maquina_no_ocupada_devuelve_none():
    from app.core.estado_maquinas import liberar, registrar_maquina

    registrar_maquina("lav_1", "L1", "mixto", "pulso")
    assert liberar("lav_1") is None


def test_asignar_maquina_no_registrada_lanza_keyerror():
    from app.core.estado_maquinas import asignar

    with pytest.raises(KeyError):
        asignar("fantasma", 1, "", "", 0)


def test_pausar_solo_aplica_a_sostenido_ocupado():
    from app.core.estado_maquinas import (
        asignar,
        obtener,
        pausar,
        registrar_maquina,
    )

    registrar_maquina("sus_1", "S1", "mixto", "sostenido")
    registrar_maquina("pul_1", "P1", "mixto", "pulso")

    assert pausar("sus_1") is False  # libre
    asignar("sus_1", 1, "A", "x", 30)
    assert pausar("sus_1") is True
    assert obtener("sus_1").pausada is True

    asignar("pul_1", 2, "B", "y", 0)
    assert pausar("pul_1") is False  # no aplica a pulso


def test_reanudar_solo_si_pausada():
    from app.core.estado_maquinas import (
        asignar,
        obtener,
        pausar,
        reanudar,
        registrar_maquina,
    )

    registrar_maquina("sus_1", "S1", "mixto", "sostenido")
    asignar("sus_1", 1, "A", "x", 30)
    assert reanudar("sus_1", 10) is False  # no está pausada
    pausar("sus_1")
    assert reanudar("sus_1", 10) is True
    em = obtener("sus_1")
    assert em.pausada is False
    assert em.duracion_min == 40  # 30 + 10


def test_pausar_y_reanudar_sin_duracion():
    from app.core.estado_maquinas import (
        asignar,
        obtener,
        pausar,
        reanudar,
        registrar_maquina,
    )

    registrar_maquina("sus_1", "S1", "mixto", "sostenido")
    asignar("sus_1", 1, "A", "x", 0)  # 0 = sin auto-apagado
    pausar("sus_1")
    assert obtener("sus_1").pausada is True
    assert reanudar("sus_1", 5) is True
    assert obtener("sus_1").duracion_min == 5


def test_cargar_desde_bd_reconstruye_estado():
    from app.core.estado_maquinas import (
        ESTADO,
        cargar_desde_bd,
        esta_disponible,
    )

    class M:
        def __init__(self, codigo, nombre, tipo, modo):
            self.codigo = codigo
            self.nombre = nombre
            self.tipo = tipo
            self.modo = modo

    maquinas = [
        M("lav_1", "L1", "mixto", "pulso"),
        M("sec_1", "S1", "secado", "sostenido"),
    ]
    ordenes = [
        {
            "id_transaccion": 7,
            "id_equipo": "L1",
            "nombre_cliente": "Juan",
            "tipo_servicio": "Lavar",
            "duracion_estimada_min": 0,
            "inicio_servicio": None,
        },
    ]
    cargar_desde_bd(maquinas, ordenes)
    assert esta_disponible("lav_1") is False
    assert ESTADO["lav_1"].orden_id == 7
    assert esta_disponible("sec_1") is True


def test_listar_ocupadas_y_disponibles():
    from app.core.estado_maquinas import (
        asignar,
        listar_disponibles,
        listar_ocupadas,
        registrar_maquina,
    )

    registrar_maquina("a", "A", "mixto", "pulso")
    registrar_maquina("b", "B", "mixto", "pulso")
    asignar("a", 1, "X", "x", 0)
    libres = [e.codigo for e in listar_disponibles()]
    ocupadas = [e.codigo for e in listar_ocupadas()]
    assert libres == ["b"]
    assert ocupadas == ["a"]
