"""Tab Segmentaciones del superadmin. CRUD dentro de cada servicio."""

from typing import Optional

from nicegui import ui

from app.core.servicios import cargar_servicio_por_id
from app.repo import segmentaciones as repo_segmentaciones
from app.repo import servicios as repo_servicios
from app.ui.admin.superadmin._componentes import (
    dialogo_eliminar_con_bypass,
    password_bypass_correcta,
)


def render(refresh_parent) -> None:
    servicios = repo_servicios._listar(solo_activos=False)
    for srv in servicios:
        segs = repo_segmentaciones._listar(servicio_id=srv.id, solo_activos=False)
        _render_seccion_servicio(srv, segs, refresh_parent)


def _render_seccion_servicio(srv, segs: list, refresh_parent) -> None:
    with ui.element("div").style(
        "background:#f8fafc;padding:12px 16px;border-radius:8px;margin-bottom:14px;"
    ):
        with ui.row().classes("w-full items-center justify-between"):
            ui.html(
                f'<div><strong style="color:#1e293b;">{srv.nombre}</strong>'
                f'<span style="color:#94a3b8;font-size:0.85rem;margin-left:8px;">'
                f"({len(segs)} segmentaciones)</span></div>"
            )
            ui.button(
                "+ Segmentación",
                on_click=lambda s=srv: _abrir_dialogo_crear(s.id, refresh_parent),
            ).props("color=primary")
    if not segs:
        ui.html(
            '<div style="text-align:center;color:#94a3b8;padding:12px;">'
            "Sin segmentaciones para este servicio.</div>"
        )
        return
    for seg in segs:
        _render_card(seg, refresh_parent)


def _render_card(seg, refresh_parent) -> None:
    activo_color = "#16a34a" if seg.activo else "#94a3b8"
    with (
        ui.element("div")
        .classes("orden-card")
        .style(f"border-left:4px solid {activo_color};")
    ):
        with ui.element("div").style("flex:1;min-width:0;"):
            ui.html(
                f'<div style="font-size:1rem;font-weight:700;color:#1e293b;">'
                f"{seg.nombre}</div>"
                f'<div style="font-size:0.85rem;color:#64748b;">'
                f"Código: <code>{seg.codigo}</code> · "
                f"Tipo: <strong>{seg.tipo_calculo}</strong> · "
                + (
                    f"Precio: <strong>${seg.precio_fijo}</strong>"
                    if seg.tipo_calculo == "fijo"
                    else f"Tarifa/kg: <strong>${seg.tarifa_por_kg}</strong>"
                )
                + f" · {seg.duracion_min} min"
                + f"</div>"
            )
            if seg.descripcion:
                ui.html(
                    f'<div style="font-size:0.82rem;color:#64748b;margin-top:4px;">'
                    f"{seg.descripcion}</div>"
                )
        with ui.element("div").style(
            "display:flex;flex-direction:column;gap:6px;align-items:flex-end;"
        ):
            ui.button(
                "✎ Editar",
                color="primary",
                on_click=lambda sid=seg.id: _abrir_dialogo_editar(sid, refresh_parent),
            )
            ui.button(
                "🗑 Eliminar",
                color="negative",
                on_click=lambda ss=seg: dialogo_eliminar_con_bypass(
                    ss.nombre,
                    lambda: _eliminar(ss.id, refresh_parent),
                    titulo="Eliminar segmentación",
                ),
            )


def _eliminar(id_seg: int, refresh_parent) -> None:
    import asyncio

    async def go():
        ok = await repo_segmentaciones.eliminar_hard(id_seg)
        if ok:
            ui.notify("Segmentación eliminada", type="positive")
        else:
            ui.notify(
                "No se puede eliminar: hay órdenes con esta segmentación.",
                type="negative",
                timeout=8000,
            )

    asyncio.create_task(go())


def _abrir_dialogo_crear(servicio_id: int, refresh_parent) -> None:
    _abrir_dialogo_formulario(servicio_id, None, refresh_parent)


def _abrir_dialogo_editar(id_seg: int, refresh_parent) -> None:
    existente = repo_segmentaciones._obtener_por_id(id_seg)
    if existente is None:
        ui.notify("Segmentación no encontrada", type="negative")
        return
    _abrir_dialogo_formulario(existente.servicio_id, existente, refresh_parent)


def _abrir_dialogo_formulario(servicio_id: int, existente, refresh_parent) -> None:
    refs: dict = {}

    def guardar() -> None:
        if not password_bypass_correcta(refs["pwd"].value or ""):
            ui.notify("Contraseña incorrecta", type="negative")
            return
        codigo = (refs["codigo"].value or "").strip().lower().replace(" ", "_")
        if not codigo or not all(c.isalnum() or c == "_" for c in codigo):
            ui.notify("Código inválido", type="negative")
            return
        nombre = (refs["nombre"].value or "").strip()
        if not nombre:
            ui.notify("El nombre es obligatorio", type="negative")
            return
        descripcion = (refs["desc"].value or "").strip()
        try:
            precio = int(float(refs["precio"].value or 0))
            tarifa = float(refs["tarifa"].value or 0)
            duracion = int(float(refs["duracion"].value or 60))
        except ValueError:
            ui.notify("Campos numéricos inválidos", type="negative")
            return
        tipo = refs["tipo"].value or "fijo"
        import asyncio

        async def go():
            if existente is None:
                new_id = await repo_segmentaciones.crear(
                    servicio_id=servicio_id,
                    codigo=codigo,
                    nombre=nombre,
                    descripcion=descripcion,
                    tipo_calculo=tipo,
                    precio_fijo=precio,
                    tarifa_por_kg=tarifa,
                    duracion_min=duracion,
                    activo=True,
                )
                if new_id is None:
                    ui.notify("Código duplicado", type="negative")
                else:
                    ui.notify(f"Segmentación '{nombre}' creada", type="positive")
                    dlg.close()
            else:
                await repo_segmentaciones.actualizar(
                    existente.id,
                    nombre=nombre,
                    descripcion=descripcion,
                    tipo_calculo=tipo,
                    precio_fijo=precio,
                    tarifa_por_kg=tarifa,
                    duracion_min=duracion,
                    activo=existente.activo,
                )
                ui.notify(f"Segmentación '{nombre}' actualizada", type="positive")
                dlg.close()

        asyncio.create_task(go())

    titulo = "Editar segmentación" if existente else "Crear segmentación"
    with ui.dialog() as dlg, ui.card().style("min-width:520px;max-width:680px;"):
        ui.label(titulo).classes("text-lg font-bold text-slate-800 mb-2")
        refs["codigo"] = ui.input(
            "Código * (sin espacios)",
            value=existente.codigo if existente else "",
        ).classes("w-full mb-2")
        refs["nombre"] = ui.input(
            "Nombre *",
            value=existente.nombre if existente else "",
        ).classes("w-full mb-2")
        refs["desc"] = ui.input(
            "Descripción",
            value=existente.descripcion if existente else "",
        ).classes("w-full mb-2")
        refs["tipo"] = ui.select(
            {"fijo": "Precio fijo", "por_kg": "Por kilogramo"},
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
                "Tarifa/kg ($)",
                value=str(existente.tarifa_por_kg or 0) if existente else "0",
            )
            .props("type=number min=0 step=0.01")
            .classes("w-full mb-2")
        )
        refs["duracion"] = (
            ui.input(
                "Duración (min)",
                value=str(existente.duracion_min) if existente else "60",
            )
            .props("type=number min=1")
            .classes("w-full mb-2")
        )
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
