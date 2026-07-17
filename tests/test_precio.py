"""Tests del cálculo de precio polimórfico."""

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from app.core.precio import calcular_precio, formatear_precio


def _item(tipo_calculo="fijo", precio_fijo=0, tarifa_por_kg=0.0):
    return SimpleNamespace(
        tipo_calculo=tipo_calculo,
        precio_fijo=precio_fijo,
        tarifa_por_kg=tarifa_por_kg,
    )


def test_precio_fijo_directo():
    assert calcular_precio(_item("fijo", 45)) == 45
    assert calcular_precio(_item("fijo", 0)) == 0


def test_precio_por_kg_con_peso():
    item = _item("por_kg", 0, 30)
    assert calcular_precio(item, 2.0) == 60
    assert calcular_precio(item, 0.0) == 0
    assert calcular_precio(item, 3.5) == 105


def test_precio_por_kg_peso_negativo_se_trunca_a_0():
    item = _item("por_kg", 0, 30)
    assert calcular_precio(item, -5.0) == 0


def test_precio_por_kg_redondeo():
    # 17.5 * 2 = 35.0 (exacto)
    assert calcular_precio(_item("por_kg", 0, 17.5), 2) == 35
    # 10.4 * 3 = 31.2 → 31
    assert calcular_precio(_item("por_kg", 0, 10.4), 3) == 31
    # 10.5 * 3 = 31.5 → 32
    assert calcular_precio(_item("por_kg", 0, 10.5), 3) == 32


def test_precio_por_duracion_devuelve_precio_fijo():
    assert calcular_precio(_item("por_duracion", 100)) == 100


def test_tipo_invalido_cae_a_precio_fijo():
    assert calcular_precio(_item("otro", 77)) == 77


def test_formatear_precio_fijo():
    assert formatear_precio(_item("fijo", 45)) == "$45"


def test_formatear_precio_por_kg():
    assert formatear_precio(_item("por_kg", 0, 30)) == "$30/kg"


def test_peso_none_o_falsy_es_0():
    item = _item("por_kg", 0, 30)
    assert calcular_precio(item, None) == 0
    assert calcular_precio(item, 0) == 0
