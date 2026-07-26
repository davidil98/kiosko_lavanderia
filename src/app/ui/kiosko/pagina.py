"""Página principal del kiosko cliente (`@ui.page("/")`).

Estructura visual:
- Header (logo + título + reloj) — estático
- Sidebar + Content — dentro de `kiosko_main` (@ui.refreshable async)
  Ambos se re-renderizan juntos para que el sidebar refleje el paso actual.

El wizard vive en `app.storage.general["kiosko_wizard"]`. El consumer loop
de eventos (`_consumir_eventos_kiosko`) escucha eventos del bus:
- TIPO_PESO_APROBADO / TIPO_PESO_RECHAZADO (admin aprueba/rechaza peso)
- TIPO_PAGO_CONFIRMADO / TIPO_PAGO_CANCELADO (admin confirma/cancela pago mostrador)
"""

import json
import sys

from dataclasses import asdict

from nicegui import app, ui

from app.eventos.bus import bus
from app.eventos.tipos import (
    TIPO_PAGO_CANCELADO,
    TIPO_PAGO_CONFIRMADO,
    TIPO_PESO_APROBADO,
    TIPO_PESO_RECHAZADO,
)
from app.ui.compartido.estilos import KIOSKO_CSS, LOGOTIPO
from app.ui.kiosko import (
    paso_exito,
    paso_nombre,
    paso_pago,
    paso_peso,
    paso_servicio,
    sidebar,
)
from app.ui.kiosko.wizard import Paso, WizardKiosko


_CLOCK_JS = """
<script>
function _updateClock() {
    var now = new Date();
    var d = now.toLocaleDateString('es-MX',{day:'2-digit',month:'2-digit',year:'numeric'});
    var t = now.toLocaleTimeString('es-MX',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
    var el = document.getElementById('reloj-txt');
    if(el) el.innerHTML = d + '<br>' + t;
}
setInterval(_updateClock, 1000);
document.addEventListener('DOMContentLoaded', _updateClock);
</script>
"""


def _wizard_storage_key() -> str:
    return "kiosko_wizard"


def _cargar_wizard() -> WizardKiosko:
    raw = app.storage.general.get(_wizard_storage_key())
    if raw is None:
        return WizardKiosko()
    try:
        return WizardKiosko.desde_dict(raw)
    except Exception:
        return WizardKiosko()


def _guardar_wizard(w: WizardKiosko) -> None:
    app.storage.general[_wizard_storage_key()] = asdict(w)


@ui.page("/")
async def kiosko_cliente():
    from app.repo import db as _db
    from app.core import maquinas as _cm
    from app.repo import maquinas as _repo_maquinas
    from app.core import loader as _cat_loader

    _db.init_db()
    _cm.set_cargador(
        lambda: {
            m.codigo: _cm.Equipo(
                codigo=m.codigo,
                nombre=m.nombre,
                tipo=m.tipo,
                capacidad_kg=m.capacidad_kg,
                gpio=m.gpio,
                modo=m.modo,
                duracion_max_min=m.duracion_max_min,
            )
            for m in _repo_maquinas._listar(solo_activas=True)
        }
    )
    _cat_loader.instalar_como_defaults()
    print(
        f"[kiosko] init OK, {len(_cat_loader.cargar_todos())} servicios",
        file=sys.stderr,
        flush=True,
    )

    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
    )
    ui.add_head_html(f'<link rel="stylesheet" href="{KIOSKO_CSS}">')
    ui.add_head_html(_CLOCK_JS)

    wizard = _cargar_wizard()

    def _on_refresh(nuevo_wizard: WizardKiosko | None = None) -> None:
        nonlocal wizard
        if nuevo_wizard is not None and nuevo_wizard is not wizard:
            wizard = nuevo_wizard
            _guardar_wizard(wizard)
        kiosko_main.refresh()

    @ui.refreshable
    async def kiosko_main() -> None:
        nonlocal wizard
        wizard = _cargar_wizard()
        sidebar.render_sidebar(wizard)
        with ui.element("div").props("id=content"):
            _render_paso(wizard, _on_refresh)

    with ui.element("div").props("id=kiosko-root data-theme=high-contrast"):
        with ui.element("div").props("id=header"):
            with ui.element("div").classes("logo-area"):
                ui.html(
                    f'<img src="{LOGOTIPO}" '
                    f'style="width:50px;height:50px;object-fit:contain;" '
                    f'alt="Logo EcoLuna">'
                )
                ui.html('<span class="titulo">Lavanderia EcoLuna</span>')
            ui.html('<div class="reloj" id="reloj-txt">--/--/----<br>--:--:--</div>')
        with ui.element("div").classes("main-row"):
            await kiosko_main()

    colas = {
        bus.subscribe(TIPO_PESO_APROBADO): "aprobado",
        bus.subscribe(TIPO_PESO_RECHAZADO): "rechazado",
        bus.subscribe(TIPO_PAGO_CONFIRMADO): "pago_confirmado",
        bus.subscribe(TIPO_PAGO_CANCELADO): "pago_cancelado",
    }

    async def _consumir_eventos_kiosko() -> None:
        for cola, tipo in list(colas.items()):
            while True:
                try:
                    evt = cola.get_nowait()
                except Exception:
                    break
                w = _cargar_wizard()
                if w.esperando_admin is not None:
                    if tipo == "aprobado":
                        nuevo = w.confirmar_peso_desde_admin()
                    elif tipo == "rechazado":
                        nuevo = w.notificar_rechazo_peso().volver_a_pesar()
                    elif tipo == "pago_confirmado":
                        nuevo = w.ir_a_exito(evt.orden_id)
                    elif tipo == "pago_cancelado":
                        nuevo = w.volver_a_pesar()
                    else:
                        continue
                    _guardar_wizard(nuevo)
                    kiosko_main.refresh()

    ui.timer(0.3, _consumir_eventos_kiosko)

    if "test" in sys.argv:

        def handle_keyboard(e):
            if not e.action.keydown:
                return
            try:
                tecla = e.key.name
                if tecla == "0":
                    val = 10
                elif tecla in ["1", "2", "5"]:
                    val = int(tecla)
                else:
                    return
                from app.adaptadores.hardware.monedero import PULSOS_A_MONEDA

                if val not in PULSOS_A_MONEDA.values():
                    return
                import urllib.request

                req = urllib.request.Request(
                    "http://localhost:8000/api/kiosko/moneda",
                    data=json.dumps({"monto": val}).encode(),
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=1)
            except Exception as ex:
                print(f"[kiosko] Error inyectando moneda: {ex}")

        ui.keyboard(on_key=handle_keyboard)


def _render_paso(wizard: WizardKiosko, refresh) -> None:
    if wizard.paso == Paso.SERVICIO:
        paso_servicio.render_paso_servicio(wizard, refresh)
    elif wizard.paso == Paso.NOMBRE:
        paso_nombre.render_paso_nombre(wizard, refresh)
    elif wizard.paso == Paso.PESO:
        paso_peso.render_paso_peso(wizard, refresh)
    elif wizard.paso == Paso.PAGO:
        paso_pago.render_paso_pago(wizard, refresh)
    elif wizard.paso == Paso.EXITO:
        paso_exito.render_paso_exito(wizard, refresh)
