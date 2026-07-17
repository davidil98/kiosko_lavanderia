"""Tab Servicios y Tarifas del superadmin.

CRUD: crear, editar, activar/desactivar, eliminar.
Todos los cambios requieren contraseña de bypass.
"""

from typing import Optional

from nicegui import ui

from app.repo import servicios as repo_servicios
from app.ui.admin.superadmin._componentes import (
    dialogo_bypass,
    dialogo_eliminar_con_bypass,
    password_bypass_correcta,
)


TIPO_LABELS = {
    "fijo": "Precio fijo",
    "por_kg": "Por kilogramo",
    "por_duracion": "Por duración",
}

ICONOS = {
    "/media/icons/leaf.svg": "Hoja (autoservicio)",
    "/media/icons/wind.svg": "Viento (secado)",
    "/media/icons/shirt.svg": "Camisa (personalizado)",
    "/media/icons/bed.svg": "Cama (edredones)",
    "/media/icons/inbox.svg": "Bandeja (entregas)",
    "/media/icons/ticket.svg": "Ticket (Point)",
    "/media/icons/gear.svg": "Engranaje (general)",
}


def render(refresh_parent) -> None:
    """Renderiza el contenido del tab Servicios. `refresh_parent` es un
    callable que re-renderiza el contenido del tab (la función externa)."""
    servicios = repo_servicios._listar(solo_activos=False)
    with ui.row().classes("w-full justify-end mb-3"):
        ui.button(
            "+ Crear servicio",
            on_click=lambda: _abrir_dialogo_crear(refresh_parent),
        ).props("color=primary")
    if not servicios:
        ui.html(
            '<div class="empty-state">No hay servicios configurados. '
            "Crea el primero con el botón de arriba.</div>"
        )
        return
    for s in servicios:
        _render_card(s, refresh_parent)


def _render_card(s, refresh_parent) -> None:
    tipo_label = TIPO_LABELS.get(s.tipo_calculo, s.tipo_calculo)
    activo_color = "#16a34a" if s.activo else "#94a3b8"
    activo_label = "Activo" if s.activo else "Inactivo"
    with (
        ui.element("div")
        .classes("orden-card")
        .style(f"border-left:4px solid {activo_color};")
    ):
        with ui.element("div").style("flex:1;min-width:0;"):
            ui.html(
                f'<div class="orden-numero">{s.codigo}</div>'
                f'<div style="font-size:1.1rem;font-weight:800;color:#1e293b;">'
                f"{s.nombre}</div>"
                f'<div style="font-size:0.85rem;color:#64748b;">'
                f"Modalidad: <strong>{s.modalidad}</strong> · "
                f"Tipo: <strong>{tipo_label}</strong> · "
                f'<span style="color:{activo_color};font-weight:700;">{activo_label}</span>'
                f"</div>"
                f'<div style="font-size:0.85rem;color:#64748b;margin-top:4px;">'
                f"Precio base: <strong>${s.precio_fijo or 0}</strong>"
                + (
                    f" · Tarifa/kg: <strong>${s.tarifa_por_kg}</strong>"
                    if s.tipo_calculo == "por_kg"
                    else ""
                )
                + f" · Duración: <strong>{s.duracion_min} min</strong>"
                + (
                    f" · Límite: <strong>{s.limite_kg} kg</strong>"
                    if s.limite_kg
                    else ""
                )
                + f" · Tipos equipo: <strong>{s.tipos_equipo or 'cualquiera'}</strong>"
                + f"</div>"
            )
        with ui.element("div").style(
            "flex-shrink:0;display:flex;flex-direction:column;gap:8px;align-items:flex-end;"
        ):
            ui.button(
                "✎ Editar",
                color="primary",
                on_click=lambda sid=s.id: _abrir_dialogo_editar(sid, refresh_parent),
            )
            label = "⏸ Desactivar" if s.activo else "▶ Activar"
            color = "warning" if s.activo else "positive"
            ui.button(
                label,
                color=color,
                on_click=lambda srv=s: dialogo_bypass(
                    lambda: _toggle(srv), titulo=f"Activar/Desactivar {srv.codigo}"
                ),
            )
            ui.button(
                "🗑 Eliminar",
                color="negative",
                on_click=lambda srv=s: dialogo_eliminar_con_bypass(
                    srv.codigo,
                    lambda: _eliminar(srv.id, refresh_parent),
                    titulo="Eliminar servicio",
                ),
            )


def _toggle(s) -> None:
    """Activa/desactiva el servicio. Se llama dentro de dialogo_bypass."""
    s.activo = not s.activo
    import asyncio

    asyncio.create_task(
        repo_servicios.actualizar(
            s.id,
            nombre=s.nombre,
            tipo_calculo=s.tipo_calculo,
            precio_fijo=s.precio_fijo,
            tarifa_por_kg=s.tarifa_por_kg,
            duracion_min=s.duracion_min,
            limite_kg=s.limite_kg,
            tipos_equipo=s.tipos_equipo,
            activo=s.activo,
        )
    )
    ui.notify(
        f"Servicio {'activado' if s.activo else 'desactivado'}",
        type="positive",
    )
    # Re-cargar la lista


def _eliminar(id_servicio: int, refresh_parent) -> None:
    import asyncio

    async def go():
        ok = await repo_servicios.eliminar_hard(id_servicio)
        if ok:
            ui.notify("Servicio eliminado", type="positive")
        else:
            ui.notify(
                "No se puede eliminar: hay órdenes con este servicio. "
                "Desactívalo en su lugar.",
                type="negative",
                timeout=8000,
            )

    asyncio.create_task(go())


# ── Diálogos de creación / edición ─────────────────────────────────────────


def _abrir_dialogo_crear(refresh_parent) -> None:
    _abrir_dialogo_formulario(existente=None, refresh_parent=refresh_parent)


def _abrir_dialogo_editar(id_servicio: int, refresh_parent) -> None:
    existente = repo_servicios._obtener_por_id(id_servicio)
    if existente is None:
        ui.notify("Servicio no encontrado", type="negative")
        return
    _abrir_dialogo_formulario(existente=existente, refresh_parent=refresh_parent)


def _abrir_dialogo_formulario(existente, refresh_parent) -> None:
    """Diálogo de creación o edición. `existente=None` significa crear."""
    refs: dict = {}

    def guardar() -> None:
        # 1. Bypass
        if not password_bypass_correcta(refs["pwd"].value or ""):
            ui.notify("Contraseña incorrecta", type="negative")
            return
        # 2. Código
        codigo = (refs["codigo"].value or "").strip().lower().replace(" ", "_")
        if not codigo or not all(c.isalnum() or c == "_" for c in codigo):
            ui.notify(
                "Código inválido (solo letras, números y guiones bajos)",
                type="negative",
            )
            return
        # 3. Nombre
        nombre = (refs["nombre"].value or "").strip()
        if not nombre:
            ui.notify("El nombre es obligatorio", type="negative")
            return
        # 4. Campos numéricos
        try:
            precio = int(float(refs["precio"].value or 0))
            tarifa = float(refs["tarifa"].value or 0)
            duracion = int(float(refs["duracion"].value or 45))
        except ValueError:
            ui.notify("Campos numéricos inválidos", type="negative")
            return
        limite = None
        if refs["limite"].value not in (None, "", "0"):
            try:
                limite = int(float(refs["limite"].value))
            except ValueError:
                ui.notify("Límite de kg inválido", type="negative")
                return
        tipos_equipo = (refs["tipos"].value or "").strip()
        modalidad = refs["modalidad"].value or "autoservicio"
        tipo = refs["tipo"].value or "fijo"
        icono = refs["icono"].value or "/media/icons/leaf.svg"

        import asyncio

        async def go():
            if existente is None:
                new_id = await repo_servicios.crear(
                    codigo=codigo,
                    nombre=nombre,
                    modalidad=modalidad,
                    icono=icono,
                    tipo_calculo=tipo,
                    precio_fijo=precio,
                    tarifa_por_kg=tarifa,
                    duracion_min=duracion,
                    limite_kg=limite,
                    tipos_equipo=tipos_equipo,
                    activo=True,
                )
                if new_id is None:
                    ui.notify("Código duplicado", type="negative")
                else:
                    ui.notify(f"Servicio '{nombre}' creado", type="positive")
                    dlg.close()
            else:
                await repo_servicios.actualizar(
                    existente.id,
                    nombre=nombre,
                    tipo_calculo=tipo,
                    precio_fijo=precio,
                    tarifa_por_kg=tarifa,
                    duracion_min=duracion,
                    limite_kg=limite,
                    tipos_equipo=tipos_equipo,
                    activo=existente.activo,
                )
                ui.notify(f"Servicio '{nombre}' actualizado", type="positive")
                dlg.close()

        asyncio.create_task(go())

    titulo = "Editar servicio" if existente else "Crear servicio"
    with ui.dialog() as dlg, ui.card().style("min-width:560px;max-width:720px;"):
        ui.label(titulo).classes("text-lg font-bold text-slate-800 mb-2")
        ui.html(
            '<p style="font-size:0.78rem;color:#64748b;margin-bottom:12px;">'
            "Los campos marcados con <strong>*</strong> son obligatorios. "
            "Activar/Desactivar no requieren bypass; crear/editar/eliminar sí."
            "</p>"
        )
        refs["codigo"] = ui.input(
            "Código único * (sin espacios, ej. 'secado_express')",
            value=existente.codigo if existente else "",
        ).classes("w-full mb-2")
        refs["nombre"] = ui.input(
            "Nombre visible *",
            value=existente.nombre if existente else "",
        ).classes("w-full mb-2")
        refs["modalidad"] = ui.select(
            {
                "autoservicio": "Autoservicio (cliente se atiende solo)",
                "personalizado": "Personalizado (lo entrega un operador)",
            },
            value=existente.modalidad if existente else "autoservicio",
            label="Modalidad *",
        ).classes("w-full mb-2")
        refs["icono"] = ui.select(
            ICONOS,
            value=existente.icono if existente else "/media/icons/leaf.svg",
            label="Icono",
        ).classes("w-full mb-2")
        refs["tipo"] = ui.select(
            {
                "fijo": "Precio fijo (ej. $45 por servicio completo)",
                "por_kg": "Por kilogramo (ej. $30/kg según el peso)",
                "por_duracion": "Por duración",
            },
            value=existente.tipo_calculo if existente else "fijo",
            label="Tipo de cálculo *",
        ).classes("w-full mb-2")
        refs["precio"] = (
            ui.input(
                "Precio fijo ($)",
                value=str(existente.precio_fijo or 0) if existente else "0",
            )
            .props("type=number min=0")
            .classes("w-full mb-2")
        )
        refs["tarifa"] = (
            ui.input(
                "Tarifa por kg ($)",
                value=str(existente.tarifa_por_kg or 0) if existente else "0",
            )
            .props("type=number min=0 step=0.01")
            .classes("w-full mb-2")
        )
        refs["duracion"] = (
            ui.input(
                "Duración estimada (min)",
                value=str(existente.duracion_min) if existente else "45",
            )
            .props("type=number min=1")
            .classes("w-full mb-2")
        )
        refs["limite"] = (
            ui.input(
                "Límite de kg (vacío = sin límite)",
                value=str(existente.limite_kg)
                if existente and existente.limite_kg
                else "",
                placeholder="ej. 5",
            )
            .props("type=number min=0")
            .classes("w-full mb-2")
        )
        refs["tipos"] = ui.input(
            "Tipos de máquina permitidos (separa con comas)",
            value=existente.tipos_equipo if existente else "",
            placeholder="ej. mixto, lavado",
        ).classes("w-full mb-2")
        refs["pwd"] = (
            ui.input(
                "Contraseña de bypass",
                password=True,
            )
            .props("type=password")
            .classes("w-full mb-4")
        )
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Guardar", on_click=guardar).props("color=primary")
    dlg.open()
