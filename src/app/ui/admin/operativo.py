"""Panel operativo (`@ui.page("/admin/operativo")`).

El operador ve:
- Órdenes `Pendiente-peso`: aprobar o rechazar.
- Órdenes `Pendiente-pago` (mostrador): confirmar pago en efectivo o cancelar.

Acciones: aprobar peso, rechazar peso, confirmar pago mostrador, cancelar pago.
La tarjeta se actualiza automáticamente cada 3 segundos.
"""

import asyncio
import os
from typing import Optional

from nicegui import app, ui

from app.core.estados import EstadoOrden
from app.eventos.bus import bus
from app.eventos.tipos import (
    EventoDominio,
    TIPO_ORDEN_CANCELADA,
    TIPO_PAGO_CANCELADO,
    TIPO_PAGO_CONFIRMADO,
    TIPO_PESO_APROBADO,
    TIPO_PESO_RECHAZADO,
)
from app.repo import transacciones
from app.ui.admin._componentes import (
    AccionTarjeta,
    boton_cerrar_sesion,
    render_header,
    render_seccion,
    tarjeta_orden,
)
from app.ui.compartido.auth import (
    redirigir_si_no_autenticado,
    usuario_actual,
)
from datetime import datetime


def _publicar(evento: EventoDominio) -> None:
    bus.publish(evento)


@ui.page("/admin/operativo")
async def admin_operativo():
    if redirigir_si_no_autenticado():
        return
    usuario = usuario_actual()
    render_header(usuario)

    @ui.refreshable
    async def contenido() -> None:
        contadores = await transacciones.contadores_pendientes()
        peso_pend = contadores.get(EstadoOrden.PENDIENTE_PESO.value, 0)
        pago_pend = contadores.get(
            EstadoOrden.PENDIENTE_PAGO.value, 0
        ) + contadores.get(EstadoOrden.PROCESANDO_PAGO.value, 0)

        with ui.element("div").props("id=admin-content"):
            ordenes_peso = await transacciones.listar_pendientes_operativo()
            solo_peso = [
                o
                for o in ordenes_peso
                if o["estado"] == EstadoOrden.PENDIENTE_PESO.value
            ]
            solo_pago = [
                o
                for o in ordenes_peso
                if o["estado"]
                in (
                    EstadoOrden.PENDIENTE_PAGO.value,
                    EstadoOrden.PROCESANDO_PAGO.value,
                )
            ]

            def _render_peso(o: dict) -> None:
                tarjeta_orden(
                    o,
                    [
                        AccionTarjeta(
                            label="✓ Aprobar peso",
                            color="positive",
                            handler=_aprobar_peso,
                        ),
                        AccionTarjeta(
                            label="✕ Rechazar",
                            color="negative",
                            handler=_rechazar_peso,
                        ),
                    ],
                )

            def _render_pago(o: dict) -> None:
                tarjeta_orden(
                    o,
                    [
                        AccionTarjeta(
                            label="✓ Confirmar pago",
                            color="positive",
                            handler=_confirmar_pago_mostrador,
                        ),
                        AccionTarjeta(
                            label="✕ Cancelar",
                            color="negative",
                            handler=_cancelar_pago,
                        ),
                    ],
                )

            render_seccion("scale", "Aprobar peso", solo_peso, _render_peso)
            render_seccion(
                "money-bag", "Confirmar pago (mostrador)", solo_pago, _render_pago
            )

            # Resumen al pie
            ui.html(
                f'<div style="margin-top:24px;padding:14px;background:#f1f5f9;'
                f'border-radius:8px;color:#475569;font-size:0.85rem;">'
                f"Total pendientes: <strong>{peso_pend + pago_pend}</strong> "
                f"(peso: {peso_pend} · pago: {pago_pend})</div>"
            )

    # Header estático: NO se re-renderiza con el timer. Solo se refresca
    # la lista de órdenes (contenido) sin perder el scroll del usuario.
    with ui.element("div").props("id=admin-content"):
        ui.html(
            '<h2 style="font-size:1.5rem;font-weight:800;color:#1e293b;'
            'margin-bottom:6px;display:flex;align-items:center;gap:10px;">'
            '<img src="/media/icons/inbox.svg" style="width:32px;height:32px;">'
            "Panel Operativo</h2>"
        )
        ui.html(
            f'<p style="color:#64748b;margin-bottom:24px;">'
            f"Aprueba pesos y confirma pagos en mostrador. Operador: <strong>{usuario}</strong>.</p>"
        )
        # El contenido refrescable va en su propio contenedor.
        with ui.element("div").props("id=operativo-contenido"):
            await contenido()
        with ui.row().classes("w-full justify-end mt-4"):
            ui.button("Servicio de cortesía", icon="star", on_click=_abrir_bypass)

    # NO usamos ui.timer() con .refresh() porque:
    # 1. Reemplaza el DOM entero y regresa el scroll al inicio.
    # 2. El usuario debe poder escribir en inputs sin que se cierre.
    # 3. Las nuevas órdenes del kiosko cliente se notifican al bus,
    #    y el bus tiene suscriptores en otros tabs. Aquí solo refrescamos
    #    cuando hay un evento real del bus (en lugar de polling).
    # Para forzar un refresh manual, el operador puede recargar F5.
    from app.eventos.bus import bus
    from app.eventos.tipos import (
        TIPO_ORDEN_CREADA,
        TIPO_ORDEN_CANCELADA,
        TIPO_PAGO_CONFIRMADO,
        TIPO_PESO_APROBADO,
        TIPO_PESO_RECHAZADO,
    )

    cola_admin = bus.subscribe(TIPO_ORDEN_CREADA)
    colas = [
        bus.subscribe(t)
        for t in (
            TIPO_ORDEN_CANCELADA,
            TIPO_PESO_APROBADO,
            TIPO_PESO_RECHAZADO,
            TIPO_PAGO_CONFIRMADO,
        )
    ]
    colas.append(cola_admin)

    async def _consumir_eventos_admin():
        while True:
            await cola_admin.get()
            contenido.refresh()

    asyncio.create_task(_consumir_eventos_admin())

    boton_cerrar_sesion()


# ── Acciones ────────────────────────────────────────────────────────────────


async def _aprobar_peso(o: dict) -> None:
    oid = o["id_transaccion"]
    peso = o.get("peso_kg", 0) or 0
    usuario = usuario_actual()
    await transacciones.aprobar_peso(oid, peso, usuario)
    _publicar(
        EventoDominio(
            tipo=TIPO_PESO_APROBADO,
            orden_id=oid,
            extra={"peso_kg": peso, "usuario": usuario},
            cuando=datetime.now(),
        )
    )
    ui.notify(f"Peso aprobado · Orden #{oid}", type="positive")


async def _rechazar_peso(o: dict) -> None:
    oid = o["id_transaccion"]
    await transacciones.rechazar_peso(oid)
    _publicar(
        EventoDominio(
            tipo=TIPO_PESO_RECHAZADO,
            orden_id=oid,
            extra={},
            cuando=datetime.now(),
        )
    )
    ui.notify(f"Peso rechazado · Orden #{oid}", type="warning")


async def _confirmar_pago_mostrador(o: dict) -> None:
    """Confirma el pago de mostrador: la orden pasa a Pendiente."""
    oid = o["id_transaccion"]
    folio = o.get("numero_transaccion_terminal", "") or ""
    usuario = usuario_actual()
    await transacciones.aprobar_pago_terminal(oid, folio, usuario)
    _publicar(
        EventoDominio(
            tipo=TIPO_PAGO_CONFIRMADO,
            orden_id=oid,
            extra={"folio": folio, "metodo": "mostrador"},
            cuando=datetime.now(),
        )
    )
    ui.notify(f"Pago confirmado · Orden #{oid}", type="positive")


async def _cancelar_pago(o: dict) -> None:
    oid = o["id_transaccion"]
    await transacciones.cancelar_pago_pendiente(oid)
    _publicar(
        EventoDominio(
            tipo=TIPO_PAGO_CANCELADO,
            orden_id=oid,
            extra={},
            cuando=datetime.now(),
        )
    )
    _publicar(
        EventoDominio(
            tipo=TIPO_ORDEN_CANCELADA,
            orden_id=oid,
            extra={},
            cuando=datetime.now(),
        )
    )
    ui.notify(f"Orden #{oid} cancelada", type="warning")


# ── Bypass ──────────────────────────────────────────────────────────────────


def _abrir_bypass() -> None:
    pwd_input_ref: dict = {"input": None}

    async def ejecutar() -> None:
        pwd = pwd_input_ref["input"].value if pwd_input_ref["input"] else ""
        if pwd != os.getenv("BYPASS_PASSWORD", "admin123"):
            ui.notify("Contraseña incorrecta", type="negative")
            return
        await transacciones.crear_orden(
            tipo_servicio="Cortesía / Bypass",
            monto=0,
            dinero_ingresado=0,
            cambio_devuelto=0,
            id_equipo="N/A",
            duracion_estimada_min=45,
            nombre_cliente="Cortesía",
            peso_kg=0,
            modalidad="autoservicio",
            estado="Pendiente",
        )
        dialogo.close()
        pwd_input_ref["input"].value = ""
        ui.notify("Servicio de cortesía creado", type="positive")

    with ui.dialog() as dialogo, ui.card().style("min-width:300px;"):
        ui.label("Autorizar Servicio de Cortesía").classes(
            "text-lg font-bold text-slate-800 mb-2"
        )
        pwd_input_ref["input"] = (
            ui.input("Contraseña").props("type=password").classes("w-full mb-4")
        )
        with ui.row().classes("w-full justify-end"):
            ui.button("Cancelar", on_click=dialogo.close).props("flat")
            ui.button("Autorizar", on_click=ejecutar).props("color=green")
    dialogo.open()
