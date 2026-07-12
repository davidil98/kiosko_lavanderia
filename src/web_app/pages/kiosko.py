import asyncio
from nicegui import ui, app
import nicegui as _ng

import database_web
import hardware
from services.notifications import (
    state,
    notificar_admin,
    notificar_kiosko,
    set_kiosko_ui_ref,
    registrar_kiosko_client,
    remover_kiosko_client,
)
from models import PASOS
from metodos_pago import MetodoMonedas
from components.kiosko.sidebar import render_sidebar
from components.kiosko.paso_servicio import render_paso_servicio
from components.kiosko.paso_nombre import render_paso_nombre
from components.kiosko.paso_peso import render_paso_peso
from components.kiosko.paso_pago import render_paso_pago
from components.kiosko.paso_exito import render_paso_exito


async def finalizar_pago():
    from models import calcular_precio

    metodo = state.metodo_pago_codigo or "monedas"
    es_pers = state.servicio_seleccionado.modalidad == "personalizado"
    modalidad = f"personalizado-{metodo}" if es_pers else f"autoservicio-{metodo}"
    # Si hay segmentación seleccionada, se cobra esa; si no, el servicio.
    item = state.get_item_cobro() or state.servicio_seleccionado
    precio_final = calcular_precio(item, state.peso_ingresado)
    ingresado = state.dinero_ingresado if metodo == "monedas" else precio_final
    cambio = max(0, state.dinero_ingresado - precio_final) if metodo == "monedas" else 0

    # Si hay segmentación, registrarla como prefijo en el nombre del servicio
    # para que el admin la vea en el panel.
    tipo_servicio = state.servicio_seleccionado.nombre
    if state.segmentacion_seleccionada:
        tipo_servicio = f"{tipo_servicio} · {state.segmentacion_seleccionada.nombre}"

    if state.ultimo_id_transaccion:
        await database_web.actualizar_tipo_servicio_async(
            state.ultimo_id_transaccion, tipo_servicio
        )

    nuevo_id = await database_web.guardar_pago_orden_async(
        state.ultimo_id_transaccion,
        metodo,
        precio_final,
        ingresado,
        cambio,
        modalidad,
    )

    if nuevo_id is None:
        ui.notify(
            "La orden ya no está disponible. Reiniciando...",
            type="negative",
            position="top",
        )
        state.reset()
        return

    state.procesar_exito(nuevo_id)
    notificar_admin()
    await asyncio.sleep(7)
    state.reset()

    state.procesar_exito(nuevo_id)
    notificar_admin()
    await asyncio.sleep(7)
    state.reset()


@ui.page("/")
def kiosko_cliente():
    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
    )
    ui.add_head_html('<link rel="stylesheet" href="/static/kiosko.css">')

    ui.add_head_html(
        """
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
    )

    @ui.refreshable
    def kiosko_ui():
        with ui.element("div").props("id=kiosko-root"):
            render_sidebar()

            with ui.element("div").props("id=main-col"):
                with ui.element("div").props("id=header"):
                    with ui.element("div").classes("logo-area"):
                        ui.image("/media/logo_slogan.png").style(
                            "width:50px;height:50px;object-fit:contain;"
                        )
                        ui.html('<span class="titulo">Lavanderia EcoLuna</span>')
                    ui.html(
                        '<div class="reloj" id="reloj-txt">--/--/----<br>--:--:--</div>'
                    )

                with ui.element("div").props("id=content"):
                    if not hardware.HARDWARE_AVAILABLE:

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
                                from services.hardware_hooks import on_moneda_ingresada

                                on_moneda_ingresada(val)
                            except Exception as ex:
                                print(f"Error: {ex}")

                        ui.keyboard(on_key=handle_keyboard)

                    if state.paso_actual == 0:
                        render_paso_servicio(kiosko_ui.refresh)

                    elif state.paso_actual == 1:
                        render_paso_nombre(kiosko_ui.refresh)

                    elif state.paso_actual == 2:
                        render_paso_peso(kiosko_ui.refresh)

                    elif state.paso_actual == 3:
                        render_paso_pago()

                    elif state.paso_actual == 4:
                        render_paso_exito()

    state.set_callback(kiosko_ui.refresh)
    set_kiosko_ui_ref(kiosko_ui.refresh)
    kiosko_ui()

    kiosko_client = _ng.context.client
    registrar_kiosko_client(kiosko_client)
    kiosko_client.on_disconnect(lambda c=kiosko_client: remover_kiosko_client(c))
