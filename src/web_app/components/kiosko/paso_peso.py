import asyncio
from nicegui import ui
from metodos_pago import METODOS_PAGO_DISPONIBLES
import database_web
from services.notifications import state, notificar_admin, notificar_kiosko


async def _eliminar_orden_activa_si_existe(id_transaccion):
    if not id_transaccion:
        return
    conn = database_web._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM transacciones WHERE id_transaccion = ? "
        "AND estado IN ('Pendiente-peso', 'Procesando-pago', 'Pendiente-pago')",
        (id_transaccion,),
    )
    conn.commit()
    conn.close()


async def _kiosko_regresar_espera(kiosko_ui_ref):
    if state.motivo_espera == "peso" and state.ultimo_id_transaccion:
        await database_web.rechazar_peso_async(state.ultimo_id_transaccion, "cliente")
        state.ultimo_id_transaccion = None
        state.peso_ingresado = 0.0
        state.peso_en_revision = 0.0
        state.paso_actual = 2
        state.mostrando_metodos_pago = False
        state.limpiar_espera_admin()
        notificar_admin()
    elif state.motivo_espera == "pago" and state.ultimo_id_transaccion:
        await database_web.cancelar_pago_pendiente_async(
            state.ultimo_id_transaccion, "cliente"
        )
        state.mostrando_metodos_pago = True
        state.limpiar_espera_admin()
        notificar_admin()


async def seleccionar_metodo_pago(metodo_cls, kiosko_ui_ref):
    state.metodo_pago_instancia = metodo_cls(state)
    state.metodo_pago_codigo = metodo_cls.codigo
    state.paso_actual = 3
    if kiosko_ui_ref:
        kiosko_ui_ref()


async def finalizar_servicio_personalizado():
    if state.ultimo_id_transaccion is None:
        notificar_kiosko(
            "No hay una orden activa. Vuelve a ingresar el peso.", tipo="negative"
        )
        return
    id_orden = await database_web.marcar_pendiente_pago_async(
        state.ultimo_id_transaccion,
        state.servicio_seleccionado.precio,
        modalidad="personalizado-pendiente-pago",
    )
    if id_orden is None:
        id_orden = await database_web.registrar_venta_pendiente_terminal_async(
            servicio=state.servicio_seleccionado.nombre,
            peso_kg=state.peso_ingresado,
            monto=state.servicio_seleccionado.precio,
            nombre_cliente=state.nombre_cliente,
            duracion=state.servicio_seleccionado.duracion_min,
            modalidad="personalizado-pendiente-pago",
        )
    state.ultimo_id_transaccion = id_orden
    state.metodo_pago_codigo = "mostrador"
    state.marcar_esperando_admin("pago")
    state.notificar_admin()


def render_paso_peso(kiosko_ui_ref):
    if state.esperando_aprobacion_admin:
        _render_esperando_admin(kiosko_ui_ref)
    elif state.mostrando_metodos_pago:
        _render_metodos_pago(kiosko_ui_ref)
    else:
        _render_ingreso_peso(kiosko_ui_ref)


def _render_esperando_admin(kiosko_ui_ref):
    if state.motivo_espera == "peso":
        titulo = "Validando peso con el operador"
        mensaje = (
            "Por favor espera mientras el operador revisa el peso "
            f"de tu ropa (<strong>{state.peso_en_revision} kg</strong>)."
        )
    elif state.metodo_pago_codigo == "mostrador":
        titulo = "Esperando confirmación de pago"
        mensaje = (
            "Acércate al mostrador para realizar el pago en efectivo. "
            "El operador confirmará tu pago para continuar."
        )
    else:
        titulo = "Procesando pago"
        mensaje = (
            "El operador está procesando tu pago en la terminal. "
            "Acerca tu tarjeta o dispositivo cuando te lo indique."
        )

    ui.html(f"""
        <div id="exito-panel" style="max-width:420px;">
            <div class="exito-titulo" style="color:#93c5fd;">{titulo}</div>
            <div class="exito-subtitulo" style="font-size:1rem;">{mensaje}</div>
            <div class="exito-datos" style="text-align:center;margin:20px 0;">
                <img src="/media/icons/gear.svg" style="width:64px;height:64px;animation:spin 2s linear infinite;opacity:0.7;" onerror="this.style.display='none'">
                <style>@keyframes spin{{100%{{transform:rotate(360deg)}}}}</style>
                <div style="margin-top:12px;font-size:0.85rem;color:#64748b;">No cierres esta ventana</div>
            </div>
        </div>
    """)
    ui.button(
        "\u2190 Regresar",
        on_click=lambda: asyncio.create_task(
            _kiosko_regresar_espera(kiosko_ui_ref)
        ),
    ).classes("btn-confirmar-nombre max-w-xs mx-auto mt-6").style(
        "background:#334155;"
    )


def _render_metodos_pago(kiosko_ui_ref):
    ui.html('<p class="instruccion">¿Cómo deseas pagar?</p>')
    es_personalizado = (
        state.servicio_seleccionado
        and state.servicio_seleccionado.modalidad == "personalizado"
    )
    with ui.element("div").style(
        "display:flex; gap:24px; flex-wrap:wrap; justify-content:center;"
    ):
        for metodo_cls in METODOS_PAGO_DISPONIBLES:
            if es_personalizado and metodo_cls.codigo == "monedas":
                continue
            with (
                ui.element("div")
                .classes("card-servicio")
                .on(
                    "click",
                    lambda cls=metodo_cls: (
                        asyncio.create_task(
                            seleccionar_metodo_pago(cls, kiosko_ui_ref)
                        )
                    ),
                )
            ):
                ui.image(metodo_cls.icono).style(
                    "width:80px;height:80px;object-fit:contain;"
                )
                ui.html(
                    f'<span style="font-size:1.2rem;font-weight:800;color:#e2e8f0;">{metodo_cls.nombre}</span>'
                )
                ui.html(
                    f'<span style="font-size:0.78rem;color:#94a3b8;">{metodo_cls.descripcion}</span>'
                )

    if es_personalizado:
        ui.button(
            "Pagar en mostrador al recibir",
            on_click=lambda: asyncio.create_task(
                finalizar_servicio_personalizado()
            ),
        ).classes("btn-confirmar-nombre max-w-sm mx-auto mt-4").style(
            "background:#a78bfa;"
        )

    async def _cancelar_desde_metodos_pago():
        await _eliminar_orden_activa_si_existe(state.ultimo_id_transaccion)
        state.ultimo_id_transaccion = None
        state.reset()
        notificar_admin()

    ui.button(
        "\u2715 Cancelar orden",
        on_click=lambda: asyncio.create_task(
            _cancelar_desde_metodos_pago()
        ),
    ).classes("btn-confirmar-nombre max-w-xs mx-auto mt-6").style(
        "background:#991b1b;color:#fecaca;"
    )


def _render_ingreso_peso(kiosko_ui_ref):
    if state.peso_rechazado_notificado:
        ui.notify(
            "El operador pidió volver a pesar. Ingresa el peso correcto.",
            type="warning",
            position="top",
            timeout=8000,
        )
        state.peso_rechazado_notificado = False

    state.peso_ingresado = 0.0
    peso_buffer = {"val": "0"}
    max_kg = state.get_limite_kg()

    with ui.element("div").props("id=nombre-panel").classes("mx-auto"):
        with ui.element("div").style(
            "display:flex;align-items:center;gap:10px;margin-bottom:6px;"
        ):
            ui.image("/media/icons/scale.svg").style(
                "width:32px;height:32px;object-fit:contain;"
            )
            ui.label("Ingresa el peso de tu ropa").style(
                "font-size:1.5rem;font-weight:800;color:#e2e8f0;margin:0;"
            )
        ui.label("Pesa tu ropa en la báscula e ingresa el valor (kg).").style(
            "font-size:0.95rem;color:#94a3b8;margin-bottom:6px;"
        )
        if max_kg:
            ui.html(
                f'<div style="font-size:0.85rem;color:#fde68a;font-weight:700;margin-bottom:10px;">'
                f"Capacidad máxima: {max_kg} kg</div>"
            )

        display_peso = ui.label("0 kg").classes("numpad-display")

        def presionar_num(d):
            v = peso_buffer["val"]
            if d == "\u232b":
                v = v[:-1] if len(v) > 1 else "0"
            elif d == ".":
                if "." not in v:
                    v += "."
            elif v == "0":
                v = d
            else:
                if len(v) < 5:
                    v += d
            peso_buffer["val"] = v
            state.peso_ingresado = float(v) if v not in ("", ".") else 0.0
            display_peso.set_text(f"{v} kg")

        with ui.element("div").classes("numpad mx-auto mt-2").style(
            "max-width:280px;"
        ):
            for d in [
                "7", "8", "9", "4", "5", "6", "1", "2", "3",
                ".", "0", "\u232b",
            ]:
                color = (
                    "bg-red-900"
                    if d == "\u232b"
                    else ("bg-slate-600" if d == "." else "bg-slate-700")
                )
                ui.button(
                    d, on_click=lambda x=d: presionar_num(x)
                ).classes(f"numpad-btn {color} text-white font-bold")

        async def enviar_peso_a_revision():
            if state.peso_ingresado <= 0:
                notificar_kiosko(
                    "Por favor ingresa un peso válido mayor a 0.",
                    tipo="warning",
                )
                return
            if max_kg and state.peso_ingresado > max_kg:
                notificar_kiosko(
                    f"Retire peso de carga que no exceda los {max_kg} kg "
                    f"y divida su carga solicitando más servicios.",
                    tipo="negative",
                )
                state.peso_ingresado = 0.0
                peso_buffer["val"] = "0"
                display_peso.set_text("0 kg")
                return
            nuevo_id = await database_web.registrar_venta_pendiente_peso_async(
                servicio=state.servicio_seleccionado.nombre,
                peso_kg=state.peso_ingresado,
                nombre_cliente=state.nombre_cliente,
                duracion=state.servicio_seleccionado.duracion_min,
                modalidad=state.servicio_seleccionado.modalidad,
            )
            state.ultimo_id_transaccion = nuevo_id
            state.peso_en_revision = state.peso_ingresado
            state.marcar_esperando_admin("peso")
            notificar_admin()

        ui.button(
            "Continuar",
            on_click=lambda: asyncio.create_task(
                enviar_peso_a_revision()
            ),
        ).classes("btn-confirmar-nombre max-w-sm mx-auto mt-4")
