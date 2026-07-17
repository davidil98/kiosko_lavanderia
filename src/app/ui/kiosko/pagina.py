"""Página principal del kiosko cliente (`@ui.page("/")`).

Estructura visual:
- Header (logo + título + reloj)
- Sidebar (5 pasos)
- Content (paso actual)

El wizard vive en `app.storage.user["kiosko_wizard"]` (dataclass serializado
a dict). Cada página NiceGUI refresca su content pasando por `refrescar()`
que re-renderiza según el `wizard.paso` y `wizard.sub`.
"""

import asyncio
import json
from dataclasses import asdict, replace

from nicegui import app, ui

from app.core.estados import MetodoPago
from app.eventos.bus import bus
from app.eventos.tipos import (
    TIPO_ORDEN_CANCELADA,
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
from app.ui.kiosko.wizard import Paso, Sub, WizardKiosko


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
    return WizardKiosko(**raw)


def _guardar_wizard(w: WizardKiosko) -> None:
    app.storage.general[_wizard_storage_key()] = asdict(w)


@ui.page("/")
def kiosko_cliente():
    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
    )
    ui.add_head_html(f'<link rel="stylesheet" href="{KIOSKO_CSS}">')
    ui.add_head_html(_CLOCK_JS)

    wizard = _cargar_wizard()

    @ui.refreshable
    def kiosko_ui() -> None:
        # Header
        with ui.element("div").props("id=kiosko-root"):
            with ui.element("div").props("id=main-col"):
                with ui.element("div").props("id=header"):
                    with ui.element("div").classes("logo-area"):
                        ui.image(LOGOTIPO).style(
                            "width:50px;height:50px;object-fit:contain;"
                        )
                        ui.html('<span class="titulo">Lavanderia EcoLuna</span>')
                    ui.html(
                        '<div class="reloj" id="reloj-txt">--/--/----<br>--:--:--</div>'
                    )

                with ui.element("div").props("id=content"):
                    _render_paso(wizard, kiosko_ui.refresh)

    def refrescar(nuevo_wizard: WizardKiosko = None) -> None:
        nonlocal wizard
        if nuevo_wizard is not None and nuevo_wizard is not wizard:
            wizard = nuevo_wizard
            _guardar_wizard(wizard)
        kiosko_ui.refresh()

    # Suscripción al bus: cuando llega `pago.confirmado` o `peso.aprobado`,
    # la página reacciona automáticamente. El handler se suscribe a nivel
    # de cliente (no del proceso) para que cada kiosko independiente tenga
    # su propia cola.
    cola_pago_confirmado = bus.subscribe(TIPO_PAGO_CONFIRMADO)
    cola_pago_cancelado = bus.subscribe(TIPO_PAGO_CANCELADO)
    cola_peso_aprobado = bus.subscribe(TIPO_PESO_APROBADO)
    cola_peso_rechazado = bus.subscribe(TIPO_PESO_RECHAZADO)
    cola_orden_cancelada = bus.subscribe(TIPO_ORDEN_CANCELADA)

    async def consumir_eventos() -> None:
        # `lanzado` evita que se acumulen tareas al re-renderizar.
        while True:
            ev = await cola_pago_confirmado.get()
            if (
                wizard.ultimo_id_transaccion is not None
                and ev.get("orden_id") == wizard.ultimo_id_transaccion
            ):
                refrescar(wizard.ir_a_exito(ev.get("orden_id")))

    async def consumir_peso() -> None:
        while True:
            ev = await cola_peso_aprobado.get()
            if (
                wizard.ultimo_id_transaccion is not None
                and ev.get("orden_id") == wizard.ultimo_id_transaccion
            ):
                # El admin aprobó el peso: pasamos al paso de pago.
                refrescar(replace(wizard, esperando_admin=None).iniciar_pago())

    async def consumir_rechazo_peso() -> None:
        while True:
            ev = await cola_peso_rechazado.get()
            if (
                wizard.ultimo_id_transaccion is not None
                and ev.get("orden_id") == wizard.ultimo_id_transaccion
            ):
                refrescar(wizard.notificar_rechazo_peso())

    asyncio.create_task(consumir_eventos())
    asyncio.create_task(consumir_peso())
    asyncio.create_task(consumir_rechazo_peso())

    # Render inicial
    kiosko_ui()

    # En modo test, capturamos teclas para simular monedas.
    if "test" in __import__("sys").argv:

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
                # Llamada HTTP al endpoint interno (en proceso)
                import urllib.request
                import json

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
    # Sidebar (siempre visible)
    sidebar.render_sidebar(wizard)

    if wizard.paso is Paso.SERVICIO:
        paso_servicio.render_paso_servicio(wizard, refresh)
    elif wizard.paso is Paso.NOMBRE:
        paso_nombre.render_paso_nombre(wizard, refresh)
    elif wizard.paso is Paso.PESO:
        paso_peso.render_paso_peso(wizard, refresh)
    elif wizard.paso is Paso.PAGO:
        paso_pago.render_paso_pago(wizard, refresh)
    elif wizard.paso is Paso.EXITO:
        paso_exito.render_paso_exito(wizard, refresh)
