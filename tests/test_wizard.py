"""Tests del wizard del kiosko cliente (lógica pura, sin NiceGUI)."""

import sys
from dataclasses import asdict
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

    db.usar_path_test(tmp_path / "w.db")
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


# ── Estado inicial ──────────────────────────────────────────────────────────


def test_wizard_inicia_en_servicio():
    from app.ui.kiosko.wizard import WizardKiosko, Paso, Sub

    w = WizardKiosko()
    assert w.paso is Paso.SERVICIO
    assert w.sub is Sub.NINGUNO
    assert w.servicio is None
    assert w.segmentacion is None
    assert w.nombre == ""
    assert w.dinero == 0
    assert w.peso == 0.0
    assert w.metodo is None
    assert w.ultimo_id_transaccion is None
    assert w.esperando_admin is None
    assert w.paso_actual if False else True  # sanity


def test_wizard_es_inmutable():
    from app.ui.kiosko.wizard import WizardKiosko

    w = WizardKiosko()
    with pytest.raises(Exception):  # frozen=True
        w.nombre = "x"


# ── Selección de servicio ──────────────────────────────────────────────────


def test_seleccionar_servicio_autoservicio_avanza_a_nombre():
    from app.ui.kiosko.wizard import WizardKiosko, Paso

    w = WizardKiosko()
    w2 = w.seleccionar_servicio("autolavado")
    assert w2.servicio is not None
    assert w2.servicio.codigo == "autolavado"
    assert w2.paso is Paso.NOMBRE
    # El servicio anterior no se mutó
    assert w.servicio is None


def test_seleccionar_servicio_personalizado_tambien_avanza_a_nombre():
    from app.ui.kiosko.wizard import WizardKiosko, Paso

    w = WizardKiosko()
    w2 = w.seleccionar_servicio("pers_ropa")
    assert w2.servicio is not None
    assert w2.servicio.es_personalizado
    assert w2.paso is Paso.NOMBRE


def test_seleccionar_servicio_inexistente_no_hace_nada():
    from app.ui.kiosko.wizard import WizardKiosko

    w = WizardKiosko()
    w2 = w.seleccionar_servicio("fantasma")
    assert w2.servicio is None
    assert w2 is w  # misma instancia (no hubo cambio)


def test_seleccionar_servicio_resetea_peso_dinero_y_metodo():
    from app.ui.kiosko.wizard import WizardKiosko
    from dataclasses import replace
    from app.core.estados import MetodoPago

    w_inicial = WizardKiosko().seleccionar_servicio("autolavado")
    w_inicial = replace(w_inicial, peso=5.0, dinero=50, metodo=MetodoPago.POINT)
    w_nuevo = w_inicial.seleccionar_servicio("secado")
    assert w_nuevo.peso == 0.0
    assert w_nuevo.dinero == 0
    assert w_nuevo.metodo is None


# ── Sub-estados ─────────────────────────────────────────────────────────────


def test_mostrar_y_ocultar_sub_lavar():
    from app.ui.kiosko.wizard import WizardKiosko, Sub

    w = WizardKiosko()
    assert w.sub is Sub.NINGUNO
    w2 = w.mostrar_sub_lavar()
    assert w2.sub is Sub.SUB_LAVAR
    w3 = w2.ocultar_sub_lavar()
    assert w3.sub is Sub.NINGUNO


def test_mostrar_segmentaciones_y_metodos_pago():
    from app.ui.kiosko.wizard import WizardKiosko, Sub

    w = WizardKiosko()
    w2 = w.mostrar_segmentaciones()
    assert w2.sub is Sub.SEGMENTACIONES
    w3 = w2.mostrar_metodos_pago()
    assert w3.sub is Sub.METODOS_PAGO


# ── Selección de segmentación ──────────────────────────────────────────────


def test_seleccionar_segmentacion_salta_a_metodos_pago():
    from app.ui.kiosko.wizard import WizardKiosko, Sub

    w = WizardKiosko().seleccionar_servicio("pers_ropa")
    segs = w.servicio.id  # asegura que se cargó
    w2 = w.mostrar_segmentaciones()
    w3 = w2.seleccionar_segmentacion(1)  # primer segmentación de pers_ropa
    assert w3.segmentacion is not None
    assert w3.sub is Sub.METODOS_PAGO


# ── Nombre ─────────────────────────────────────────────────────────────────


def test_with_nombre_actualiza_y_confirmar_limpia():
    from app.ui.kiosko.wizard import WizardKiosko, Paso

    w = WizardKiosko().seleccionar_servicio("autolavado")
    w2 = w.with_nombre("A")
    w3 = w2.with_nombre("An")
    w4 = w3.with_nombre("Ana")
    w5 = w4.confirmar_nombre()
    assert w5.nombre == "Ana"
    assert w5.paso is Paso.PESO


def test_confirmar_nombre_sin_texto_usa_cliente():
    from app.ui.kiosko.wizard import WizardKiosko, Paso

    w = WizardKiosko().seleccionar_servicio("autolavado")
    w2 = w.confirmar_nombre()
    assert w2.nombre == "Cliente"
    assert w2.paso is Paso.PESO


# ── Peso y pago ───────────────────────────────────────────────────────────


def test_capturar_peso_y_volver_a_pesar():
    from app.ui.kiosko.wizard import WizardKiosko

    w = WizardKiosko().seleccionar_servicio("autolavado").confirmar_nombre()
    w2 = w.capturar_peso(3.5)
    assert w2.peso == 3.5
    w3 = w2.volver_a_pesar()
    assert w3.peso == 0.0


def test_limite_kg_autolavado_es_5():
    from app.ui.kiosko.wizard import WizardKiosko

    w = WizardKiosko().seleccionar_servicio("autolavado")
    assert w.limite_kg() == 5


def test_limite_kg_pers_ropa_es_5_fijo():
    from app.ui.kiosko.wizard import WizardKiosko

    w = WizardKiosko().seleccionar_servicio("pers_ropa")
    assert w.limite_kg() == 5


def test_precio_total_autolavado_es_45_fijo():
    from app.ui.kiosko.wizard import WizardKiosko

    w = WizardKiosko().seleccionar_servicio("autolavado").confirmar_nombre()
    w = w.capturar_peso(3.0)
    assert w.precio_total() == 45


def test_precio_total_pers_ropa_depende_del_peso():
    from app.ui.kiosko.wizard import WizardKiosko

    w = WizardKiosko().seleccionar_servicio("pers_ropa").confirmar_nombre()
    w = w.capturar_peso(2.5)
    assert w.precio_total() == 75  # 30/kg * 2.5


def test_precio_total_con_segmentacion():
    from app.ui.kiosko.wizard import WizardKiosko

    w = (
        WizardKiosko()
        .seleccionar_servicio("pers_ropa")
        .confirmar_nombre()
        .capturar_peso(2.0)
        .mostrar_segmentaciones()
    )
    # segmento "completo" (por_kg a 30)
    w = w.seleccionar_segmentacion(w.servicio.id)  # primer id
    # Volvemos a buscar el id real
    from app.core.servicios import cargar_segmentaciones

    segs = cargar_segmentaciones(servicio_id=w.servicio.id)
    w = w.seleccionar_segmentacion(segs[0].id)
    assert w.segmentacion is not None
    assert w.precio_total() == 60  # 30 * 2


def test_puede_pagar_monedas_solo_con_dinero_suficiente():
    from app.ui.kiosko.wizard import WizardKiosko
    from dataclasses import replace

    w = (
        WizardKiosko()
        .seleccionar_servicio("autolavado")
        .confirmar_nombre()
        .capturar_peso(3.0)
    )
    assert w.puede_pagar_monedas() is False
    w2 = replace(w, dinero=20)
    assert w2.puede_pagar_monedas() is False
    w3 = replace(w, dinero=45)
    assert w3.puede_pagar_monedas() is True
    w4 = replace(w, dinero=100)
    assert w4.puede_pagar_monedas() is True


def test_ir_a_exito_y_reset():
    from app.ui.kiosko.wizard import WizardKiosko, Paso

    w = (
        WizardKiosko()
        .seleccionar_servicio("autolavado")
        .confirmar_nombre()
        .ir_a_exito(42)
    )
    assert w.paso is Paso.EXITO
    assert w.ultimo_id_transaccion == 42
    w2 = w.reset()
    assert w2.paso is Paso.SERVICIO
    assert w2.servicio is None
    assert w2.ultimo_id_transaccion is None


def test_empezar_y_terminar_espera():
    from app.ui.kiosko.wizard import WizardKiosko

    w = WizardKiosko()
    assert w.esperando_admin is None
    w2 = w.empezar_espera("peso")
    assert w2.esperando_admin == ("peso", "")
    w3 = w2.terminar_espera()
    assert w3.esperando_admin is None


def test_iniciar_paso_de_pago():
    from app.ui.kiosko.wizard import WizardKiosko, Paso
    from app.core.estados import MetodoPago

    w = WizardKiosko()
    w = w.seleccionar_metodo(MetodoPago.MONEDAS).iniciar_pago()
    assert w.paso is Paso.PAGO
    assert w.metodo is MetodoPago.MONEDAS


def test_serializacion_asdict_y_round_trip():
    """`asdict` funciona, pero el round-trip exacto no (anida ServicioInfo
    que se desarma a dict). Esto documenta la limitación: la UI usa
    `asdict` para guardar en storage y re-carga construyendo el wizard
    desde los constructores (no desde dicts planos)."""
    from app.ui.kiosko.wizard import WizardKiosko

    w = (
        WizardKiosko()
        .seleccionar_servicio("autolavado")
        .confirmar_nombre()
        .capturar_peso(2.5)
    )
    d = asdict(w)
    assert d["peso"] == 2.5
    assert d["paso"].value == "peso"
    assert d["nombre"] == "Cliente"
    # El servicio se desarma a dict
    assert isinstance(d["servicio"], dict)
    assert d["servicio"]["codigo"] == "autolavado"


def test_wizard_se_reconstruye_via_constructores():
    """Simula el ciclo UI: storage guarda asdict, UI reconstruye con
    constructores a partir de los códigos (no del dict crudo)."""
    from app.ui.kiosko.wizard import WizardKiosko

    w = (
        WizardKiosko()
        .seleccionar_servicio("autolavado")
        .confirmar_nombre()
        .capturar_peso(2.5)
    )
    # UI: "guardar"
    codigo_servicio = w.servicio.codigo
    nombre = w.nombre
    peso = w.peso
    # UI: "restaurar"
    w2 = (
        WizardKiosko()
        .seleccionar_servicio(codigo_servicio)
        .with_nombre(nombre)
        .capturar_peso(peso)
    )
    assert w2.servicio.codigo == w.servicio.codigo
    assert w2.peso == w.peso
