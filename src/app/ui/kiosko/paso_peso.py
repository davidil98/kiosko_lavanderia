"""Paso 3: Pesar ropa.

Tres sub-estados visuales (orden de precedencia):
- `wizard.esperando_admin is not None`: overlay de espera (aprobación de peso
  o confirmación de pago Point/mostrador).
- `wizard.sub is Sub.SEGMENTACIONES`: elección de segmentación.
- (sub=Sub.METODOS_PAGO se renderiza en `paso_pago.py`).
- default: ingreso de peso con numpad.
"""

import asyncio
from datetime import datetime

from dataclasses import replace
from nicegui import ui

from app.core.estados import EstadoOrden
from app.core.precio import calcular_precio
from app.core.servicios import cargar_segmentaciones
from app.eventos.bus import bus
from app.eventos.tipos import (
    EventoDominio,
    TIPO_ORDEN_CANCELADA,
    TIPO_ORDEN_CREADA,
    TIPO_PAGO_CANCELADO,
    TIPO_PESO_APROBADO,
    TIPO_PESO_RECHAZADO,
)
from app.repo import transacciones
from app.ui.kiosko.wizard import Sub, WizardKiosko


def render_paso_peso(wizard: WizardKiosko, refresh) -> None:
    if wizard.esperando_admin is not None:
        _render_esperando_admin(wizard, refresh)
        return
    if wizard.sub == Sub.SEGMENTACIONES:
        _render_segmentaciones(wizard, refresh)
        return
    _render_ingreso_peso(wizard, refresh)


# ── Overlay de espera (admin) ────────────────────────────────────────────────


def _render_esperando_admin(wizard: WizardKiosko, refresh) -> None:
    motivo, metodo = wizard.esperando_admin
    if motivo == "peso":
        titulo = "Validando peso con el operador"
        mensaje = (
            "Por favor espera mientras el operador revisa el peso "
            f"de tu ropa (<strong>{wizard.peso} kg</strong>)."
        )
    elif metodo == "point":
        titulo = "Procesando pago con Point"
        mensaje = (
            "Acerca tu tarjeta o dispositivo a la terminal Point cuando "
            "te lo indique el operador. La confirmación es automática."
        )
    elif metodo == "mostrador":
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
                <img src="/media/icons/gear.svg"
                     style="width:64px;height:64px;animation:spin 2s linear infinite;opacity:0.7;"
                     onerror="this.style.display='none'">
                <style>@keyframes spin{{100%{{transform:rotate(360deg)}}}}</style>
                <div style="margin-top:12px;font-size:0.85rem;color:#64748b;">
                    No cierres esta ventana
                </div>
            </div>
        </div>
    """)
    ui.button(
        "← Regresar",
        on_click=lambda: _regresar(wizard, refresh),
    ).classes("btn-confirmar-nombre max-w-xs mx-auto mt-6").style("background:#334155;")


async def _regresar(wizard: WizardKiosko, refresh) -> None:
    if wizard.esperando_admin is None:
        return
    motivo, metodo = wizard.esperando_admin
    if motivo == "peso" and wizard.ultimo_id_transaccion is not None:
        await transacciones.rechazar_peso(wizard.ultimo_id_transaccion)
        bus.publish(
            EventoDominio(
                tipo=TIPO_ORDEN_CANCELADA,
                orden_id=wizard.ultimo_id_transaccion,
                extra={},
                cuando=datetime.now(),
            )
        )
        refresh(wizard.volver_a_pesar())
        return
    if wizard.ultimo_id_transaccion is None:
        refresh(wizard.volver_a_pesar())
        return
    if metodo == "point":
        from app.adaptadores.mercado_pago import point as mp_point

        mp_id = await transacciones.obtener_mp_order_id(wizard.ultimo_id_transaccion)
        if mp_id:
            await asyncio.to_thread(mp_point.cancelar_orden, mp_id)
    await transacciones.cancelar_pago_pendiente(wizard.ultimo_id_transaccion)
    bus.publish(
        EventoDominio(
            tipo=TIPO_PAGO_CANCELADO,
            orden_id=wizard.ultimo_id_transaccion,
            extra={},
            cuando=datetime.now(),
        )
    )
    refresh(wizard.volver_a_pesar())


# ── Sub-menú de segmentaciones ──────────────────────────────────────────────


def _render_segmentaciones(wizard: WizardKiosko, refresh) -> None:
    if wizard.servicio is None:
        refresh(replace(wizard, sub=Sub.NINGUNO))
        return
    segs = cargar_segmentaciones(servicio_id=wizard.servicio.id, solo_activos=True)
    if not segs:
        # El servicio no tiene segmentaciones: saltar a métodos de pago.
        refresh(replace(wizard, sub=Sub.NINGUNO).mostrar_metodos_pago())
        return

    ui.html(
        f'<p class="instruccion">Elige la opción para '
        f"<strong>{wizard.servicio.nombre}</strong></p>"
    )
    ui.html(
        f'<div style="text-align:center;font-size:0.85rem;color:#94a3b8;margin-bottom:18px;">'
        f'Peso registrado: <strong style="color:#e2e8f0;">{wizard.peso} kg</strong>'
        f"</div>"
    )
    with ui.element("div").style(
        "display:flex; gap:18px; flex-wrap:wrap; justify-content:center;"
    ):
        for seg in segs:
            precio = calcular_precio(seg, wizard.peso)
            with (
                ui.element("div")
                .classes("card-servicio")
                .style("max-width:240px;")
                .on(
                    "click",
                    lambda sid=seg.id: refresh(wizard.seleccionar_segmentacion(sid)),
                )
            ):
                ui.html(
                    f'<span style="font-size:1.1rem;font-weight:800;color:#e2e8f0;">{seg.nombre}</span>'
                )
                if seg.descripcion:
                    ui.html(
                        f'<span style="font-size:0.78rem;color:#94a3b8;text-align:center;">{seg.descripcion}</span>'
                    )
                if seg.tipo_calculo == "por_kg":
                    ui.html(
                        f'<span style="font-size:0.78rem;color:#64748b;">'
                        f"${int(seg.tarifa_por_kg)}/kg × {wizard.peso}kg = "
                        f'<strong style="color:#3b82f6;font-size:1.4rem;">${precio}</strong></span>'
                    )
                else:
                    ui.html(
                        f'<span style="font-size:1.5rem;font-weight:800;color:#3b82f6;">${precio}</span>'
                    )
                if seg.duracion_min:
                    ui.html(
                        f'<span style="font-size:0.72rem;color:#64748b;">≈ {seg.duracion_min} min</span>'
                    )

    ui.button(
        "← Volver a pesar",
        on_click=lambda: refresh(wizard.volver_a_pesar()),
    ).classes("btn-confirmar-nombre max-w-xs mx-auto mt-6").style("background:#334155;")


# ── Numpad de ingreso de peso ───────────────────────────────────────────────


def _render_ingreso_peso(wizard: WizardKiosko, refresh) -> None:
    if wizard.peso_rechazado_notificado:
        ui.notify(
            "El operador pidió volver a pesar. Ingresa el peso correcto.",
            type="warning",
            position="top",
            timeout=8000,
        )
        wizard = replace(wizard, peso=0.0, peso_rechazado_notificado=False)

    max_kg = wizard.limite_kg()
    peso_buffer = {"val": "0"}

    with ui.element("div").props("id=nombre-panel").classes("mx-auto"):
        with ui.element("div").style(
            "display:flex;align-items:center;gap:10px;margin-bottom:6px;"
        ):
            ui.html(
                '<img src="/media/icons/scale.svg" '
                'style="width:32px;height:32px;object-fit:contain;" '
                'alt="Escala">'
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
        preview_precio = ui.html("")

        def _parsear(v: str) -> float:
            try:
                return float(v) if v not in ("", ".") else 0.0
            except ValueError:
                return 0.0

        def presionar_num(d: str) -> None:
            nonlocal wizard
            v = peso_buffer["val"]
            if d == "⌫":
                v = v[:-1] if len(v) > 1 else "0"
            elif d == ".":
                if "." not in v:
                    v += "."
            elif v == "0":
                v = d
            elif len(v) < 5:
                v += d
            peso_buffer["val"] = v
            wizard = replace(wizard, peso=_parsear(v))
            display_peso.set_text(f"{v} kg")
            _actualizar_preview(wizard, preview_precio)

        with ui.element("div").classes("numpad mx-auto mt-2").style("max-width:280px;"):
            for d in ["7", "8", "9", "4", "5", "6", "1", "2", "3", ".", "0", "⌫"]:
                color = (
                    "bg-red-900"
                    if d == "⌫"
                    else ("bg-slate-600" if d == "." else "bg-slate-700")
                )
                ui.button(d, on_click=lambda x=d: presionar_num(x)).classes(
                    f"numpad-btn {color} text-white font-bold"
                )

        _actualizar_preview(wizard, preview_precio)

        async def enviar_peso_a_revision() -> None:
            nonlocal wizard
            if wizard.peso <= 0:
                ui.notify(
                    "Por favor ingresa un peso válido mayor a 0.",
                    type="warning",
                )
                return
            if max_kg and wizard.peso > max_kg:
                ui.notify(
                    f"Retire peso de carga que no exceda los {max_kg} kg "
                    f"y divida su carga solicitando más servicios.",
                    type="negative",
                )
                peso_buffer["val"] = "0"
                display_peso.set_text("0 kg")
                wizard = replace(wizard, peso=0.0)
                _actualizar_preview(wizard, preview_precio)
                return
            if wizard.servicio is None:
                return
            modalidad = (
                "personalizado" if wizard.servicio.es_personalizado else "autoservicio"
            )
            nuevo_id = await transacciones.crear_orden_pendiente_peso(
                tipo_servicio=wizard.servicio.nombre,
                peso_kg=wizard.peso,
                nombre_cliente=wizard.nombre or "Cliente",
                duracion_estimada_min=wizard.servicio.duracion_min,
                modalidad=modalidad,
            )
            bus.publish(
                EventoDominio(
                    tipo=TIPO_ORDEN_CREADA,
                    orden_id=nuevo_id,
                    extra={
                        "servicio": wizard.servicio.nombre,
                        "peso_kg": wizard.peso,
                        "nombre": wizard.nombre or "Cliente",
                        "modalidad": modalidad,
                    },
                    cuando=datetime.now(),
                )
            )
            nuevo = replace(
                wizard,
                ultimo_id_transaccion=nuevo_id,
                esperando_admin=("peso", ""),
            )
            refresh(nuevo)

        ui.button(
            "Continuar",
            on_click=enviar_peso_a_revision,
        ).classes("btn-confirmar-nombre max-w-sm mx-auto mt-4")


def _actualizar_preview(wizard: WizardKiosko, preview_precio) -> None:
    if wizard.servicio and wizard.servicio.tipo_calculo == "por_kg":
        precio = calcular_precio(wizard.servicio, wizard.peso)
        preview_precio.set_content(
            f'<div style="text-align:center;margin-top:14px;padding:10px;background:#1e293b;border-radius:8px;">'
            f'<span style="color:#94a3b8;font-size:0.78rem;">Precio estimado: </span>'
            f'<span style="color:#3b82f6;font-size:1.3rem;font-weight:800;">${precio}</span>'
            f'<span style="color:#64748b;font-size:0.7rem;"> '
            f"(${int(wizard.servicio.tarifa_por_kg)}/kg × {wizard.peso}kg)</span>"
            f"</div>"
        )
    else:
        preview_precio.set_content("")
