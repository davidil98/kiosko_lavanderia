import asyncio
import os
from nicegui import ui, app
import nicegui as _ng

import hardware
import database_web
from services.auth import redirigir_si_no_autenticado, usuario_actual, USUARIOS
from services.notifications import (
    state,
    notificar_admin,
    notificar_kiosko,
    registrar_callback_operativo,
    remover_callback_operativo,
    registrar_admin_client,
    remover_admin_client,
    get_admin_client,
)
from components.admin.header import render_admin_header
from components.admin.operativo_seccion import (
    render_esperando_peso,
    render_procesando_pago,
)
from components.shared import render_seccion


@ui.page("/admin/operativo")
async def admin_operativo():
    if redirigir_si_no_autenticado():
        return

    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
    )
    ui.add_head_html('<link rel="stylesheet" href="/static/admin.css">')

    page_client = _ng.context.client
    client_id = registrar_admin_client(page_client)
    page_client.on_disconnect(lambda c=page_client: remover_admin_client(client_id))

    def _client():
        return get_admin_client(client_id)

    # ── Bypass Dialog ──
    async def ejecutar_bypass():
        pwd = input_bypass_pwd.value
        if pwd == os.getenv("BYPASS_PASSWORD", "admin123"):
            await database_web.registrar_venta_async(
                servicio="Cortesía / Bypass",
                monto=0,
                ingresado=0,
                cambio=0,
                equipo="N/A",
                duracion=45,
                nombre_cliente="Cortesía",
                peso_kg=0,
                modalidad="autoservicio",
            )
            dialogo_bypass.close()
            input_bypass_pwd.value = ""
            ui.notify(
                "Servicio de cortesía creado y añadido a pendientes.", type="positive"
            )
            notificar_admin()
        else:
            ui.notify("Contraseña incorrecta", type="negative")

    with ui.dialog() as dialogo_bypass, ui.card().style("min-width:300px;"):
        ui.label("Autorizar Servicio de Cortesía").classes(
            "text-lg font-bold text-slate-800 mb-2"
        )
        input_bypass_pwd = (
            ui.input("Contraseña").props("type=password").classes("w-full mb-4")
        )
        with ui.row().classes("w-full justify-end"):
            ui.button("Cancelar", on_click=dialogo_bypass.close).props("flat")
            ui.button("Autorizar", on_click=ejecutar_bypass).props("color=green")

    # ── Cambio de usuario Dialog ──
    with ui.dialog() as dialogo_cambio, ui.card().style("min-width:320px;"):
        ui.label("Cambiar operador en turno").classes(
            "text-lg font-bold text-slate-800 mb-2"
        )
        sel_usuario = ui.select(
            list(USUARIOS.keys()), label="Selecciona usuario", value=usuario_actual()
        ).classes("w-full")
        input_cambio_pwd = (
            ui.input("Contraseña").props("type=password").classes("w-full mt-3 mb-4")
        )

        def confirmar_cambio():
            u = sel_usuario.value
            p = input_cambio_pwd.value
            if u in USUARIOS and USUARIOS[u] == p:
                app.storage.user["usuario"] = u
                ui.notify(f"Sesión cambiada a {u}", type="positive")
                dialogo_cambio.close()
                input_cambio_pwd.value = ""
                ui.navigate.to("/admin/operativo")
            else:
                ui.notify("Contraseña incorrecta", type="negative")

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancelar", on_click=dialogo_cambio.close).props("flat")
            ui.button("Confirmar", on_click=confirmar_cambio).props("color=primary")

    # ── Header ──
    def extra_bypass():
        ui.button(
            "Cortesía / Bypass",
            on_click=dialogo_bypass.open,
        ).props(
            "icon=img:/media/icons/ticket.svg outline color=primary size=sm"
        ).classes("font-bold")

    render_admin_header(
        icon_path="/media/icons/inbox.svg",
        title="Panel Operativo",
        back_url="/admin",
        extra_buttons=[extra_bypass],
        dialogo_cambio=dialogo_cambio,
    )

    # ── Vista de Órdenes ──
    @ui.refreshable
    async def vista_operativo():
        with ui.element("div").props("id=admin-content").style("width:100%;"):
            pendientes = await database_web.obtener_ordenes_pendientes_admin_async()

            esperando_peso = [v for v in pendientes if v["estado"] == "Pendiente-peso"]
            procesando_pago = [
                v
                for v in pendientes
                if v["estado"] in ("Procesando-pago", "Pendiente-pago")
            ]

            render_seccion(
                "scale",
                "Esperando validación de peso",
                "badge-pendiente",
                esperando_peso,
                lambda v: render_esperando_peso(v, aprobar_peso, rechazar_peso),
            )

            render_seccion(
                "ticket",
                "Procesando pago",
                "badge-en-proceso",
                procesando_pago,
                lambda v: render_procesando_pago(
                    v, confirmar_pago, cancelar_pago_pendiente_handler
                ),
            )

    # ── Handlers ──
    async def aprobar_peso(venta):
        await database_web.aprobar_peso_async(
            venta["id_transaccion"], venta.get("peso_kg", 0), usuario_actual()
        )
        state.peso_ingresado = venta.get("peso_kg", 0)
        state.mostrando_metodos_pago = True
        state.limpiar_espera_admin()
        cl = _client()
        if cl:
            with cl:
                ui.notify(
                    f"✓ Peso aprobado — {venta.get('nombre_cliente', 'Orden')} #{venta['id_transaccion']}",
                    type="positive",
                    position="top",
                )
        await vista_operativo.refresh()
        notificar_kiosko("Peso aprobado. Selecciona tu método de pago.", "positive")

    async def rechazar_peso(venta):
        await database_web.rechazar_peso_async(
            venta["id_transaccion"], usuario_actual()
        )
        state.peso_ingresado = 0.0
        state.peso_en_revision = 0.0
        state.peso_rechazado_notificado = True
        state.paso_actual = 2
        state.mostrando_metodos_pago = False
        state.limpiar_espera_admin()
        cl = _client()
        if cl:
            with cl:
                ui.notify(
                    f"↩ Peso rechazado — {venta.get('nombre_cliente', 'Orden')} #{venta['id_transaccion']}",
                    type="warning",
                    position="top",
                )
        await vista_operativo.refresh()
        notificar_kiosko("El administrador pidió volver a pesar.", "warning")

    async def confirmar_pago(venta, folio_input):
        # Las órdenes Point se confirman automáticamente desde la terminal
        if "point" in venta.get("modalidad", ""):
            cl = _client()
            if cl:
                with cl:
                    ui.notify(
                        "Este pago se confirma automáticamente desde la terminal Point.",
                        type="info",
                        position="top",
                    )
            return
        folio = folio_input.value.strip() if folio_input else ""
        await database_web.aprobar_pago_terminal_async(
            venta["id_transaccion"], folio, usuario_actual()
        )
        state.limpiar_espera_admin()
        modalidad = venta.get("modalidad", "")
        es_pers = "personalizado" in modalidad
        if es_pers:
            state.procesar_exito(venta["id_transaccion"])
        else:
            state.procesar_exito(venta["id_transaccion"])
        notificar_admin()
        cl = _client()
        if cl:
            with cl:
                ui.notify(
                    f"✓ Pago confirmado — Orden #{venta['id_transaccion']}",
                    type="positive",
                    position="top",
                )
        await vista_operativo.refresh()
        if es_pers:
            notificar_kiosko(
                "Pago confirmado. Acércate al mostrador para la recepción.", "positive"
            )
        else:
            notificar_kiosko("Pago confirmado. Gracias por tu compra.", "positive")
        await asyncio.sleep(7)
        state.reset()

    async def cancelar_pago_pendiente_handler(venta):
        await database_web.cancelar_pago_pendiente_async(
            venta["id_transaccion"], usuario_actual()
        )
        state.mostrando_metodos_pago = True
        state.limpiar_espera_admin()
        cl = _client()
        if cl:
            with cl:
                ui.notify(
                    f"✕ Pago cancelado — Orden #{venta['id_transaccion']}",
                    type="warning",
                    position="top",
                )
        await vista_operativo.refresh()
        notificar_kiosko("El pago fue cancelado. Puedes intentar de nuevo.", "warning")

    await vista_operativo()
    registrar_callback_operativo(vista_operativo.refresh)
    page_client.on_disconnect(
        lambda: remover_callback_operativo(vista_operativo.refresh)
    )
