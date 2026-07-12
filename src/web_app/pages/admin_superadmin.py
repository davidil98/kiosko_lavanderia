import os
import asyncio
from datetime import datetime, timedelta
from nicegui import ui
import nicegui as _ng
from nicegui_highcharts import highchart

import database_web
from services.auth import (
    redirigir_si_no_autenticado,
    redirigir_si_no_superadmin,
    usuario_actual,
)
from services.notifications import (
    registrar_callback_operativo,
    remover_callback_operativo,
)
from components.admin.header import render_admin_header
from models import cargar_servicios, cargar_segmentaciones, calcular_precio


@ui.page("/admin/superadmin")
async def admin_superadmin():
    if redirigir_si_no_autenticado() or redirigir_si_no_superadmin():
        return

    ui.add_head_html(
        '<link rel="preconnect" href="https://fonts.googleapis.com">'
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
    )
    ui.add_head_html('<link rel="stylesheet" href="/static/admin.css">')

    page_client = _ng.context.client
    client_id = page_client.id

    render_admin_header(
        icon_path="/media/icons/gear.svg",
        title="Superadministrador",
    )

    with ui.element("div").props("id=admin-content"):
        ui.html(
            '<div style="background:#fef3c7;border-left:4px solid #f59e0b;'
            "padding:12px 16px;margin-bottom:18px;border-radius:6px;"
            'color:#92400e;font-size:0.88rem;">'
            "<strong>Importante:</strong> Los cambios en servicios y "
            "segmentaciones se aplican al instante en la base de datos. "
            "El kiosko y el panel admin leen la lista en cada render, por "
            "lo que no requieren reinicio. El cambio de precio puede afectar "
            "órdenes en curso solo si aún no han pasado por aprobación de "
            "peso."
            "</div>"
        )

        with ui.tabs().classes("w-full") as tabs:
            tab_servicios = ui.tab("Servicios y Tarifas")
            tab_segmentos = ui.tab("Segmentaciones")
            tab_maquinas = ui.tab("Máquinas")
            tab_metricas = ui.tab("Métricas")
            tab_backup = ui.tab("Respaldo")
            tab_calc = ui.tab("Calculadora")

        with ui.tab_panels(tabs, value=tab_servicios).classes("w-full"):
            with ui.tab_panel(tab_servicios):
                await _render_tab_servicios(page_client, client_id)
            with ui.tab_panel(tab_segmentos):
                await _render_tab_segmentaciones(page_client, client_id)
            with ui.tab_panel(tab_maquinas):
                await _render_tab_maquinas(page_client, client_id)
            with ui.tab_panel(tab_metricas):
                await _render_tab_metricas(page_client, client_id)
            with ui.tab_panel(tab_backup):
                await _render_tab_backup(page_client, client_id)
            with ui.tab_panel(tab_calc):
                await _render_tab_calculadora()


# ── Tab Servicios ─────────────────────────────────────────────────────────────


async def _render_tab_servicios(page_client, client_id):
    """CRUD de servicios. Crear/editar/activar/desactivar."""

    @ui.refreshable
    async def lista_servicios():
        servicios = await database_web.listar_servicios_async(solo_activos=False)
        if not servicios:
            ui.html('<div class="empty-state">No hay servicios configurados.</div>')
            return
        for s in servicios:
            _render_servicio_card(s, lista_servicios, page_client)

    with ui.row().classes("w-full justify-end mb-3"):
        ui.button(
            "+ Crear servicio",
            on_click=lambda: _abrir_dialog_crear_servicio(lista_servicios, page_client),
        ).props("color=primary")

    await lista_servicios()


def _render_servicio_card(s, refreshable, page_client):
    tipo_label = {
        "fijo": "Precio fijo",
        "por_kg": "Por kilogramo",
        "por_duracion": "Por duración",
    }.get(s["tipo_calculo"], s["tipo_calculo"])
    activo_color = "#16a34a" if s["activo"] else "#94a3b8"
    activo_label = "Activo" if s["activo"] else "Inactivo"

    with (
        ui.element("div")
        .classes("orden-card")
        .style(f"border-left:4px solid {activo_color};")
    ):
        with ui.element("div").style("flex:1;min-width:0;"):
            ui.html(
                f'<div class="orden-numero">{s["codigo"]}</div>'
                f'<div style="font-size:1.1rem;font-weight:800;color:#1e293b;">{s["nombre"]}</div>'
                f'<div style="font-size:0.85rem;color:#64748b;">'
                f"Modalidad: <strong>{s['modalidad']}</strong> · "
                f"Tipo: <strong>{tipo_label}</strong> · "
                f'<span style="color:{activo_color};font-weight:700;">{activo_label}</span>'
                f"</div>"
                f'<div style="font-size:0.85rem;color:#64748b;margin-top:4px;">'
                f"Precio base: <strong>${s['precio_fijo'] or 0}</strong>"
                + (
                    f" · Tarifa/kg: <strong>${s['tarifa_por_kg']}</strong>"
                    if s["tipo_calculo"] == "por_kg"
                    else ""
                )
                + f" · Duración: <strong>{s['duracion_min']} min</strong>"
                + (
                    f" · Límite: <strong>{s['limite_kg']} kg</strong>"
                    if s["limite_kg"]
                    else ""
                )
                + f" · Tipos equipo: <strong>{s['tipos_equipo'] or 'cualquiera'}</strong>"
                + f"</div>"
            )
        with ui.element("div").style(
            "flex-shrink:0;display:flex;flex-direction:column;gap:8px;align-items:flex-end;"
        ):
            ui.label("✎ Editar").classes("btn-maquina btn-iniciar").on(
                "click",
                lambda e, sid=s["id"]: _abrir_editor_servicio(
                    sid, refreshable, page_client
                ),
            )
            toggle_label = "⏸ Desactivar" if s["activo"] else "▶ Activar"
            toggle_class = (
                "btn-maquina btn-pausar" if s["activo"] else "btn-maquina btn-iniciar"
            )
            ui.label(toggle_label).classes(toggle_class).on(
                "click",
                lambda e, sid=s["id"], act=s["activo"]: asyncio.create_task(
                    _toggle_servicio(sid, not act, refreshable, page_client)
                ),
            )
            ui.label("🗑").classes("btn-maquina btn-pausar").on(
                "click",
                lambda e, sid=s["id"], nom=s["nombre"]: asyncio.create_task(
                    _eliminar_servicio_handler(sid, nom, refreshable, page_client)
                ),
            )


async def _toggle_servicio(id_servicio, nuevo_activo, refreshable, page_client):
    s_fila = None
    servicios = await database_web.listar_servicios_async(solo_activos=False)
    for s in servicios:
        if s["id"] == id_servicio:
            s_fila = s
            break
    if not s_fila:
        return
    await database_web.actualizar_servicio_async(
        id_servicio,
        s_fila["nombre"],
        s_fila["tipo_calculo"],
        s_fila["precio_fijo"],
        s_fila["tarifa_por_kg"],
        s_fila["duracion_min"],
        s_fila["limite_kg"],
        s_fila["tipos_equipo"],
        nuevo_activo,
    )
    with page_client:
        ui.notify(
            f"Servicio {'activado' if nuevo_activo else 'desactivado'}.",
            type="positive",
            position="top",
        )
    refreshable.refresh()


async def _eliminar_servicio_handler(id_servicio, nombre, refreshable, page_client):
    # El dialog se crea dentro de un contexto async para que los ui.* tengan
    # acceso al cliente/socket correcto (de lo contrario quedan huerfanos y
    # el dialog nunca se muestra).
    await asyncio.sleep(0)
    with page_client:
        with ui.dialog() as dlg, ui.card().style("min-width:380px;"):
            ui.label("Eliminar servicio").classes(
                "text-lg font-bold text-slate-800 mb-2"
            )
            ui.html(
                f'<p style="color:#475569;margin-bottom:8px;">Vas a eliminar '
                f"<strong>{nombre}</strong>. Esta acción es <strong>irreversible</strong>."
                "</p>"
                '<p style="color:#94a3b8;font-size:0.85rem;">Solo se puede eliminar '
                "si ningún cliente tiene órdenes históricas con este servicio. Si "
                "existen, hazlo inactivo en su lugar.</p>"
            )
            pwd_in = (
                ui.input("Contraseña de bypass", password=True)
                .props("type=password")
                .classes("w-full")
            )

            async def _confirmar():
                if pwd_in.value != os.getenv("BYPASS_PASSWORD", "admin123"):
                    with page_client:
                        ui.notify(
                            "Contraseña incorrecta.",
                            type="negative",
                            position="top",
                        )
                    return
                ok = await database_web.eliminar_servicio_hard_async(id_servicio)
                if ok:
                    with page_client:
                        ui.notify(
                            f"Servicio '{nombre}' eliminado.",
                            type="positive",
                            position="top",
                        )
                    dlg.close()
                    refreshable.refresh()
                else:
                    with page_client:
                        ui.notify(
                            "No se puede eliminar: hay órdenes con este servicio. "
                            "Desactívalo en su lugar.",
                            type="negative",
                            position="top",
                            timeout=8000,
                        )
                    dlg.close()

            with ui.row().classes("w-full justify-end mt-3 gap-2"):
                ui.button("Cancelar", on_click=dlg.close).props("flat")
                ui.button("Eliminar", on_click=_confirmar).props("color=negative")

        dlg.open()


def _abrir_dialog_crear_servicio(refreshable, page_client):
    with ui.dialog() as dlg, ui.card().style("min-width:560px;max-width:720px;"):
        ui.label("Crear nuevo servicio").classes(
            "text-lg font-bold text-slate-800 mb-1"
        )
        ui.html(
            '<p style="font-size:0.78rem;color:#64748b;margin-bottom:14px;">'
            "Los campos marcados con <strong>*</strong> son obligatorios. "
            "Los demás se pueden dejar en blanco si no aplican a este servicio."
            "</p>"
        )

        # ── Identidad ─────────────────────────────────────────────────────
        ui.html(
            '<div style="font-size:0.85rem;font-weight:700;color:#475569;'
            'margin-top:6px;margin-bottom:4px;">Identidad</div>'
        )
        codigo_in = ui.input(
            "Código único * (sin espacios, ej. 'secado_express')"
        ).classes("w-full")
        nombre_in = ui.input("Nombre visible *").classes("w-full")
        modalidad_in = ui.select(
            {
                "autoservicio": "Autoservicio (cliente se atiende solo)",
                "personalizado": "Personalizado (lo entrega un operador)",
            },
            value="autoservicio",
            label="Modalidad *",
        ).classes("w-full")
        icono_in = ui.select(
            {
                "/media/icons/leaf.svg": "Hoja (default autoservicio)",
                "/media/icons/wind.svg": "Viento (secado)",
                "/media/icons/shirt.svg": "Camisa (personalizado ropa)",
                "/media/icons/bed.svg": "Cama (personalizado edredones)",
                "/media/icons/inbox.svg": "Bandeja (entregas)",
                "/media/icons/ticket.svg": "Ticket (punto Point)",
                "/media/icons/gear.svg": "Engranaje (general)",
            },
            value="/media/icons/leaf.svg",
            label="Icono (cómo se ve en el kiosko)",
        ).classes("w-full")

        # ── Cobro ────────────────────────────────────────────────────────
        ui.html(
            '<div style="font-size:0.85rem;font-weight:700;color:#475569;'
            'margin-top:14px;margin-bottom:4px;">Cobro</div>'
        )
        tipo_in = ui.select(
            {
                "fijo": "Precio fijo (ej. $45 por servicio completo)",
                "por_kg": "Por kilogramo (ej. $30/kg según el peso)",
                "por_duracion": "Por duración (ej. $X por Y minutos)",
            },
            value="fijo",
            label="Tipo de cálculo *",
        ).classes("w-full")
        precio_in = (
            ui.input("Precio fijo ($)", value="0")
            .props("type=number min=0")
            .classes("w-full")
        )
        tarifa_in = (
            ui.input("Tarifa por kg ($)", value="0")
            .props("type=number min=0 step=0.01")
            .classes("w-full")
        )
        duracion_in = (
            ui.input("Duración estimada (min)", value="45")
            .props("type=number min=1")
            .classes("w-full")
        )
        limite_in = (
            ui.input(
                "Límite de kg (vacío = sin límite)",
                value="",
                placeholder="ej. 5",
            )
            .props("type=number min=0")
            .classes("w-full")
        )

        # ── Compatibilidad con máquinas ───────────────────────────────────
        ui.html(
            '<div style="font-size:0.85rem;font-weight:700;color:#475569;'
            'margin-top:14px;margin-bottom:4px;">Compatibilidad con máquinas</div>'
        )
        tipos_equipo_in = ui.input(
            "Tipos de máquina permitidos (separa con comas)",
            value="",
            placeholder="ej. mixto, lavado  — o deja vacío para cualquiera",
        ).classes("w-full")
        ui.html(
            '<div style="font-size:0.72rem;color:#94a3b8;margin-top:2px;">'
            "Opciones válidas: <code>lavado</code>, <code>secado</code>, "
            "<code>mixto</code> (lava y seca), <code>doblado</code>. "
            "Vacío = cualquier máquina compatible."
            "</div>"
        )

        # ── Confirmación ──────────────────────────────────────────────────
        ui.html(
            '<div style="font-size:0.85rem;font-weight:700;color:#475569;'
            'margin-top:14px;margin-bottom:4px;">Confirmación</div>'
        )
        pwd_in = (
            ui.input("Contraseña de bypass").props("type=password").classes("w-full")
        )

        async def _guardar():
            # 1. Contraseña
            if pwd_in.value != os.getenv("BYPASS_PASSWORD", "admin123"):
                with page_client:
                    ui.notify(
                        "Contraseña incorrecta.",
                        type="negative",
                        position="top",
                    )
                return

            # 2. Código
            codigo = codigo_in.value.strip().lower().replace(" ", "_")
            if not codigo:
                with page_client:
                    ui.notify(
                        "El código es obligatorio.",
                        type="negative",
                        position="top",
                    )
                return
            if not all(c.isalnum() or c == "_" for c in codigo):
                with page_client:
                    ui.notify(
                        "El código solo puede tener letras, números y guiones bajos.",
                        type="negative",
                        position="top",
                    )
                return

            # 3. Nombre
            nombre = nombre_in.value.strip()
            if not nombre:
                with page_client:
                    ui.notify(
                        "El nombre es obligatorio.",
                        type="negative",
                        position="top",
                    )
                return

            # 4. Precio / tarifa según tipo
            tipo = tipo_in.value
            try:
                precio = int(precio_in.value or 0)
                tarifa = float(tarifa_in.value or 0)
            except (TypeError, ValueError):
                with page_client:
                    ui.notify(
                        "Precio y tarifa deben ser números.",
                        type="negative",
                        position="top",
                    )
                return
            if tipo == "fijo" and precio < 0:
                with page_client:
                    ui.notify(
                        "El precio fijo no puede ser negativo.",
                        type="negative",
                        position="top",
                    )
                return
            if tipo == "por_kg" and tarifa <= 0:
                with page_client:
                    ui.notify(
                        "Para cobrar por kilo, la tarifa debe ser mayor a 0.",
                        type="negative",
                        position="top",
                    )
                return
            if tipo == "por_duracion" and precio <= 0:
                with page_client:
                    ui.notify(
                        "Para cobrar por duración, el precio debe ser mayor a 0.",
                        type="negative",
                        position="top",
                    )
                return

            # 5. Duración
            try:
                duracion = int(duracion_in.value or 0)
            except (TypeError, ValueError):
                with page_client:
                    ui.notify(
                        "La duración debe ser un número entero de minutos.",
                        type="negative",
                        position="top",
                    )
                return
            if duracion <= 0:
                with page_client:
                    ui.notify(
                        "La duración debe ser mayor a 0 minutos.",
                        type="negative",
                        position="top",
                    )
                return

            # 6. Límite kg (opcional)
            limite = None
            if limite_in.value and str(limite_in.value).strip():
                try:
                    limite = int(limite_in.value)
                    if limite <= 0:
                        with page_client:
                            ui.notify(
                                "El límite de kg debe ser mayor a 0.",
                                type="negative",
                                position="top",
                            )
                        return
                except (TypeError, ValueError):
                    with page_client:
                        ui.notify(
                            "El límite de kg debe ser un número entero.",
                            type="negative",
                            position="top",
                        )
                    return

            # 7. Tipos de equipo (CSV)
            tipos_equipo_csv = tipos_equipo_in.value.strip()
            tipos_validos = {"lavado", "secado", "mixto", "doblado", ""}
            tipos_list = [t.strip() for t in tipos_equipo_csv.split(",") if t.strip()]
            tipos_invalidos = [t for t in tipos_list if t not in tipos_validos]
            if tipos_invalidos:
                with page_client:
                    ui.notify(
                        f"Tipos de equipo no válidos: {', '.join(tipos_invalidos)}. "
                        "Usa solo: lavado, secado, mixto, doblado.",
                        type="negative",
                        position="top",
                        timeout=8000,
                    )
                return
            tipos_equipo = ",".join(tipos_list)

            # 8. Insertar
            try:
                new_id = await database_web.crear_servicio_async(
                    codigo,
                    nombre,
                    modalidad_in.value,
                    icono_in.value,
                    tipo,
                    precio,
                    tarifa,
                    duracion,
                    limite,
                    tipos_equipo,
                )
                if new_id is None:
                    with page_client:
                        ui.notify(
                            f"Ya existe un servicio con código '{codigo}'.",
                            type="negative",
                            position="top",
                        )
                    return
                with page_client:
                    ui.notify(
                        f"Servicio '{nombre}' creado.",
                        type="positive",
                        position="top",
                    )
                dlg.close()
                refreshable.refresh()
            except Exception as e:
                with page_client:
                    ui.notify(f"Error: {e}", type="negative", position="top")

        with ui.row().classes("w-full justify-end mt-3 gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Crear", on_click=_guardar).props("color=primary")

    dlg.open()


def _abrir_editor_servicio(id_servicio, refreshable, page_client):
    """Diálogo de edición con BYPASS_PASSWORD como segunda barrera."""
    s_row = None
    servicios = database_web._listar_servicios(solo_activos=False)
    for s in servicios:
        if s["id"] == id_servicio:
            s_row = s
            break
    if not s_row:
        return

    with ui.dialog() as dlg, ui.card().style("min-width:520px;max-width:640px;"):
        ui.label(f"Editar servicio: {s_row['codigo']}").classes(
            "text-lg font-bold text-slate-800 mb-2"
        )

        nombre_in = ui.input("Nombre visible", value=s_row["nombre"]).classes("w-full")
        tipo_in = ui.select(
            ["fijo", "por_kg", "por_duracion"],
            value=s_row["tipo_calculo"],
            label="Tipo de cálculo",
        ).classes("w-full")
        precio_in = (
            ui.input(
                "Precio fijo ($)",
                value=str(s_row["precio_fijo"] or 0),
            )
            .props("type=number")
            .classes("w-full")
        )
        tarifa_in = (
            ui.input(
                "Tarifa por kg ($)",
                value=str(s_row["tarifa_por_kg"] or 0),
            )
            .props("type=number step=0.01")
            .classes("w-full")
        )
        duracion_in = (
            ui.input(
                "Duración (min)",
                value=str(s_row["duracion_min"] or 0),
            )
            .props("type=number")
            .classes("w-full")
        )
        limite_in = (
            ui.input(
                "Límite de kg (vacío = sin límite)",
                value=str(s_row["limite_kg"] or ""),
            )
            .props("type=number")
            .classes("w-full")
        )
        tipos_equipo_in = ui.input(
            "Tipos de equipo (CSV: mixto,lavado,secado)",
            value=s_row["tipos_equipo"] or "",
        ).classes("w-full")
        activo_in = ui.checkbox("Activo", value=bool(s_row["activo"])).classes("w-full")

        # Live calculadora
        calc_preview = ui.html("")

        def _actualizar_preview():
            try:
                peso = 3.0
                tarifa = float(tarifa_in.value or 0)
                precio = int(precio_in.value or 0)
                tipo = tipo_in.value
                if tipo == "fijo":
                    txt = f'<div style="background:#dbeafe;padding:10px;border-radius:6px;margin-top:8px;color:#1e40af;">Precio fijo: <strong>${precio}</strong></div>'
                elif tipo == "por_kg":
                    txt = f'<div style="background:#dbeafe;padding:10px;border-radius:6px;margin-top:8px;color:#1e40af;">Ejemplo: <strong>${int(round(tarifa * peso))}</strong> para {peso} kg</div>'
                else:
                    txt = f'<div style="background:#dbeafe;padding:10px;border-radius:6px;margin-top:8px;color:#1e40af;">Precio por {duracion_in.value} min: <strong>${precio}</strong></div>'
                calc_preview.set_content(txt)
            except (ValueError, TypeError):
                calc_preview.set_content("")

        for inp in (tipo_in, precio_in, tarifa_in, duracion_in):
            inp.on("update:model-value", lambda e: _actualizar_preview())
        _actualizar_preview()

        async def _guardar():
            pwd = pwd_in.value
            if pwd != os.getenv("BYPASS_PASSWORD", "admin123"):
                with page_client:
                    ui.notify("Contraseña incorrecta.", type="negative", position="top")
                return
            try:
                await database_web.actualizar_servicio_async(
                    id_servicio,
                    nombre_in.value.strip() or s_row["nombre"],
                    tipo_in.value,
                    int(precio_in.value or 0),
                    float(tarifa_in.value or 0),
                    int(duracion_in.value or 0),
                    int(limite_in.value) if limite_in.value else None,
                    tipos_equipo_in.value.strip(),
                    activo_in.value,
                )
                with page_client:
                    ui.notify(
                        f"Servicio '{nombre_in.value}' actualizado.",
                        type="positive",
                        position="top",
                    )
                dlg.close()
                refreshable.refresh()
            except Exception as e:
                with page_client:
                    ui.notify(f"Error guardando: {e}", type="negative", position="top")

        ui.separator().classes("my-3")
        ui.html(
            '<div style="font-size:0.78rem;color:#64748b;margin-bottom:6px;">'
            "Para confirmar, ingresa la contraseña de bypass."
            "</div>"
        )
        pwd_in = (
            ui.input("Contraseña de bypass", password=True)
            .props("type=password")
            .classes("w-full")
        )

        with ui.row().classes("w-full justify-end mt-3 gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Guardar cambios", on_click=_guardar).props("color=primary")

    dlg.open()


# ── Tab Segmentaciones ────────────────────────────────────────────────────────


async def _render_tab_segmentaciones(page_client, client_id):
    servicios = await database_web.listar_servicios_async(solo_activos=False)
    if not servicios:
        ui.html('<div class="empty-state">Crea servicios primero.</div>')
        return

    @ui.refreshable
    async def lista_segs_por_servicio():
        for s in servicios:
            segs = await database_web.listar_segmentaciones_async(
                servicio_id=s["id"], solo_activos=False
            )
            with ui.element("div").style("margin-bottom:20px;"):
                ui.html(
                    f'<div style="font-size:1.05rem;font-weight:800;color:#1e293b;'
                    f'margin-bottom:8px;display:flex;align-items:center;gap:8px;">'
                    f'<img src="{s["icono"] or "/media/icons/leaf.svg"}" '
                    f'style="width:24px;height:24px;">'
                    f"{s['nombre']} "
                    f'<span style="font-size:0.78rem;color:#64748b;font-weight:500;">'
                    f"({s['codigo']})</span></div>"
                )
                if not segs:
                    ui.html(
                        '<div style="font-size:0.85rem;color:#94a3b8;'
                        'margin-bottom:8px;">Sin segmentaciones. El kiosko '
                        "saltará directo a métodos de pago.</div>"
                    )
                else:
                    for seg in segs:
                        _render_segmento_row(seg, s, lista_segs_por_servicio)
                with ui.row().classes("w-full justify-end mt-1"):
                    ui.button(
                        "+ Crear segmentación",
                        on_click=lambda sid=s["id"]: _abrir_dialog_crear_segmento(
                            sid, lista_segs_por_servicio, page_client
                        ),
                    ).props("color=primary size=sm")

    def _render_segmento_row(seg, s_padre, refreshable):
        tipo_label = {
            "fijo": "Fijo",
            "por_kg": "Por kg",
            "por_duracion": "Por duración",
        }.get(seg["tipo_calculo"], seg["tipo_calculo"])
        activo_color = "#16a34a" if seg["activo"] else "#94a3b8"
        with (
            ui.element("div")
            .classes("orden-card")
            .style(f"border-left:4px solid {activo_color};padding:10px 14px;")
        ):
            with ui.element("div").style("flex:1;min-width:0;"):
                ui.html(
                    f'<div style="font-weight:800;color:#1e293b;">{seg["nombre"]}</div>'
                    f'<div style="font-size:0.78rem;color:#64748b;">'
                    f"Código: <code>{seg['codigo']}</code> · "
                    f"Tipo: {tipo_label} · "
                    f'Activo: <span style="color:{activo_color};font-weight:700;">{"Sí" if seg["activo"] else "No"}</span>'
                    f"</div>"
                    f'<div style="font-size:0.85rem;color:#475569;margin-top:2px;">'
                    + (
                        f"Precio: <strong>${seg['precio_fijo']}</strong>"
                        if seg["tipo_calculo"] != "por_kg"
                        else f"Tarifa: <strong>${seg['tarifa_por_kg']}/kg</strong>"
                    )
                    + f" · Duración: <strong>{seg['duracion_min']} min</strong>"
                    + f"</div>"
                    + (
                        f'<div style="font-size:0.78rem;color:#64748b;">{seg["descripcion"]}</div>'
                        if seg["descripcion"]
                        else ""
                    )
                )
            with ui.element("div").style(
                "flex-shrink:0;display:flex;flex-direction:column;gap:6px;align-items:flex-end;"
            ):
                ui.label("✎").classes("btn-maquina btn-iniciar").on(
                    "click",
                    lambda e, sid=seg["id"]: _abrir_editor_segmento(
                        sid, refreshable, page_client
                    ),
                )
                toggle_label = "⏸" if seg["activo"] else "▶"
                ui.label(toggle_label).classes("btn-maquina btn-pausar").on(
                    "click",
                    lambda e, sid=seg["id"], act=seg["activo"], sg=seg: (
                        asyncio.create_task(
                            _toggle_segmento(sg, not act, refreshable, page_client)
                        )
                    ),
                )
                ui.label("🗑").classes("btn-maquina btn-pausar").on(
                    "click",
                    lambda e, sid=seg["id"], nom=seg["nombre"]: asyncio.create_task(
                        _eliminar_segmento_handler(sid, nom, refreshable, page_client)
                    ),
                )

    async def _toggle_segmento(seg, nuevo_activo, refreshable, page_client):
        await database_web.actualizar_segmentacion_async(
            seg["id"],
            seg["nombre"],
            seg["descripcion"],
            seg["tipo_calculo"],
            seg["precio_fijo"],
            seg["tarifa_por_kg"],
            seg["duracion_min"],
            nuevo_activo,
        )
        with page_client:
            ui.notify(
                f"Segmentación {'activada' if nuevo_activo else 'desactivada'}.",
                type="positive",
                position="top",
            )
        refreshable.refresh()

    await lista_segs_por_servicio()


async def _eliminar_segmento_handler(id_seg, nombre, refreshable, page_client):
    await asyncio.sleep(0)
    with page_client:
        with ui.dialog() as dlg, ui.card().style("min-width:380px;"):
            ui.label("Eliminar segmentación").classes(
                "text-lg font-bold text-slate-800 mb-2"
            )
            ui.html(
                f'<p style="color:#475569;margin-bottom:8px;">Vas a eliminar '
                f"<strong>{nombre}</strong>. Esta acción es <strong>irreversible</strong>."
                "</p>"
                '<p style="color:#94a3b8;font-size:0.85rem;">Solo se puede eliminar '
                "si ningún cliente tiene órdenes con esta segmentación. Si existen, "
                "desactívala en su lugar.</p>"
            )
            pwd_in = (
                ui.input("Contraseña de bypass", password=True)
                .props("type=password")
                .classes("w-full")
            )

            async def _confirmar():
                if pwd_in.value != os.getenv("BYPASS_PASSWORD", "admin123"):
                    with page_client:
                        ui.notify(
                            "Contraseña incorrecta.",
                            type="negative",
                            position="top",
                        )
                    return
                ok = await database_web.eliminar_segmentacion_hard_async(id_seg)
                if ok:
                    with page_client:
                        ui.notify(
                            f"Segmentación '{nombre}' eliminada.",
                            type="positive",
                            position="top",
                        )
                    dlg.close()
                    refreshable.refresh()
                else:
                    with page_client:
                        ui.notify(
                            "No se puede eliminar: hay órdenes con esta segmentación. "
                            "Desactívala en su lugar.",
                            type="negative",
                            position="top",
                            timeout=8000,
                        )
                    dlg.close()

            with ui.row().classes("w-full justify-end mt-3 gap-2"):
                ui.button("Cancelar", on_click=dlg.close).props("flat")
                ui.button("Eliminar", on_click=_confirmar).props("color=negative")

        dlg.open()


def _abrir_dialog_crear_segmento(servicio_id, refreshable, page_client):
    with ui.dialog() as dlg, ui.card().style("min-width:520px;max-width:640px;"):
        ui.label("Crear segmentación").classes("text-lg font-bold text-slate-800 mb-2")

        codigo_in = ui.input(
            "Código único dentro del servicio (ej. 'solo_lava')"
        ).classes("w-full")
        nombre_in = ui.input("Nombre visible").classes("w-full")
        desc_in = ui.input("Descripción (opcional)").classes("w-full")
        tipo_in = ui.select(
            ["fijo", "por_kg", "por_duracion"],
            value="fijo",
            label="Tipo de cálculo",
        ).classes("w-full")
        precio_in = (
            ui.input("Precio fijo ($)", value="0")
            .props("type=number")
            .classes("w-full")
        )
        tarifa_in = (
            ui.input("Tarifa por kg ($)", value="0")
            .props("type=number step=0.01")
            .classes("w-full")
        )
        duracion_in = (
            ui.input("Duración (min)", value="60")
            .props("type=number")
            .classes("w-full")
        )

        pwd_in = (
            ui.input("Contraseña de bypass", password=True)
            .props("type=password")
            .classes("w-full mt-3")
        )

        async def _guardar():
            if pwd_in.value != os.getenv("BYPASS_PASSWORD", "admin123"):
                with page_client:
                    ui.notify(
                        "Contraseña incorrecta.",
                        type="negative",
                        position="top",
                    )
                return
            codigo = codigo_in.value.strip().lower().replace(" ", "_")
            if not codigo or not nombre_in.value.strip():
                with page_client:
                    ui.notify(
                        "Código y nombre son obligatorios.",
                        type="negative",
                        position="top",
                    )
                return
            try:
                new_id = await database_web.crear_segmentacion_async(
                    servicio_id,
                    codigo,
                    nombre_in.value.strip(),
                    desc_in.value.strip(),
                    tipo_in.value,
                    int(precio_in.value or 0),
                    float(tarifa_in.value or 0),
                    int(duracion_in.value or 0),
                )
                if new_id is None:
                    with page_client:
                        ui.notify(
                            f"Ya existe una segmentación con código '{codigo}' "
                            "en este servicio.",
                            type="negative",
                            position="top",
                        )
                    return
                with page_client:
                    ui.notify(
                        f"Segmentación '{nombre_in.value}' creada.",
                        type="positive",
                        position="top",
                    )
                dlg.close()
                refreshable.refresh()
            except Exception as e:
                with page_client:
                    ui.notify(f"Error: {e}", type="negative", position="top")

        with ui.row().classes("w-full justify-end mt-3 gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Crear", on_click=_guardar).props("color=primary")

    dlg.open()


def _abrir_editor_segmento(id_seg, refreshable, page_client):
    seg = None
    todas = database_web._listar_segmentaciones(solo_activos=False)
    for s in todas:
        if s["id"] == id_seg:
            seg = s
            break
    if not seg:
        return

    with ui.dialog() as dlg, ui.card().style("min-width:520px;max-width:640px;"):
        ui.label(f"Editar segmentación: {seg['codigo']}").classes(
            "text-lg font-bold text-slate-800 mb-2"
        )

        nombre_in = ui.input("Nombre", value=seg["nombre"]).classes("w-full")
        desc_in = ui.input("Descripción", value=seg["descripcion"] or "").classes(
            "w-full"
        )
        tipo_in = ui.select(
            ["fijo", "por_kg", "por_duracion"],
            value=seg["tipo_calculo"],
            label="Tipo de cálculo",
        ).classes("w-full")
        precio_in = (
            ui.input(
                "Precio fijo ($)",
                value=str(seg["precio_fijo"] or 0),
            )
            .props("type=number")
            .classes("w-full")
        )
        tarifa_in = (
            ui.input(
                "Tarifa por kg ($)",
                value=str(seg["tarifa_por_kg"] or 0),
            )
            .props("type=number step=0.01")
            .classes("w-full")
        )
        duracion_in = (
            ui.input(
                "Duración (min)",
                value=str(seg["duracion_min"] or 0),
            )
            .props("type=number")
            .classes("w-full")
        )
        activo_in = ui.checkbox("Activo", value=bool(seg["activo"])).classes("w-full")

        calc_preview = ui.html("")

        def _actualizar_preview():
            try:
                peso = 3.0
                tarifa = float(tarifa_in.value or 0)
                precio = int(precio_in.value or 0)
                tipo = tipo_in.value
                if tipo == "fijo":
                    txt = f'<div style="background:#dcfce7;padding:8px;border-radius:6px;margin-top:6px;color:#166534;">Precio: <strong>${precio}</strong></div>'
                elif tipo == "por_kg":
                    txt = f'<div style="background:#dcfce7;padding:8px;border-radius:6px;margin-top:6px;color:#166534;">{peso} kg → <strong>${int(round(tarifa * peso))}</strong></div>'
                else:
                    txt = f'<div style="background:#dcfce7;padding:8px;border-radius:6px;margin-top:6px;color:#166534;">{duracion_in.value} min → <strong>${precio}</strong></div>'
                calc_preview.set_content(txt)
            except (ValueError, TypeError):
                calc_preview.set_content("")

        for inp in (tipo_in, precio_in, tarifa_in, duracion_in):
            inp.on("update:model-value", lambda e: _actualizar_preview())
        _actualizar_preview()

        async def _guardar():
            pwd = pwd_in.value
            if pwd != os.getenv("BYPASS_PASSWORD", "admin123"):
                with page_client:
                    ui.notify("Contraseña incorrecta.", type="negative", position="top")
                return
            try:
                await database_web.actualizar_segmentacion_async(
                    id_seg,
                    nombre_in.value.strip() or seg["nombre"],
                    desc_in.value.strip(),
                    tipo_in.value,
                    int(precio_in.value or 0),
                    float(tarifa_in.value or 0),
                    int(duracion_in.value or 0),
                    activo_in.value,
                )
                with page_client:
                    ui.notify(
                        f"Segmentación '{nombre_in.value}' actualizada.",
                        type="positive",
                        position="top",
                    )
                dlg.close()
                refreshable.refresh()
            except Exception as e:
                with page_client:
                    ui.notify(f"Error guardando: {e}", type="negative", position="top")

        ui.separator().classes("my-3")
        pwd_in = (
            ui.input("Contraseña de bypass", password=True)
            .props("type=password")
            .classes("w-full")
        )

        with ui.row().classes("w-full justify-end mt-3 gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Guardar cambios", on_click=_guardar).props("color=primary")

    dlg.open()


# ── Tab Calculadora (preview para todos los admin) ───────────────────────────


async def _render_tab_calculadora():
    servicios = await database_web.listar_servicios_async(solo_activos=True)
    if not servicios:
        ui.html('<div class="empty-state">Sin servicios.</div>')
        return

    ui.html(
        '<p style="color:#475569;margin-bottom:12px;">Simula el precio de un '
        "servicio o segmentación con un peso dado. Útil para responderle al "
        "cliente en mostrador.</p>"
    )

    # Opciones del selector de servicio. Usamos labels simples (strings)
    # y un dict paralelo para mapear label -> id. Esto evita el [object Object]
    # que muestra nicegui al recibir un dict como opción.
    label_to_id_serv = {}
    label_to_id_seg = {}
    etiquetas_serv = []
    for s in servicios:
        label = f"{s['codigo']} – {s['nombre']}"
        label_to_id_serv[label] = s["id"]
        etiquetas_serv.append(label)

    servicio_select = ui.select(
        etiquetas_serv,
        label="Servicio",
        value=etiquetas_serv[0] if etiquetas_serv else None,
    ).classes("w-full max-w-md")

    peso_in = (
        ui.input("Peso (kg)", value="3.0")
        .props("type=number step=0.01")
        .classes("w-full max-w-md")
    )

    etiquetas_seg = ["(usar servicio directo)"]
    seg_select = ui.select(
        etiquetas_seg,
        label="Segmentación (opcional)",
        value=etiquetas_seg[0],
    ).classes("w-full max-w-md")

    precio_out = ui.html("").classes("w-full max-w-md")

    async def _actualizar_opciones_seg():
        nonlocal label_to_id_seg, etiquetas_seg
        label_serv = servicio_select.value
        if not label_serv:
            seg_select.options = []
            seg_select.value = None
            seg_select.update()
            return
        id_serv = label_to_id_serv.get(label_serv)
        if id_serv is None:
            return
        segs = await database_web.listar_segmentaciones_async(
            servicio_id=id_serv, solo_activos=True
        )
        label_to_id_seg = {"(usar servicio directo)": None}
        opts = ["(usar servicio directo)"]
        for seg in segs:
            label = f"{seg['nombre']} (${seg['precio_fijo'] or seg['tarifa_por_kg']})"
            label_to_id_seg[label] = seg["id"]
            opts.append(label)
        seg_select.options = opts
        seg_select.value = opts[0]
        seg_select.update()

    async def _calcular():
        try:
            label_serv = servicio_select.value
            id_serv = label_to_id_serv.get(label_serv) if label_serv else None
            if id_serv is None:
                return
            servicios_all = await database_web.listar_servicios_async(solo_activos=True)
            servicio = next(s for s in servicios_all if s["id"] == id_serv)
            try:
                peso = float(peso_in.value or 0)
            except (TypeError, ValueError):
                peso = 0.0
            label_seg = seg_select.value
            id_seg = label_to_id_seg.get(label_seg) if label_seg else None
            if id_seg:
                from database_web import _obtener_segmentacion_por_id

                fila = _obtener_segmentacion_por_id(id_seg)
                tipo = fila["tipo_calculo"]
                if tipo == "fijo":
                    precio = fila["precio_fijo"]
                    desglose = f"Tarifa fija de ${precio}"
                elif tipo == "por_kg":
                    precio = int(round(fila["tarifa_por_kg"] * peso))
                    desglose = f"${fila['tarifa_por_kg']}/kg × {peso} kg = ${precio}"
                else:
                    precio = fila["precio_fijo"]
                    desglose = f"${precio} por {fila['duracion_min']} min"
                titulo = fila["nombre"]
            else:
                tipo = servicio["tipo_calculo"]
                if tipo == "fijo":
                    precio = servicio["precio_fijo"]
                    desglose = f"Tarifa fija de ${precio}"
                elif tipo == "por_kg":
                    precio = int(round(servicio["tarifa_por_kg"] * peso))
                    desglose = (
                        f"${servicio['tarifa_por_kg']}/kg × {peso} kg = ${precio}"
                    )
                else:
                    precio = servicio["precio_fijo"]
                    desglose = f"${precio} por {servicio['duracion_min']} min"
                titulo = servicio["nombre"]
            precio_out.set_content(
                f'<div style="background:#dbeafe;padding:14px;border-radius:8px;'
                f'margin-top:10px;border:1px solid #93c5fd;">'
                f'<div style="font-size:0.78rem;color:#1e40af;font-weight:700;">{titulo}</div>'
                f'<div style="font-size:2rem;font-weight:800;color:#1e3a8a;margin:4px 0;">${precio}</div>'
                f'<div style="font-size:0.85rem;color:#475569;">{desglose}</div>'
                f"</div>"
            )
        except Exception as e:
            precio_out.set_content(
                f'<div style="color:#ef4444;margin-top:10px;">Error: {e}</div>'
            )

    servicio_select.on(
        "update:model-value",
        lambda e: asyncio.create_task(_actualizar_opciones_seg()),
    )
    peso_in.on("update:model-value", lambda e: asyncio.create_task(_calcular()))
    seg_select.on("update:model-value", lambda e: asyncio.create_task(_calcular()))

    ui.button("Calcular", on_click=lambda: asyncio.create_task(_calcular())).props(
        "color=primary"
    ).classes("mt-3")

    # Carga inicial
    await _actualizar_opciones_seg()
    await _calcular()


# ── Tab Maquinas ──────────────────────────────────────────────────────────────


async def _render_tab_maquinas(page_client, client_id):
    """CRUD de máquinas (hardware). Crear/editar/activar/desactivar/eliminar."""

    @ui.refreshable
    async def lista_maquinas():
        maquinas = await database_web.listar_maquinas_async(solo_activas=False)
        if not maquinas:
            ui.html('<div class="empty-state">No hay máquinas configuradas.</div>')
            return
        for m in maquinas:
            _render_maquina_card(m, lista_maquinas, page_client)

    with ui.row().classes("w-full justify-end mb-3"):
        ui.button(
            "+ Crear máquina",
            on_click=lambda: _abrir_dialog_crear_maquina(lista_maquinas, page_client),
        ).props("color=primary")

    await lista_maquinas()


def _render_maquina_card(m, refreshable, page_client):
    tipo_label = {
        "mixto": "Lava + Seca",
        "lavado": "Solo lavado",
        "secado": "Solo secado",
        "doblado": "Doblado",
    }.get(m["tipo"], m["tipo"])
    modo_label = "Pulso (0.5s)" if m["modo"] == "pulso" else "Sostenido (HIGH continuo)"
    activo_color = "#16a34a" if m["activa"] else "#94a3b8"
    activo_label = "Activa" if m["activa"] else "Inactiva"

    with (
        ui.element("div")
        .classes("orden-card")
        .style(f"border-left:4px solid {activo_color};")
    ):
        with ui.element("div").style("flex:1;min-width:0;"):
            ui.html(
                f'<div class="orden-numero">{m["codigo"]}</div>'
                f'<div style="font-size:1.1rem;font-weight:800;color:#1e293b;">{m["nombre"]}</div>'
                f'<div style="font-size:0.85rem;color:#64748b;">'
                f"Tipo: <strong>{tipo_label}</strong> · "
                f"GPIO: <code>{m['gpio']}</code> · "
                f"Capacidad: <strong>{m['capacidad_kg']} kg</strong> · "
                f"Modo: <strong>{modo_label}</strong>"
                f"</div>"
                f'<div style="font-size:0.78rem;color:#64748b;margin-top:2px;">'
                f"Duración máx (sostenido): <strong>{m['duracion_max_min']} min</strong> · "
                f"Orden: <strong>{m['orden']}</strong> · "
                f'<span style="color:{activo_color};font-weight:700;">{activo_label}</span>'
                f"</div>"
            )
        with ui.element("div").style(
            "flex-shrink:0;display:flex;flex-direction:column;gap:8px;align-items:flex-end;"
        ):
            ui.label("✎ Editar").classes("btn-maquina btn-iniciar").on(
                "click",
                lambda e, mid=m["id"]: _abrir_editor_maquina(
                    mid, refreshable, page_client
                ),
            )
            toggle_label = "⏸ Desactivar" if m["activa"] else "▶ Activar"
            toggle_class = (
                "btn-maquina btn-pausar" if m["activa"] else "btn-maquina btn-iniciar"
            )
            ui.label(toggle_label).classes(toggle_class).on(
                "click",
                lambda e, mid=m["id"], act=m["activa"], mq=m: asyncio.create_task(
                    _toggle_maquina(mq, not act, refreshable, page_client)
                ),
            )
            ui.label("🗑").classes("btn-maquina btn-pausar").on(
                "click",
                lambda e, mid=m["id"], nom=m["nombre"]: asyncio.create_task(
                    _eliminar_maquina_handler(mid, nom, refreshable, page_client)
                ),
            )


async def _toggle_maquina(m, nuevo_activo, refreshable, page_client):
    ok = await database_web.actualizar_maquina_async(
        m["id"],
        m["nombre"],
        m["tipo"],
        m["capacidad_kg"],
        m["gpio"],
        m["modo"],
        m["duracion_max_min"],
        m["orden"],
        nuevo_activo,
    )
    if ok:
        with page_client:
            ui.notify(
                f"Máquina {'activada' if nuevo_activo else 'desactivada'}.",
                type="positive",
                position="top",
            )
    else:
        with page_client:
            ui.notify(
                "No se pudo actualizar (¿GPIO duplicado?).",
                type="negative",
                position="top",
            )
    refreshable.refresh()


async def _eliminar_maquina_handler(id_maquina, nombre, refreshable, page_client):
    await asyncio.sleep(0)
    with page_client:
        with ui.dialog() as dlg, ui.card().style("min-width:380px;"):
            ui.label("Eliminar máquina").classes(
                "text-lg font-bold text-slate-800 mb-2"
            )
            ui.html(
                f'<p style="color:#475569;margin-bottom:8px;">Vas a eliminar '
                f"<strong>{nombre}</strong>. Esta acción es <strong>irreversible</strong>."
                "</p>"
                '<p style="color:#94a3b8;font-size:0.85rem;">Solo se puede eliminar '
                "si ningún cliente tiene órdenes asignadas a esta máquina. Si "
                "existen, desactívala en su lugar.</p>"
            )
            pwd_in = (
                ui.input("Contraseña de bypass", password=True)
                .props("type=password")
                .classes("w-full")
            )

            async def _confirmar():
                if pwd_in.value != os.getenv("BYPASS_PASSWORD", "admin123"):
                    with page_client:
                        ui.notify(
                            "Contraseña incorrecta.",
                            type="negative",
                            position="top",
                        )
                    return
                ok = await database_web.eliminar_maquina_hard_async(id_maquina)
                if ok:
                    with page_client:
                        ui.notify(
                            f"Máquina '{nombre}' eliminada.",
                            type="positive",
                            position="top",
                        )
                    dlg.close()
                    refreshable.refresh()
                else:
                    with page_client:
                        ui.notify(
                            "No se puede eliminar: hay órdenes con esta máquina. "
                            "Desactívala en su lugar.",
                            type="negative",
                            position="top",
                            timeout=8000,
                        )
                    dlg.close()

            with ui.row().classes("w-full justify-end mt-3 gap-2"):
                ui.button("Cancelar", on_click=dlg.close).props("flat")
                ui.button("Eliminar", on_click=_confirmar).props("color=negative")

        dlg.open()


def _abrir_editor_maquina(id_maquina, refreshable, page_client):
    m = None
    for x in database_web._listar_maquinas(solo_activas=False):
        if x["id"] == id_maquina:
            m = x
            break
    if not m:
        return

    with ui.dialog() as dlg, ui.card().style("min-width:520px;max-width:640px;"):
        ui.label(f"Editar máquina: {m['codigo']}").classes(
            "text-lg font-bold text-slate-800 mb-2"
        )

        nombre_in = ui.input("Nombre", value=m["nombre"]).classes("w-full")
        tipo_in = ui.select(
            ["lavado", "secado", "mixto", "doblado"],
            value=m["tipo"],
            label="Tipo de máquina",
        ).classes("w-full")
        gpio_in = (
            ui.input("GPIO (pin BCM)", value=str(m["gpio"]), validation=r"^\d+$")
            .props("type=number")
            .classes("w-full")
        )
        capacidad_in = (
            ui.input("Capacidad (kg)", value=str(m["capacidad_kg"]))
            .props("type=number")
            .classes("w-full")
        )
        modo_in = ui.select(
            ["pulso", "sostenido"],
            value=m["modo"],
            label="Modo de activación",
        ).classes("w-full")
        duracion_in = (
            ui.input(
                "Duración máx. sostenido (min)",
                value=str(m["duracion_max_min"]),
            )
            .props("type=number")
            .classes("w-full")
        )
        orden_in = (
            ui.input("Orden en pantalla", value=str(m["orden"]))
            .props("type=number")
            .classes("w-full")
        )
        activo_in = ui.checkbox("Activa", value=bool(m["activa"])).classes("w-full")

        pwd_in = (
            ui.input("Contraseña de bypass", password=True)
            .props("type=password")
            .classes("w-full mt-3")
        )

        async def _guardar():
            if pwd_in.value != os.getenv("BYPASS_PASSWORD", "admin123"):
                with page_client:
                    ui.notify(
                        "Contraseña incorrecta.",
                        type="negative",
                        position="top",
                    )
                return
            try:
                gpio = int(gpio_in.value)
            except (TypeError, ValueError):
                with page_client:
                    ui.notify(
                        "GPIO debe ser un número entero.",
                        type="negative",
                        position="top",
                    )
                return
            # Validar que el GPIO no esté duplicado
            ya_usado = await database_web.existe_gpio_async(gpio, id_excluir=id_maquina)
            if ya_usado:
                with page_client:
                    ui.notify(
                        f"El GPIO {gpio} ya está usado por otra máquina.",
                        type="negative",
                        position="top",
                    )
                return
            ok = await database_web.actualizar_maquina_async(
                id_maquina,
                nombre_in.value.strip() or m["nombre"],
                tipo_in.value,
                int(capacidad_in.value or 0),
                gpio,
                modo_in.value,
                int(duracion_in.value or 25),
                int(orden_in.value or 0),
                activo_in.value,
            )
            if ok:
                with page_client:
                    ui.notify(
                        f"Máquina '{nombre_in.value}' actualizada.",
                        type="positive",
                        position="top",
                    )
                dlg.close()
                refreshable.refresh()
            else:
                with page_client:
                    ui.notify(
                        "No se pudo actualizar (¿GPIO duplicado?).",
                        type="negative",
                        position="top",
                    )

        with ui.row().classes("w-full justify-end mt-3 gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Guardar cambios", on_click=_guardar).props("color=primary")

    dlg.open()


def _abrir_dialog_crear_maquina(refreshable, page_client):
    with ui.dialog() as dlg, ui.card().style("min-width:520px;max-width:640px;"):
        ui.label("Crear nueva máquina").classes("text-lg font-bold text-slate-800 mb-2")

        codigo_in = ui.input("Código único (sin espacios, ej. 'secadora_2')").classes(
            "w-full"
        )
        nombre_in = ui.input("Nombre visible").classes("w-full")
        tipo_in = ui.select(
            ["lavado", "secado", "mixto", "doblado"],
            value="mixto",
            label="Tipo",
        ).classes("w-full")
        gpio_in = (
            ui.input("GPIO (pin BCM)", value="17")
            .props("type=number")
            .classes("w-full")
        )
        capacidad_in = (
            ui.input("Capacidad (kg)", value="5").props("type=number").classes("w-full")
        )
        modo_in = ui.select(
            ["pulso", "sostenido"],
            value="pulso",
            label="Modo",
        ).classes("w-full")
        duracion_in = (
            ui.input("Duración máx. sostenido (min)", value="25")
            .props("type=number")
            .classes("w-full")
        )

        pwd_in = (
            ui.input("Contraseña de bypass", password=True)
            .props("type=password")
            .classes("w-full mt-3")
        )

        async def _guardar():
            if pwd_in.value != os.getenv("BYPASS_PASSWORD", "admin123"):
                with page_client:
                    ui.notify(
                        "Contraseña incorrecta.",
                        type="negative",
                        position="top",
                    )
                return
            codigo = codigo_in.value.strip().lower().replace(" ", "_")
            if not codigo or not nombre_in.value.strip():
                with page_client:
                    ui.notify(
                        "Código y nombre son obligatorios.",
                        type="negative",
                        position="top",
                    )
                return
            try:
                gpio = int(gpio_in.value)
            except (TypeError, ValueError):
                with page_client:
                    ui.notify(
                        "GPIO debe ser un número entero.",
                        type="negative",
                        position="top",
                    )
                return
            if await database_web.existe_gpio_async(gpio):
                with page_client:
                    ui.notify(
                        f"El GPIO {gpio} ya está usado por otra máquina.",
                        type="negative",
                        position="top",
                    )
                return
            new_id = await database_web.crear_maquina_async(
                codigo,
                nombre_in.value.strip(),
                tipo_in.value,
                int(capacidad_in.value or 0),
                gpio,
                modo_in.value,
                int(duracion_in.value or 25),
            )
            if new_id is None:
                with page_client:
                    ui.notify(
                        f"Ya existe una máquina con código '{codigo}'.",
                        type="negative",
                        position="top",
                    )
                return
            with page_client:
                ui.notify(
                    f"Máquina '{nombre_in.value}' creada. "
                    "Reinicia el kiosko para que tome efecto el GPIO.",
                    type="positive",
                    position="top",
                    timeout=8000,
                )
            dlg.close()
            refreshable.refresh()

        with ui.row().classes("w-full justify-end mt-3 gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Crear", on_click=_guardar).props("color=primary")

    dlg.open()


# ── Tab Respaldo (default snapshot) ─────────────────────────────────────────


async def _render_tab_backup(page_client, client_id):
    """Snapshot de fábrica para revertir servicios, segmentaciones y máquinas."""

    @ui.refreshable
    async def vista_backups():
        backups = await database_web.listar_backups_async()
        if not backups:
            ui.html('<div class="empty-state">No hay respaldo configurado.</div>')
            return

        ui.html(
            '<p style="color:#475569;margin-bottom:14px;">'
            "Cada vez que inicias la app por primera vez, se guarda un snapshot "
            "del catálogo de fábrica (servicios, segmentaciones, máquinas). "
            "Si haces muchos cambios y quieres volver al estado inicial, "
            "usa el botón <strong>Restaurar valores por defecto</strong>."
            "</p>"
            '<p style="color:#94a3b8;font-size:0.85rem;margin-bottom:14px;">'
            "<strong>Importante:</strong> la restauración borra los servicios, "
            "segmentaciones y máquinas actuales y los reemplaza con el snapshot. "
            "Las órdenes históricas NO se tocan."
            "</p>"
        )

        with (
            ui.element("div")
            .classes("orden-card")
            .style("flex-direction:column;gap:8px;")
        ):
            for b in backups:
                bk = await database_web.obtener_backup_async(b["tabla"])
                n = len(bk["datos"]) if bk else 0
                ui.html(
                    f'<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;">'
                    f"<div>"
                    f'<div style="font-weight:800;color:#1e293b;">{b["tabla"]}</div>'
                    f'<div style="font-size:0.78rem;color:#64748b;">'
                    f"Creado: {b['created_at']} · Nota: {b['nota']}"
                    f"</div>"
                    f"</div>"
                    f'<div style="font-size:1.4rem;font-weight:800;color:#3b82f6;">'
                    f"{n} filas"
                    f"</div>"
                    f"</div>"
                )

        with ui.row().classes("w-full gap-2 mt-3 justify-end"):
            ui.button(
                "💾 Crear respaldo ahora",
                on_click=lambda: _confirmar_crear_respaldo(vista_backups, page_client),
            ).props("color=primary")

            ui.button(
                "↻ Restaurar valores por defecto",
                on_click=lambda: _abrir_dialog_restaurar(vista_backups, page_client),
            ).props("color=negative")

    await vista_backups()


def _confirmar_crear_respaldo(refreshable, page_client):
    """Crea un snapshot del estado actual como el nuevo 'por defecto'."""
    with ui.dialog() as dlg, ui.card().style("min-width:420px;"):
        ui.label("Crear respaldo ahora").classes(
            "text-lg font-bold text-slate-800 mb-2"
        )
        ui.html(
            '<p style="color:#475569;margin-bottom:8px;">'
            "Esto sobrescribe el snapshot de fábrica con el estado actual "
            "de servicios, segmentaciones y máquinas."
            "</p>"
            '<p style="color:#94a3b8;font-size:0.85rem;margin-bottom:12px;">'
            "<strong>¿Por qué?</strong> Si ya configuraste el catálogo a tu "
            "gusto y quieres que ese sea el nuevo 'punto de retorno' para "
            "futuras restauraciones."
            "</p>"
        )
        nota_in = ui.input(
            "Nota (opcional)",
            value="Respaldo manual",
            placeholder="ej. Después de configurar tarifas de julio",
        ).classes("w-full")

        async def _guardar():
            n = await database_web.crear_backup_completo_async(nota_in.value.strip())
            total = sum(v for v in n.values() if isinstance(v, int))
            with page_client:
                ui.notify(
                    f"Respaldo creado. {total} filas guardadas en 3 tablas.",
                    type="positive",
                    position="top",
                )
            dlg.close()
            refreshable.refresh()

        with ui.row().classes("w-full justify-end mt-3 gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Crear respaldo", on_click=_guardar).props("color=primary")

    dlg.open()


def _abrir_dialog_restaurar(refreshable, page_client):
    """Diálogo de restauración con BYPASS_PASSWORD."""
    with ui.dialog() as dlg, ui.card().style("min-width:440px;"):
        ui.label("Restaurar valores por defecto").classes(
            "text-lg font-bold text-slate-800 mb-2"
        )
        ui.html(
            '<p style="color:#475569;margin-bottom:8px;">'
            "Vas a <strong>borrar</strong> los servicios, segmentaciones y "
            "máquinas actuales y reemplazarlos con el snapshot de fábrica."
            "</p>"
            '<p style="background:#fef3c7;color:#92400e;padding:10px;border-radius:6px;'
            'font-size:0.85rem;margin-bottom:8px;">'
            "Las órdenes históricas <strong>NO se borran</strong>, pero las "
            "máquinas o servicios que ya no existan en el snapshot quedarán "
            "huérfanas (sin asignar). Úsalo con cuidado."
            "</p>"
        )
        pwd_in = (
            ui.input("Contraseña de bypass").props("type=password").classes("w-full")
        )

        async def _confirmar():
            if pwd_in.value != os.getenv("BYPASS_PASSWORD", "admin123"):
                with page_client:
                    ui.notify(
                        "Contraseña incorrecta.",
                        type="negative",
                        position="top",
                    )
                return
            await asyncio.sleep(0)
            with page_client:
                resultado = await database_web.restaurar_backup_completo_async()
                total_ok = sum(
                    v["filas"]
                    for v in resultado.values()
                    if isinstance(v, dict) and v.get("ok")
                )
                ui.notify(
                    f"Restauración completa: {total_ok} filas en 3 tablas.",
                    type="positive",
                    position="top",
                )
                dlg.close()
                refreshable.refresh()

        with ui.row().classes("w-full justify-end mt-3 gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Restaurar", on_click=_confirmar).props("color=negative")

    dlg.open()


# ── Tab Métricas (con Highcharts) ─────────────────────────────────────────────


async def _render_tab_metricas(page_client, client_id):
    """Reportes analíticos con gráficos Highcharts."""

    # Estado del rango de fechas (en este closure)
    estado = {"fecha_desde": "", "fecha_hasta": ""}

    # Filtro de rango en la parte superior
    with ui.row().classes("w-full items-center gap-2 mb-3"):
        ui.label("Rango:").classes("font-bold text-slate-700")
        ui.select(
            {
                "": "Todo el historial",
                "7d": "Últimos 7 días",
                "30d": "Último mes",
                "90d": "Últimos 3 meses",
                "1y": "Último año",
            },
            value="",
            on_change=lambda e: _aplicar_rango(e.value, estado),
        ).classes("min-w-40")
        ui.label().bind_text_from(
            estado, "fecha_desde", backward=lambda v: f"Desde: {v or '—'}"
        )
        ui.label().bind_text_from(
            estado, "fecha_hasta", backward=lambda v: f"Hasta: {v or '—'}"
        )

    # Contenedor de KPIs
    kpi_container = ui.column().classes("w-full")

    # Contenedor de gráficos
    charts_container = ui.column().classes("w-full")

    async def _aplicar_rango(rango_key: str, est: dict):
        if rango_key == "":
            est["fecha_desde"] = ""
            est["fecha_hasta"] = ""
        else:
            hoy = datetime.now().date()
            if rango_key == "7d":
                desde = hoy - timedelta(days=7)
            elif rango_key == "30d":
                desde = hoy - timedelta(days=30)
            elif rango_key == "90d":
                desde = hoy - timedelta(days=90)
            elif rango_key == "1y":
                desde = hoy - timedelta(days=365)
            else:
                desde = hoy
            est["fecha_desde"] = desde.isoformat()
            est["fecha_hasta"] = hoy.isoformat()
        await _refrescar()

    async def _refrescar():
        kpi_container.clear()
        charts_container.clear()
        with kpi_container:
            await _render_kpis(estado["fecha_desde"], estado["fecha_hasta"])
        with charts_container:
            await _render_charts(estado["fecha_desde"], estado["fecha_hasta"])

    await _refrescar()


async def _render_kpis(fecha_desde: str, fecha_hasta: str):
    resumen = await database_web.reporte_resumen_async(fecha_desde, fecha_hasta)
    with ui.element("div").classes("dash-grid"):
        with (
            ui.element("div")
            .classes("dash-card")
            .style("flex-direction:column;align-items:center;")
        ):
            ui.html(
                f'<div style="font-size:0.78rem;color:#64748b;font-weight:600;">'
                "Órdenes"
                "</div>"
                f'<div style="font-size:2rem;font-weight:800;color:#1e293b;">'
                f"{resumen['n_orden']}"
                "</div>"
            )
        with (
            ui.element("div")
            .classes("dash-card")
            .style("flex-direction:column;align-items:center;")
        ):
            ui.html(
                f'<div style="font-size:0.78rem;color:#64748b;font-weight:600;">'
                "Recaudado"
                "</div>"
                f'<div style="font-size:2rem;font-weight:800;color:#16a34a;">'
                f"${resumen['recaudado']:,.0f}"
                "</div>"
            )
        with (
            ui.element("div")
            .classes("dash-card")
            .style("flex-direction:column;align-items:center;")
        ):
            ui.html(
                f'<div style="font-size:0.78rem;color:#64748b;font-weight:600;">'
                "Kilos lavados"
                "</div>"
                f'<div style="font-size:2rem;font-weight:800;color:#3b82f6;">'
                f"{resumen['kg_total']:.1f}"
                "</div>"
            )
        with (
            ui.element("div")
            .classes("dash-card")
            .style("flex-direction:column;align-items:center;")
        ):
            ui.html(
                f'<div style="font-size:0.78rem;color:#64748b;font-weight:600;">'
                "Promedio kg/orden"
                "</div>"
                f'<div style="font-size:2rem;font-weight:800;color:#7c3aed;">'
                f"{resumen['kg_prom']:.1f}"
                "</div>"
            )


async def _render_charts(fecha_desde: str, fecha_hasta: str):
    """Renderiza los 5 gráficos con Highcharts."""
    # 1. Uso por máquina (pie chart)
    uso = await database_web.reporte_uso_por_maquina_async(fecha_desde, fecha_hasta)
    with ui.element("div").classes("orden-card").style("flex-direction:column;"):
        ui.html(
            '<div class="orden-numero" style="margin-bottom:6px;">'
            "Uso por máquina (# servicios)"
            "</div>"
        )
        if uso:
            data = [
                {
                    "name": u["id_equipo"],
                    "y": u["n_servicios"],
                }
                for u in uso
            ]
            highchart(
                {
                    "chart": {"type": "pie", "height": 320},
                    "title": {"text": None},
                    "plotOptions": {
                        "pie": {
                            "allowPointSelect": True,
                            "cursor": "pointer",
                            "dataLabels": {
                                "enabled": True,
                                "format": "<b>{point.name}</b>: {point.y}",
                            },
                        }
                    },
                    "series": [
                        {
                            "name": "Servicios",
                            "colorByPoint": True,
                            "data": data,
                        }
                    ],
                    "credits": {"enabled": False},
                }
            )
        else:
            ui.html(
                '<div style="color:#94a3b8;font-size:0.85rem;">'
                "Sin datos en el rango seleccionado."
                "</div>"
            )

    # 2. Horas pico (column chart)
    horas = await database_web.reporte_horas_pico_async(fecha_desde, fecha_hasta)
    with ui.element("div").classes("orden-card").style("flex-direction:column;"):
        ui.html(
            '<div class="orden-numero" style="margin-bottom:6px;">'
            "Horas pico del día"
            "</div>"
        )
        highchart(
            {
                "chart": {"type": "column", "height": 320},
                "title": {"text": None},
                "xAxis": {
                    "categories": [f"{h['hora']:02d}:00" for h in horas],
                    "title": {"text": "Hora del día"},
                },
                "yAxis": {
                    "title": {"text": "# servicios"},
                    "min": 0,
                    "allowDecimals": False,
                },
                "plotOptions": {"column": {"color": "#3b82f6", "borderRadius": 4}},
                "series": [
                    {
                        "name": "Servicios",
                        "data": [h["n"] for h in horas],
                    }
                ],
                "legend": {"enabled": False},
                "credits": {"enabled": False},
            }
        )

    # 3. Días pico (column chart)
    dias = await database_web.reporte_dias_pico_async(fecha_desde, fecha_hasta)
    with ui.element("div").classes("orden-card").style("flex-direction:column;"):
        ui.html(
            '<div class="orden-numero" style="margin-bottom:6px;">'
            "Días pico de la semana"
            "</div>"
        )
        highchart(
            {
                "chart": {"type": "column", "height": 320},
                "title": {"text": None},
                "xAxis": {
                    "categories": [d["nombre"] for d in dias],
                    "title": {"text": "Día de la semana"},
                },
                "yAxis": {
                    "title": {"text": "# servicios"},
                    "min": 0,
                    "allowDecimals": False,
                },
                "plotOptions": {"column": {"color": "#7c3aed", "borderRadius": 4}},
                "series": [
                    {
                        "name": "Servicios",
                        "data": [d["n"] for d in dias],
                    }
                ],
                "legend": {"enabled": False},
                "credits": {"enabled": False},
            }
        )

    # 4. Consumo promedio por servicio (bar chart)
    consumo = await database_web.reporte_consumo_promedio_async(
        fecha_desde, fecha_hasta
    )
    with ui.element("div").classes("orden-card").style("flex-direction:column;"):
        ui.html(
            '<div class="orden-numero" style="margin-bottom:6px;">'
            "Consumo promedio por servicio"
            "</div>"
        )
        if consumo:
            categorias = [c["tipo_servicio"] for c in consumo]
            highchart(
                {
                    "chart": {"type": "bar", "height": 320},
                    "title": {"text": None},
                    "xAxis": {
                        "categories": categorias,
                        "title": {"text": None},
                    },
                    "yAxis": [
                        {
                            "title": {"text": "Kg promedio"},
                            "min": 0,
                        },
                        {
                            "title": {"text": "Monto promedio ($)"},
                            "opposite": True,
                            "min": 0,
                        },
                    ],
                    "plotOptions": {"bar": {"grouping": False}},
                    "series": [
                        {
                            "name": "Kg promedio",
                            "data": [c["kg_prom"] for c in consumo],
                            "color": "#3b82f6",
                        },
                        {
                            "name": "Monto promedio ($)",
                            "data": [c["monto_prom"] for c in consumo],
                            "yAxis": 1,
                            "color": "#16a34a",
                        },
                    ],
                    "credits": {"enabled": False},
                }
            )
        else:
            ui.html(
                '<div style="color:#94a3b8;font-size:0.85rem;">'
                "Sin datos en el rango seleccionado."
                "</div>"
            )

    # 5. Tasa de uso: efectivo vs tarjeta (stacked bar por mes)
    tasa = await database_web.reporte_tasa_pago_async(fecha_desde, fecha_hasta)
    with ui.element("div").classes("orden-card").style("flex-direction:column;"):
        ui.html(
            '<div class="orden-numero" style="margin-bottom:6px;">'
            "Tasa de uso: Efectivo vs Tarjeta (por mes)"
            "</div>"
        )
        if tasa:
            categorias = [t["mes"] for t in tasa]
            metodos = [
                "Efectivo",
                "Tarjeta (Point)",
                "Tarjeta (Terminal)",
                "Efectivo (mostrador)",
            ]
            colores = {
                "Efectivo": "#16a34a",
                "Tarjeta (Point)": "#3b82f6",
                "Tarjeta (Terminal)": "#f59e0b",
                "Efectivo (mostrador)": "#a78bfa",
            }
            series = [
                {
                    "name": m,
                    "data": [t.get(m, 0) for t in tasa],
                    "stack": "total",
                    "color": colores[m],
                }
                for m in metodos
            ]
            highchart(
                {
                    "chart": {"type": "column", "height": 360},
                    "title": {"text": None},
                    "xAxis": {"categories": categorias, "title": {"text": "Mes"}},
                    "yAxis": {
                        "title": {"text": "Recaudado ($)"},
                        "min": 0,
                    },
                    "plotOptions": {
                        "column": {"stacking": "normal", "borderRadius": 2}
                    },
                    "series": series,
                    "legend": {"enabled": True},
                    "credits": {"enabled": False},
                }
            )
        else:
            ui.html(
                '<div style="color:#94a3b8;font-size:0.85rem;">'
                "Sin datos en el rango seleccionado."
                "</div>"
            )
