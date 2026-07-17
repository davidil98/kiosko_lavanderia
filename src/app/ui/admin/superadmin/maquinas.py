"""Tab Máquinas del superadmin. CRUD de lavadoras/secadoras."""

from typing import Optional

from nicegui import ui

from app.core.maquinas import recargar_equipos
from app.repo import maquinas as repo_maquinas
from app.ui.admin.superadmin._componentes import (
    dialogo_eliminar_con_bypass,
    password_bypass_correcta,
)


TIPOS = {
    "lavado": "Solo lavado",
    "secado": "Solo secado",
    "mixto": "Lava y seca",
    "doblado": "Doblado",
}
MODOS = {"pulso": "Pulso (0.5s)", "sostenido": "Sostenido"}


def render(refresh_parent) -> None:
    maquinas = repo_maquinas._listar(solo_activas=False)
    with ui.row().classes("w-full justify-end mb-3"):
        ui.button(
            "+ Crear máquina",
            color="primary",
            on_click=lambda: _abrir_dialogo_crear(refresh_parent),
        )
    if not maquinas:
        ui.html('<div class="empty-state">No hay máquinas configuradas.</div>')
        return
    for m in maquinas:
        _render_card(m, refresh_parent)


def _render_card(m, refresh_parent) -> None:
    activo_color = "#16a34a" if m.activa else "#94a3b8"
    with (
        ui.element("div")
        .classes("orden-card")
        .style(f"border-left:4px solid {activo_color};")
    ):
        with ui.element("div").style("flex:1;min-width:0;"):
            ui.html(
                f'<div style="font-size:1rem;font-weight:800;color:#1e293b;">'
                f'{m.nombre} <span style="font-size:0.78rem;color:#64748b;">'
                f"({m.codigo})</span></div>"
                f'<div style="font-size:0.85rem;color:#64748b;">'
                f"Tipo: <strong>{m.tipo}</strong> · Capacidad: <strong>"
                f"{m.capacidad_kg} kg</strong> · GPIO: <code>{m.gpio}</code> · "
                f"Modo: <strong>{m.modo}</strong>"
                + (f" · {m.duracion_max_min} min" if m.modo == "sostenido" else "")
                + f"</div>"
            )
        with ui.element("div").style(
            "display:flex;flex-direction:column;gap:6px;align-items:flex-end;"
        ):
            ui.button(
                "✎ Editar",
                color="primary",
                on_click=lambda mid=m.id: _abrir_dialogo_editar(mid, refresh_parent),
            )
            label = "⏸ Desactivar" if m.activa else "▶ Activar"
            color = "warning" if m.activa else "positive"
            ui.button(
                label,
                color=color,
                on_click=lambda mm=m: dialogo_bypass(
                    lambda: _toggle(mm), titulo=f"Activar/Desactivar {mm.codigo}"
                ),
            )
            ui.button(
                "🗑 Eliminar",
                color="negative",
                on_click=lambda mm=m: dialogo_eliminar_con_bypass(
                    mm.nombre,
                    lambda: _eliminar(mm.id, refresh_parent),
                    titulo="Eliminar máquina",
                ),
            )


def dialogo_bypass(on_autorizar, titulo: str) -> None:
    """Reuso del diálogo bypass (mismo que en servicios)."""
    from app.ui.admin.superadmin._componentes import dialogo_bypass as _db

    _db(on_autorizar, titulo)


def _toggle(m) -> None:
    m.activa = not m.activa
    import asyncio

    asyncio.create_task(
        repo_maquinas.actualizar(
            m.id,
            nombre=m.nombre,
            tipo=m.tipo,
            capacidad_kg=m.capacidad_kg,
            gpio=m.gpio,
            modo=m.modo,
            duracion_max_min=m.duracion_max_min,
            orden=m.orden,
            activa=m.activa,
        )
    )
    recargar_equipos()
    ui.notify(
        f"Máquina {'activada' if m.activa else 'desactivada'}",
        type="positive",
    )


def _eliminar(id_maquina: int, refresh_parent) -> None:
    import asyncio

    async def go():
        ok = await repo_maquinas.eliminar_hard(id_maquina)
        if ok:
            recargar_equipos()
            ui.notify("Máquina eliminada", type="positive")
        else:
            ui.notify(
                "No se puede eliminar: hay órdenes con esta máquina. "
                "Desactívala en su lugar.",
                type="negative",
                timeout=8000,
            )

    asyncio.create_task(go())


def _abrir_dialogo_crear(refresh_parent) -> None:
    _abrir_dialogo_formulario(None, refresh_parent)


def _abrir_dialogo_editar(id_maquina: int, refresh_parent) -> None:
    existente = repo_maquinas._obtener_por_id(id_maquina)
    if existente is None:
        ui.notify("Máquina no encontrada", type="negative")
        return
    _abrir_dialogo_formulario(existente, refresh_parent)


def _abrir_dialogo_formulario(existente, refresh_parent) -> None:
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
        try:
            capacidad = int(float(refs["capacidad"].value or 5))
            gpio = int(float(refs["gpio"].value or 0))
            duracion = int(float(refs["duracion"].value or 25))
        except ValueError:
            ui.notify("Campos numéricos inválidos", type="negative")
            return
        if not (4 <= gpio <= 27):
            ui.notify("GPIO debe estar entre 4 y 27 (BCM)", type="negative")
            return
        tipo = refs["tipo"].value or "mixto"
        modo = refs["modo"].value or "pulso"

        import asyncio

        async def go():
            if existente is None:
                new_id = await repo_maquinas.crear(
                    codigo=codigo,
                    nombre=nombre,
                    tipo=tipo,
                    capacidad_kg=capacidad,
                    gpio=gpio,
                    modo=modo,
                    duracion_max_min=duracion,
                    activa=True,
                )
                if new_id is None:
                    ui.notify("Código duplicado", type="negative")
                else:
                    recargar_equipos()
                    ui.notify(f"Máquina '{nombre}' creada", type="positive")
                    dlg.close()
            else:
                await repo_maquinas.actualizar(
                    existente.id,
                    nombre=nombre,
                    tipo=tipo,
                    capacidad_kg=capacidad,
                    gpio=gpio,
                    modo=modo,
                    duracion_max_min=duracion,
                    orden=existente.orden,
                    activa=existente.activa,
                )
                recargar_equipos()
                ui.notify(f"Máquina '{nombre}' actualizada", type="positive")
                dlg.close()

        asyncio.create_task(go())

    titulo = "Editar máquina" if existente else "Crear máquina"
    with ui.dialog() as dlg, ui.card().style("min-width:520px;"):
        ui.label(titulo).classes("text-lg font-bold text-slate-800 mb-2")
        refs["codigo"] = ui.input(
            "Código * (sin espacios)",
            value=existente.codigo if existente else "",
        ).classes("w-full mb-2")
        refs["nombre"] = ui.input(
            "Nombre visible *",
            value=existente.nombre if existente else "",
        ).classes("w-full mb-2")
        refs["tipo"] = ui.select(
            TIPOS,
            value=existente.tipo if existente else "mixto",
            label="Tipo *",
        ).classes("w-full mb-2")
        refs["capacidad"] = (
            ui.input(
                "Capacidad (kg)",
                value=str(existente.capacidad_kg) if existente else "5",
            )
            .props("type=number min=1")
            .classes("w-full mb-2")
        )
        refs["gpio"] = (
            ui.input(
                "Pin GPIO (BCM, 4-27)",
                value=str(existente.gpio) if existente else "17",
            )
            .props("type=number min=4 max=27")
            .classes("w-full mb-2")
        )
        refs["modo"] = ui.select(
            MODOS,
            value=existente.modo if existente else "pulso",
            label="Modo *",
        ).classes("w-full mb-2")
        refs["duracion"] = (
            ui.input(
                "Duración máxima (min, para modo sostenido)",
                value=str(existente.duracion_max_min) if existente else "25",
            )
            .props("type=number min=1")
            .classes("w-full mb-2")
        )
        ui.html(
            '<div style="font-size:0.72rem;color:#f59e0b;margin-bottom:8px;">'
            "⚠ Cambiar el GPIO requiere reiniciar la Pi para que tome efecto."
            "</div>"
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
