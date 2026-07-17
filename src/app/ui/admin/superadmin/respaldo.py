"""Tab Respaldo del superadmin. Crear y restaurar snapshots de los 3 catálogos.

Decisión del usuario: solo una ventana de advertencia al restaurar
('¿Seguro que quiere restaurar a servicios por defecto/respaldo?'),
sin bypass. El crear sí pide bypass.
"""

from nicegui import ui

from app.core.loader import instalar_como_defaults
from app.core.maquinas import recargar_equipos
from app.repo import respaldos as repo_respaldos
from app.ui.admin.superadmin._componentes import (
    dialogo_bypass,
    password_bypass_correcta,
)


def render(refresh_parent) -> None:
    ui.html(
        '<h3 style="font-size:1.15rem;font-weight:700;color:#1e293b;'
        'margin-bottom:8px;">Respaldo de fábrica</h3>'
        '<p style="color:#64748b;font-size:0.88rem;margin-bottom:18px;">'
        "Los 3 catálogos (servicios, segmentaciones, máquinas) se guardan "
        "como un snapshot JSON. Restaurar los reemplaza con el snapshot. "
        "Las órdenes históricas <strong>no se tocan</strong>."
        "</p>"
    )
    with ui.row().classes("w-full gap-3 mb-4"):
        ui.button(
            "💾 Crear respaldo ahora",
            color="primary",
            on_click=lambda: dialogo_bypass(
                _crear_respaldo, titulo="Crear respaldo de fábrica"
            ),
        )
        ui.button(
            "⚠ Restaurar desde respaldo",
            color="warning",
            on_click=lambda: _abrir_dialogo_restaurar(refresh_parent),
        )

    ui.html(
        '<h3 style="font-size:1.05rem;font-weight:700;margin-top:24px;margin-bottom:8px;">Snapshots existentes</h3>'
    )
    respaldos = repo_respaldos._listar()
    if not respaldos:
        ui.html(
            '<div style="text-align:center;color:#94a3b8;padding:14px;">'
            "No hay respaldos guardados. Crea el primero con el botón de arriba.</div>"
        )
        return
    for r in respaldos:
        with ui.element("div").style(
            "background:white;padding:10px 14px;border-radius:6px;margin-bottom:6px;"
            "display:flex;align-items:center;gap:10px;font-size:0.88rem;"
        ):
            ui.html(
                f'<strong style="color:#1e293b;">{r["tabla"]}</strong>'
                f'<span style="color:#94a3b8;">{r["created_at"]}</span>'
                f'<span style="color:#475569;margin-left:8px;">'
                f"<em>{r['nota']}</em></span>"
            )


def _crear_respaldo() -> None:
    """Crea un respaldo de los 3 catálogos. Se llama dentro de dialogo_bypass."""
    import asyncio

    async def go():
        r = await repo_respaldos.crear_completo("Respaldo manual")
        total = sum(r.values())
        ui.notify(f"Respaldo creado ({total} filas)", type="positive")

    asyncio.create_task(go())


def _abrir_dialogo_restaurar(refresh_parent) -> None:
    """Advertencia explícita antes de restaurar. NO requiere bypass."""
    pwd_ref: dict = {"input": None}

    def confirmar() -> None:
        pwd = pwd_ref["input"].value if pwd_ref["input"] else ""
        if not password_bypass_correcta(pwd):
            ui.notify("Contraseña incorrecta", type="negative")
            return
        import asyncio

        async def go():
            r = await repo_respaldos.restaurar_completo()
            ui.notify("Restauración completada", type="positive")
            recargar_equipos()
            instalar_como_defaults()

        asyncio.create_task(go())
        dlg.close()

    with ui.dialog() as dlg, ui.card().style("min-width:400px;"):
        ui.html(
            '<div style="font-size:1.1rem;font-weight:700;color:#dc2626;'
            'margin-bottom:8px;">⚠ ¿Seguro que quiere restaurar?</div>'
            '<p style="color:#475569;font-size:0.88rem;margin-bottom:12px;">'
            "Esto reemplazará los <strong>servicios, segmentaciones y "
            "máquinas</strong> actuales con la versión guardada en el "
            "respaldo. Las órdenes históricas NO se tocan."
            "</p>"
            '<p style="color:#94a3b8;font-size:0.78rem;margin-bottom:12px;">'
            "Esta acción no se puede deshacer."
            "</p>"
        )
        pwd_ref["input"] = (
            ui.input(
                "Contraseña de bypass (por seguridad)",
                password=True,
            )
            .props("type=password")
            .classes("w-full mb-3")
        )
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Cancelar", on_click=dlg.close).props("flat")
            ui.button("Sí, restaurar", color="negative", on_click=confirmar)
    dlg.open()
