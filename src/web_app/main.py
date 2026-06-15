from nicegui import ui, app, Client
import asyncio
from models import (
    KioskoState,
    SERVICIOS_AUTO,
    SERVICIOS_PERSONALIZADO,
    PASOS,
    get_limite_kg,
)
import database_web
import hardware
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEDIA_DIR = os.path.join(BASE_DIR, "media")

# ──────────────────────────────────────────────
#  USUARIOS ESTÁTICOS (cambiar contraseñas aquí)
# ──────────────────────────────────────────────
USUARIOS = {
    "Moi": "admin123",
    "Capi": "socio123",
    "David": "admin456",
}

# ──────────────────────────────────────────────
#  ESTADO GLOBAL
# ──────────────────────────────────────────────
state = KioskoState()

_admin_refresh_callbacks: list = []
_admin_clients: dict = {}


def registrar_callback_admin(cb):
    _admin_refresh_callbacks.append(cb)


def remover_callback_admin(cb):
    if cb in _admin_refresh_callbacks:
        _admin_refresh_callbacks.remove(cb)


def notificar_admin():
    for cb in list(_admin_refresh_callbacks):
        try:
            res = cb()
            if asyncio.iscoroutine(res):
                asyncio.create_task(res)
        except Exception:
            pass


# ── Hardware ──
def on_moneda_ingresada(valor):
    if state.servicio_seleccionado and not state.exito:
        state.ingresar_dinero(valor)


lector_monedas = hardware.LectorMonedas(callback=on_moneda_ingresada)
app.on_startup(lector_monedas.start)
hardware.init_gpio_lavadoras()

database_web.init_db()
app.add_static_files("/media", MEDIA_DIR)

# ──────────────────────────────────────────────
#  CSS COMPARTIDO
# ──────────────────────────────────────────────
FONTS_HTML = """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
"""

KIOSKO_CSS = """
<style>
    * { box-sizing: border-box; }
    html, body {
        margin: 0; padding: 0; width: 100%; height: 100%;
        overflow: hidden; font-family: 'Inter', sans-serif;
        background: #1a1a2e; color: #e2e8f0;
    }
    #kiosko-root { display: flex; width: 100vw; height: 100vh; }
    #sidebar {
        width: 180px; flex-shrink: 0; background: #16213e;
        display: flex; flex-direction: column;
        border-right: 2px solid #0f3460;
    }
    .sidebar-title {
        padding: 16px 12px; font-size: 0.78rem; font-weight: 700;
        color: #64748b; text-transform: uppercase; letter-spacing: 0.1em;
        text-align: center; border-bottom: 1px solid #0f3460;
    }
    .paso-item {
        padding: 14px 12px; font-size: 0.82rem; line-height: 1.35;
        color: #475569; border-bottom: 1px solid #0f3460;
        display: flex; align-items: center; gap: 10px; font-weight: 500;
    }
    .paso-item .num {
        width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0;
        display: flex; align-items: center; justify-content: center;
        font-size: 0.7rem; font-weight: 700;
        background: #1e293b; color: #475569; border: 2px solid #334155;
    }
    .paso-item.activo { color: #93c5fd; background: rgba(96,165,250,0.07); border-left: 3px solid #3b82f6; }
    .paso-item.activo .num { background: #3b82f6; color: #fff; border-color: #3b82f6; }
    .paso-item.completado { color: #4ade80; }
    .paso-item.completado .num { background: #16a34a; color: #fff; border-color: #16a34a; }
    #main-col { flex: 1; display: flex; flex-direction: column; min-width: 0; }
    #header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 8px 18px; background: #16213e;
        border-bottom: 2px solid #0f3460; flex-shrink: 0;
    }
    #header .logo-area { display: flex; align-items: center; gap: 12px; }
    #header .titulo { font-size: 1.3rem; font-weight: 800; color: #e2e8f0; }
    #header .reloj { font-size: 0.82rem; color: #94a3b8; text-align: right; line-height: 1.65; }
    #content {
        flex: 1; display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        padding: 16px; overflow: hidden;
    }
    .instruccion {
        font-size: 1.1rem; color: #94a3b8; margin-bottom: 22px;
        text-align: center; font-weight: 500;
    }
    /* Tarjetas de servicio */
    .card-servicio {
        cursor: pointer; border-radius: 16px;
        background: #16213e; border: 2px solid #0f3460;
        padding: 24px 20px; width: 185px;
        display: flex; flex-direction: column; align-items: center;
        gap: 6px; transition: all 0.22s; user-select: none;
    }
    .card-servicio:hover {
        border-color: #3b82f6; background: #1e3a5f;
        transform: translateY(-4px);
        box-shadow: 0 10px 24px rgba(59,130,246,0.22);
    }
    .card-personalizado { border-color: #7c3aed; }
    .card-personalizado:hover { border-color: #a78bfa; background: #2e1065; box-shadow: 0 10px 24px rgba(139,92,246,0.22); }
    /* Panel nombre/peso */
    #nombre-panel {
        background: #16213e; border: 2px solid #0f3460;
        border-radius: 18px; padding: 24px 28px;
        width: 100%; max-width: 480px; text-align: center;
    }
    .btn-confirmar-nombre {
        margin-top: 14px; width: 100%; padding: 13px;
        background: #3b82f6; color: #fff; border: none; border-radius: 12px;
        font-size: 1rem; font-weight: 700; cursor: pointer; transition: background 0.2s;
    }
    .btn-confirmar-nombre:hover { background: #2563eb; }
    .btn-confirmar-nombre:disabled { background: #1e3a5f; color: #475569; cursor: not-allowed; }
    /* Panel numérico (peso) */
    .numpad { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 12px; }
    .numpad-btn {
        background: #1e293b; color: #e2e8f0; border: 1px solid #334155;
        border-radius: 10px; padding: 14px 0; font-size: 1.4rem; font-weight: 700;
        cursor: pointer; text-align: center; transition: background 0.15s;
    }
    .numpad-btn:hover { background: #2d3f55; }
    .numpad-btn:active { background: #3b82f6; }
    .numpad-display {
        font-size: 2.8rem; font-weight: 800; color: #60a5fa;
        background: #0f172a; border-radius: 12px; padding: 10px 20px;
        margin: 10px 0; border: 1px solid #1e3a5f; text-align: center;
        letter-spacing: 0.05em;
    }
    /* Panel pago */
    #pago-panel {
        background: #16213e; border: 2px solid #0f3460;
        border-radius: 18px; padding: 22px 26px;
        width: 100%; max-width: 400px;
    }
    .monto-box {
        background: #0f172a; border-radius: 12px;
        padding: 16px; text-align: center; margin: 14px 0;
        border: 1px solid #1e3a5f;
    }
    .monto-label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.1em; }
    .monto-valor { font-size: 3.2rem; font-weight: 800; color: #60a5fa; line-height: 1.1; }
    .monto-sub { font-size: 0.9rem; color: #94a3b8; margin-top: 4px; }
    .progress-bar-bg { background: #0f172a; border-radius: 6px; height: 9px; overflow: hidden; margin: 4px 0 2px; }
    .progress-bar-fill { height: 100%; background: linear-gradient(90deg,#3b82f6,#8b5cf6); border-radius: 6px; transition: width 0.4s; }
    .progress-pct { font-size: 0.72rem; color: #475569; margin-bottom: 12px; }
    .btn-cancelar {
        width: 100%; margin-top: 10px; padding: 11px;
        background: #D10000; color: #FF5C5C; border: none; border-radius: 11px;
        font-size: 0.95rem; font-weight: 600; cursor: pointer; transition: background 0.2s;
    }
    .btn-cancelar:hover { background: #FF5C5C; }
    /* Éxito */
    #exito-panel { text-align: center; width: 100%; max-width: 420px; }
    .exito-icono { font-size: 4.5rem; }
    .exito-titulo { font-size: 2rem; font-weight: 800; color: #4ade80; margin: 10px 0 6px; }
    .exito-subtitulo { font-size: 1.1rem; color: #94a3b8; margin-bottom: 14px; }
    .exito-datos {
        background: #16213e; border: 1px solid #0f3460;
        border-radius: 14px; padding: 14px 20px; margin-bottom: 14px; text-align: left;
    }
    .exito-dato-row { display: flex; justify-content: space-between; align-items: center; padding: 5px 0; }
    .exito-dato-label { font-size: 0.82rem; color: #64748b; font-weight: 600; }
    .exito-dato-val { font-size: 0.95rem; color: #e2e8f0; font-weight: 700; }
    .cambio-box {
        background: rgba(234,179,8,0.13); border: 1px solid rgba(234,179,8,0.3);
        border-radius: 12px; padding: 10px 18px; font-size: 1.1rem;
        color: #fde68a; font-weight: 700; margin-top: 8px; display: inline-block;
    }
    .reinicio-txt { font-size: 0.82rem; color: #475569; margin-top: 16px; }
</style>
"""

ADMIN_CSS = """
<style>
    * { box-sizing: border-box; }
    body { background: #f1f5f9; font-family: 'Inter', sans-serif; margin: 0; color: #1e293b; }
    .nicegui-content {
        max-width: none !important; padding: 0 !important; margin: 0 auto !important;
        align-items: center !important; justify-content: flex-start !important;
        display: flex !important; flex-direction: column !important;
    }
    #admin-header {
        background: white; border-bottom: 2px solid #e2e8f0;
        padding: 14px 36px; position: sticky; top: 0; z-index: 10;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        width: 100%;
    }
    #admin-header-inner {
        width: 100%; max-width: 1200px; margin: 0 auto;
        display: flex; align-items: center; justify-content: space-between;
    }
    .logo-area { display: flex; align-items: center; gap: 14px; }
    .logo-area img { width: 46px; height: 46px; object-fit: contain; }
    .admin-title { font-size: 1.35rem; font-weight: 800; color: #1e293b; }
    .admin-subtitle { font-size: 0.8rem; color: #64748b; font-weight: 500; }
    #status-indicator { font-size: 0.82rem; color: #64748b; display: flex; align-items: center; gap: 8px; }
    .dot-live { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; animation: pulse-green 2s infinite; }
    @keyframes pulse-green { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }
    #admin-content { padding: 28px 36px; margin: 0 auto; width: 100%; max-width: 1200px; }
    .seccion-header {
        display: flex; align-items: center; gap: 10px;
        font-size: 0.9rem; font-weight: 700; color: #475569;
        text-transform: uppercase; letter-spacing: 0.07em;
        padding-bottom: 10px; margin-bottom: 16px;
        border-bottom: 2px solid #e2e8f0;
    }
    .badge { padding: 2px 12px; border-radius: 999px; font-size: 0.78rem; font-weight: 700; }
    .badge-pendiente { background: #fef3c7; color: #92400e; }
    .badge-en-proceso { background: #fde8d8; color: #9a3412; }
    .orden-card {
        background: white; border-radius: 14px; border: 1px solid #e2e8f0;
        padding: 18px 22px; margin-bottom: 12px;
        display: flex; align-items: center; justify-content: space-between;
        gap: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        transition: box-shadow 0.2s;
    }
    .orden-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
    .orden-card.en-proceso { border-left: 4px solid #f59e0b; }
    .orden-nombre { font-size: 1.2rem; font-weight: 800; color: #1e293b; margin-bottom: 3px; }
    .orden-numero { display: inline-block; font-size: 0.72rem; font-weight: 700; background: #eff6ff; color: #3b82f6; padding: 2px 10px; border-radius: 999px; margin-bottom: 6px; }
    .orden-servicio-badge { display: inline-block; font-size: 0.78rem; font-weight: 700; padding: 2px 10px; border-radius: 999px; margin-left: 4px; }
    .badge-lavar { background: #dbeafe; color: #1d4ed8; }
    .badge-secar { background: #fce7f3; color: #be185d; }
    .badge-personalizado { background: #ede9fe; color: #6d28d9; }
    .orden-meta { font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }
    .maquina-label { font-size: 0.72rem; color: #94a3b8; font-weight: 600; text-align: right; margin-bottom: 6px; }
    .maquinas-row { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .btn-maquina {
        border: none; border-radius: 10px; padding: 9px 16px;
        font-size: 0.82rem; font-weight: 700; cursor: pointer;
        transition: all 0.18s; white-space: nowrap;
    }
    .btn-iniciar { background: #16a34a; color: white; }
    .btn-iniciar:hover { background: #15803d; transform: translateY(-1px); }
    .btn-finalizar { background: #0284c7; color: white; }
    .btn-finalizar:hover { background: #0369a1; }
    .btn-pausar { background: #dc2626; color: white; }
    .btn-pausar:hover { background: #b91c1c; }
    .btn-disabled { background: #cbd5e1; color: #94a3b8; cursor: not-allowed; }
    .empty-state { text-align: center; padding: 40px 0; color: #94a3b8; }
    .empty-state .icon { font-size: 2.8rem; margin-bottom: 10px; }
    .empty-state p { font-size: 0.95rem; font-weight: 500; }
    /* Kanban */
    .kanban-board { display: flex; gap: 16px; overflow-x: auto; padding-bottom: 16px; min-height: 500px; margin: 0 auto; }
    .kanban-col {
        background: #f8fafc; border-radius: 14px; border: 1px solid #e2e8f0;
        padding: 14px; min-width: 220px; flex: 1; display: flex; flex-direction: column; gap: 10px;
    }
    .kanban-col-title {
        font-size: 0.82rem; font-weight: 800; text-transform: uppercase;
        letter-spacing: 0.07em; padding-bottom: 10px; border-bottom: 2px solid #e2e8f0;
        margin-bottom: 4px;
    }
    .kanban-card {
        background: white; border-radius: 12px; padding: 14px 16px;
        border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        cursor: pointer; transition: all 0.2s;
    }
    .kanban-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); transform: translateY(-2px); }
    .kanban-card-nombre { font-weight: 800; font-size: 1rem; color: #1e293b; }
    .kanban-card-meta { font-size: 0.75rem; color: #94a3b8; margin-top: 4px; }
    .kanban-card-notas { font-size: 0.8rem; color: #475569; margin-top: 6px; background: #f1f5f9; border-radius: 6px; padding: 4px 8px; }
    /* Dashboard cards */
    .dash-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 28px; max-width: 700px; margin: 60px auto; }
    .dash-card {
        background: white; border-radius: 20px; border: 2px solid #e2e8f0;
        padding: 40px 32px; text-align: center; cursor: pointer;
        transition: all 0.25s; box-shadow: 0 4px 16px rgba(0,0,0,0.06);
    }
    .dash-card:hover { transform: translateY(-6px); box-shadow: 0 16px 40px rgba(0,0,0,0.12); border-color: #3b82f6; }
    .dash-card-icon { font-size: 3.5rem; margin-bottom: 14px; }
    .dash-card-title { font-size: 1.25rem; font-weight: 800; color: #1e293b; }
    .dash-card-sub { font-size: 0.85rem; color: #94a3b8; margin-top: 6px; }
    /* Login */
    .login-wrap {
        min-height: 100vh; display: flex; align-items: center; justify-content: center;
        background: linear-gradient(135deg, #f0f9ff 0%, #e0e7ff 100%);
    }
    .login-card {
        background: white; border-radius: 24px; padding: 48px 40px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.12); width: 380px;
    }
    .login-title { font-size: 1.6rem; font-weight: 800; color: #1e293b; margin-bottom: 6px; }
    .login-sub { font-size: 0.9rem; color: #64748b; margin-bottom: 32px; }
    /* User chip */
    .user-chip {
        display: flex; align-items: center; gap: 8px;
        background: #f1f5f9; border-radius: 999px; padding: 6px 14px;
        font-size: 0.82rem; font-weight: 700; color: #475569; cursor: pointer;
    }
    .user-chip:hover { background: #e2e8f0; }
</style>
"""


# ── Helpers de autenticación ───────────────────────────────────────────────────
def esta_autenticado() -> bool:
    return app.storage.user.get("authenticated", False)


def usuario_actual() -> str:
    return app.storage.user.get("usuario", "")


def redirigir_si_no_autenticado():
    if not esta_autenticado():
        ui.navigate.to("/admin")
        return True
    return False


# ──────────────────────────────────────────────
#  VISTA CLIENTE   /
# ──────────────────────────────────────────────
@ui.page("/")
def kiosko_cliente():
    ui.add_head_html(FONTS_HTML + KIOSKO_CSS)

    ui.add_head_html("""
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
    """)

    @ui.refreshable
    def kiosko_ui():
        with ui.element("div").props("id=kiosko-root"):
            # ══ SIDEBAR ══
            with ui.element("div").props("id=sidebar"):
                ui.html('<div class="sidebar-title">Progreso</div>')
                for i, paso in enumerate(PASOS):
                    if i < state.paso_actual:
                        cls, num = "paso-item completado", "✓"
                    elif i == state.paso_actual:
                        cls, num = "paso-item activo", str(i + 1)
                    else:
                        cls, num = "paso-item", str(i + 1)
                    ui.html(
                        f'<div class="{cls}"><span class="num">{num}</span>{paso}</div>'
                    )

            # ══ COLUMNA DERECHA ══
            with ui.element("div").props("id=main-col"):
                # ── HEADER ──
                with ui.element("div").props("id=header"):
                    with ui.element("div").classes("logo-area"):
                        ui.image("/media/logo_slogan.png").style(
                            "width:50px;height:50px;object-fit:contain;"
                        )
                        ui.html('<span class="titulo">Lavandería EcoLuna</span>')
                    ui.html(
                        '<div class="reloj" id="reloj-txt">--/--/----<br>--:--:--</div>'
                    )

                # ── CONTENIDO ──
                with ui.element("div").props("id=content"):
                    # Teclado de monedas (modo test/simulación)
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
                                on_moneda_ingresada(val)
                            except Exception as ex:
                                print(f"Error: {ex}")

                        ui.keyboard(on_key=handle_keyboard)

                    # ══════════════════════════════════════
                    #  PASO 0 — SELECCIÓN DE SERVICIO
                    # ══════════════════════════════════════
                    if state.paso_actual == 0:
                        if state.mostrando_sub_lavar:
                            # ── Sub-menú: tipo de Lavado ──
                            ui.html(
                                '<p class="instruccion">Selecciona el tipo de servicio de <strong>Lavado</strong></p>'
                            )
                            with ui.element("div").style(
                                "display:flex; gap:18px; flex-wrap:wrap; justify-content:center;"
                            ):
                                # Autolavado
                                auto = SERVICIOS_AUTO[0]  # Autolavado
                                with (
                                    ui.element("div")
                                    .classes("card-servicio")
                                    .on(
                                        "click",
                                        lambda: state.seleccionar_servicio(
                                            "Autolavado"
                                        ),
                                    )
                                ):
                                    ui.html(
                                        f'<img src="/media/washing-clothes_dark.png" style="width:80px;height:80px;">'
                                    )
                                    ui.html(
                                        '<span style="font-size:1.15rem;font-weight:800;color:#e2e8f0;">Autolavado</span>'
                                    )
                                    ui.html(
                                        f'<span style="font-size:1.7rem;font-weight:800;color:#3b82f6;">${auto.precio}</span>'
                                    )
                                    ui.html(
                                        '<span style="font-size:0.78rem;color:#64748b;">Insertas monedas tú mismo</span>'
                                    )

                                # Personalizado: 2 opciones
                                for svc in SERVICIOS_PERSONALIZADO:
                                    with (
                                        ui.element("div")
                                        .classes("card-servicio card-personalizado")
                                        .on(
                                            "click",
                                            lambda s=svc.nombre: (
                                                state.seleccionar_servicio(s)
                                            ),
                                        )
                                    ):
                                        ui.image(svc.icono).style(
                                            "width:64px;height:64px;object-fit:contain;"
                                        )
                                        ui.html(
                                            f'<span style="font-size:0.95rem;font-weight:800;color:#e2e8f0;">{svc.subtipo.capitalize()}</span>'
                                        )
                                        ui.html(
                                            '<span style="font-size:1.0rem;font-weight:700;color:#a78bfa;">Personalizado</span>'
                                        )
                                        ui.html(
                                            f'<span style="font-size:1.5rem;font-weight:800;color:#a78bfa;">${svc.precio}</span>'
                                        )
                                        ui.html(
                                            '<span style="font-size:0.78rem;color:#94a3b8;">Pagar en mostrador</span>'
                                        )

                            ui.button(
                                "← Volver",
                                on_click=lambda: (
                                    setattr(state, "mostrando_sub_lavar", False),
                                    kiosko_ui.refresh(),
                                ),
                            ).classes(
                                "btn-confirmar-nombre max-w-xs mx-auto mt-6"
                            ).style("background:#334155;")

                        else:
                            # ── Menú principal ──
                            ui.html(
                                '<p class="instruccion">Selecciona el servicio que deseas utilizar</p>'
                            )
                            with ui.element("div").style(
                                "display:flex; gap:28px; justify-content:center;"
                            ):
                                # Lavado (abre sub-menú)
                                lav = SERVICIOS_AUTO[0]
                                with (
                                    ui.element("div")
                                    .classes("card-servicio")
                                    .on(
                                        "click",
                                        lambda: (
                                            setattr(state, "mostrando_sub_lavar", True),
                                            kiosko_ui.refresh(),
                                        ),
                                    )
                                ):
                                    ui.html(
                                        '<img src="/media/washing-clothes_dark.png" style="width:100px;height:100px;">'
                                    )
                                    ui.html(
                                        '<span style="font-size:1.25rem;font-weight:700;color:#e2e8f0;">Lavar</span>'
                                    )
                                    ui.html(
                                        f'<span style="font-size:1.2rem;font-weight:800;color:#3b82f6;">Ver opciones</span>'
                                    )
                                # Secado
                                secar = SERVICIOS_AUTO[1]
                                with (
                                    ui.element("div")
                                    .classes("card-servicio")
                                    .on(
                                        "click",
                                        lambda: state.seleccionar_servicio("Secado"),
                                    )
                                ):
                                    ui.html(
                                        '<img src="/media/drying_dark.png" style="width:100px;height:100px;">'
                                    )
                                    ui.html(
                                        f'<span style="font-size:1.25rem;font-weight:700;color:#e2e8f0;">{secar.nombre}</span>'
                                    )
                                    ui.html(
                                        f'<span style="font-size:1.9rem;font-weight:800;color:#3b82f6;">${secar.precio}</span>'
                                    )

                    # ══════════════════════════════
                    #  PASO 1 — INGRESAR NOMBRE
                    # ══════════════════════════════
                    elif state.paso_actual == 1:
                        state.nombre_cliente = ""
                        with (
                            ui.element("div")
                            .props("id=nombre-panel")
                            .classes("mx-auto")
                        ):
                            ui.label("Ingresa un nombre o apodo para tu orden").style(
                                "font-size:1.3rem;color:#94a3b8;margin:0 0 8px;"
                            )
                            display_nombre = (
                                ui.label("\xa0")
                                .props("id=nombre-display")
                                .style("font-size:2rem;font-weight:700;color:#FFFFFF;")
                            )

                        def presionar_tecla(tecla):
                            if tecla == "⌫":
                                state.nombre_cliente = state.nombre_cliente[:-1]
                            else:
                                if len(state.nombre_cliente) < 12:
                                    state.nombre_cliente += tecla
                            display_nombre.set_text(
                                state.nombre_cliente if state.nombre_cliente else "\xa0"
                            )

                        filas = [
                            ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
                            ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
                            ["Z", "X", "C", "V", "B", "N", "M", "⌫"],
                        ]
                        with ui.column().classes(
                            "w-full max-w-lg mx-auto items-center gap-1 mt-4 p-2 bg-slate-900 rounded-xl"
                        ):
                            for fila in filas:
                                with ui.row().classes(
                                    "w-full justify-center flex-nowrap gap-1"
                                ):
                                    for tecla in fila:
                                        color_btn = (
                                            "bg-red-900"
                                            if tecla == "⌫"
                                            else "bg-slate-700"
                                        )
                                        ui.button(
                                            tecla,
                                            on_click=lambda t=tecla: presionar_tecla(t),
                                        ).classes(
                                            f"w-10 h-14 text-xl font-bold rounded-lg {color_btn} text-white shadow-md px-1 py-1"
                                        )
                            with ui.row().classes("w-full justify-center mt-1"):
                                ui.button(
                                    "ESPACIO", on_click=lambda: presionar_tecla(" ")
                                ).classes(
                                    "w-3/4 h-14 text-xl font-bold bg-slate-700 text-white rounded-lg shadow-md px-0"
                                )

                        def ir_a_pesar():
                            if state.nombre_cliente.strip() == "":
                                ui.notify(
                                    "Por favor, ingresa al menos una letra.",
                                    type="warning",
                                    position="top",
                                )
                                return
                            state.paso_actual = 2
                            kiosko_ui.refresh()

                        ui.button("Continuar", on_click=ir_a_pesar).classes(
                            "btn-confirmar-nombre max-w-lg mx-auto mt-4"
                        )

                    # ══════════════════════════════
                    #  PASO 2 — PESAR ROPA
                    # ══════════════════════════════
                    elif state.paso_actual == 2:
                        state.peso_ingresado = 0.0
                        peso_buffer = {"val": "0"}
                        max_kg = state.get_limite_kg()

                        with (
                            ui.element("div")
                            .props("id=nombre-panel")
                            .classes("mx-auto")
                        ):
                            with ui.element("div").style(
                                "display:flex;align-items:center;gap:10px;margin-bottom:6px;"
                            ):
                                ui.image("/media/icons/scale.svg").style(
                                    "width:32px;height:32px;object-fit:contain;"
                                )
                                ui.label("Ingresa el peso de tu ropa").style(
                                    "font-size:1.5rem;font-weight:800;color:#e2e8f0;margin:0;"
                                )
                            ui.label(
                                "Pesa tu ropa en la báscula e ingresa el valor (kg)."
                            ).style(
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
                                if d == "⌫":
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
                                state.peso_ingresado = (
                                    float(v) if v not in ("", ".") else 0.0
                                )
                                display_peso.set_text(f"{v} kg")

                            with (
                                ui.element("div")
                                .classes("numpad mx-auto mt-2")
                                .style("max-width:280px;")
                            ):
                                for d in [
                                    "7",
                                    "8",
                                    "9",
                                    "4",
                                    "5",
                                    "6",
                                    "1",
                                    "2",
                                    "3",
                                    ".",
                                    "0",
                                    "⌫",
                                ]:
                                    color = (
                                        "bg-red-900"
                                        if d == "⌫"
                                        else (
                                            "bg-slate-600"
                                            if d == "."
                                            else "bg-slate-700"
                                        )
                                    )
                                    ui.button(
                                        d, on_click=lambda x=d: presionar_num(x)
                                    ).classes(
                                        f"numpad-btn {color} text-white font-bold"
                                    )

                            def ir_a_pago_desde_peso():
                                if state.peso_ingresado <= 0:
                                    ui.notify(
                                        "Por favor ingresa un peso válido mayor a 0.",
                                        type="warning",
                                    )
                                    return
                                # BLOQUEO: si el peso excede la capacidad de la(s) máquina(s),
                                # no se permite continuar. Se limpia el peso y se notifica.
                                if max_kg and state.peso_ingresado > max_kg:
                                    ui.notify(
                                        f"Retire peso de carga que no exceda los {max_kg} kg "
                                        f"y divida su carga solicitando más servicios.",
                                        type="negative",
                                        position="top",
                                        timeout=10000,
                                    )
                                    state.peso_ingresado = 0.0
                                    peso_buffer["val"] = "0"
                                    display_peso.set_text("0 kg")
                                    return
                                # Si es personalizado, salta el paso de pago
                                if (
                                    state.servicio_seleccionado
                                    and state.servicio_seleccionado.modalidad
                                    == "personalizado"
                                ):
                                    asyncio.create_task(
                                        finalizar_servicio_personalizado()
                                    )
                                else:
                                    state.paso_actual = 3
                                    kiosko_ui.refresh()

                            ui.button(
                                "Continuar", on_click=ir_a_pago_desde_peso
                            ).classes("btn-confirmar-nombre max-w-sm mx-auto mt-4")

                    # ══════════════════════════════
                    #  PASO 3 — PAGO (solo autoservicio)
                    # ══════════════════════════════
                    elif state.paso_actual == 3:
                        pct = (
                            min(
                                100,
                                int(
                                    state.dinero_ingresado
                                    / state.servicio_seleccionado.precio
                                    * 100
                                ),
                            )
                            if state.servicio_seleccionado
                            and state.servicio_seleccionado.precio > 0
                            else 100
                        )
                        faltante = state.get_faltante()

                        if (
                            state.dinero_ingresado > state.servicio_seleccionado.precio
                            and not state.alerta_excedente_mostrada
                        ):
                            ui.notify(
                                "Has ingresado más dinero del necesario.",
                                type="warning",
                                position="top",
                                timeout=8000,
                            )
                            state.alerta_excedente_mostrada = True

                        with ui.element("div").props("id=pago-panel"):
                            ui.html(
                                f'<p style="font-size:0.88rem;color:#94a3b8;margin:0 0 2px;font-weight:600;">Cliente</p>'
                            )
                            ui.html(
                                f'<p style="font-size:1.3rem;font-weight:800;color:#e2e8f0;margin:0 0 4px;">{state.nombre_cliente}</p>'
                            )
                            ui.html(
                                f'<p style="font-size:0.82rem;color:#64748b;margin:0 0 2px;">Servicio: <strong style="color:#93c5fd;">{state.servicio_seleccionado.nombre}</strong></p>'
                            )
                            ui.html(
                                f'<p style="font-size:0.82rem;color:#64748b;margin:0 0 10px;">Peso: <strong style="color:#93c5fd;">{state.peso_ingresado} kg</strong></p>'
                            )

                            with ui.element("div").classes("monto-box"):
                                ui.html(
                                    '<div class="monto-label">Falta por insertar</div>'
                                )
                                ui.html(f'<div class="monto-valor">${faltante}</div>')
                                ui.html(
                                    f'<div class="monto-sub">Ingresado ${state.dinero_ingresado} de ${state.servicio_seleccionado.precio}</div>'
                                )

                            ui.html(
                                f'<div class="progress-bar-bg"><div class="progress-bar-fill" style="width:{pct}%;"></div></div>'
                            )
                            ui.html(
                                f'<div class="progress-pct">{pct}% completado — inserte monedas en el dispensador</div>'
                            )

                            btn_confirmar = ui.button("✓ Confirmar y Registrar Pago")
                            if state.puede_pagar():
                                btn_confirmar.on("click", finalizar_pago)
                                btn_confirmar.style(
                                    "width:100%; margin-top:16px; padding:14px; font-size:1.1rem; font-weight:700; cursor:pointer;"
                                )
                            else:
                                btn_confirmar.disable()
                                btn_confirmar.style(
                                    "width:100%; margin-top:16px; padding:14px; background:#1e293b; color:#475569; border-radius:11px; font-size:1.1rem; font-weight:700; cursor:not-allowed;"
                                )

                            async def confirmar_cancelacion():
                                if state.dinero_ingresado > 0:
                                    with ui.dialog() as dialog, ui.card():
                                        ui.label("Advertencia").style(
                                            "font-size:1.25rem;font-weight:bold;color:#ef4444;margin-bottom:8px;"
                                        )
                                        ui.label(
                                            "Tienes saldo ingresado. ¿Deseas cancelar? Deberías reclamarlo en mostrador."
                                        ).style("color:#64748b;white-space:normal;")
                                        with ui.row().style(
                                            "width:100%;justify-content:flex-end;margin-top:16px;gap:8px;"
                                        ):
                                            ui.button(
                                                "No, continuar", on_click=dialog.close
                                            )
                                            ui.button(
                                                "Sí, cancelar",
                                                on_click=lambda: (
                                                    dialog.close(),
                                                    state.reset(),
                                                ),
                                                color="red",
                                            )
                                    dialog.open()
                                else:
                                    state.reset()

                            btn_cancelar = ui.button(
                                "✕ Cancelar y regresar", color="red"
                            ).classes("btn-cancelar")
                            btn_cancelar.on("click", confirmar_cancelacion)

                    # ══════════════════════════════
                    #  PASO 4 — ÉXITO
                    # ══════════════════════════════
                    elif state.paso_actual == 4:
                        cambio = state.get_cambio()
                        es_personalizado = (
                            state.servicio_seleccionado
                            and state.servicio_seleccionado.modalidad == "personalizado"
                        )
                        cambio_html = (
                            f'<div class="cambio-box">'
                            f'<img src="/media/icons/money-bag.svg" style="width:20px;height:20px;vertical-align:middle;margin-right:6px;">'
                            f"Su cambio: ${cambio}</div>"
                            if cambio > 0
                            else ""
                        )
                        subtitulo = (
                            "Tu orden ha sido registrada. Dirígete al mostrador."
                            if es_personalizado
                            else "Dirígete a la máquina asignada."
                        )
                        precio_label = "Precio" if es_personalizado else "Pagado"
                        precio_valor = (
                            f'${state.servicio_seleccionado.precio} <span style="font-size:0.78rem;color:#a78bfa;font-weight:600;">(pagará en mostrador)</span>'
                            if es_personalizado
                            else f"${state.servicio_seleccionado.precio if state.servicio_seleccionado else 0}"
                        )
                        ui.html(f"""
                            <div id="exito-panel">
                                <div class="exito-icono">✅</div>
                                <div class="exito-titulo">¡Orden Registrada!</div>
                                <div class="exito-subtitulo">{subtitulo}</div>
                                <div class="exito-datos">
                                    <div class="exito-dato-row">
                                        <span class="exito-dato-label">Orden #</span>
                                        <span class="exito-dato-val">{state.ultimo_id_transaccion}</span>
                                    </div>
                                    <div class="exito-dato-row">
                                        <span class="exito-dato-label">Cliente</span>
                                        <span class="exito-dato-val">{state.nombre_cliente}</span>
                                    </div>
                                    <div class="exito-dato-row">
                                        <span class="exito-dato-label">Servicio</span>
                                        <span class="exito-dato-val">{state.servicio_seleccionado.nombre if state.servicio_seleccionado else ""}</span>
                                    </div>
                                    <div class="exito-dato-row">
                                        <span class="exito-dato-label">Peso</span>
                                        <span class="exito-dato-val">{state.peso_ingresado} kg</span>
                                    </div>
                                    <div class="exito-dato-row">
                                        <span class="exito-dato-label">{precio_label}</span>
                                        <span class="exito-dato-val">{precio_valor}</span>
                                    </div>
                                </div>
                                {cambio_html}
                                <div class="reinicio-txt">El sistema se reiniciará automáticamente en breve...</div>
                            </div>
                        """)

    state.set_callback(kiosko_ui.refresh)
    kiosko_ui()


async def finalizar_pago():
    """Autoservicio: registra en BD, notifica admin y espera 7s."""
    nuevo_id = await database_web.registrar_venta_async(
        servicio=state.servicio_seleccionado.nombre,
        monto=state.servicio_seleccionado.precio,
        ingresado=state.dinero_ingresado,
        cambio=state.get_cambio(),
        equipo="N/A",
        duracion=state.servicio_seleccionado.duracion_min,
        nombre_cliente=state.nombre_cliente,
        peso_kg=state.peso_ingresado,
        modalidad="autoservicio",
    )
    state.procesar_exito(nuevo_id)
    notificar_admin()
    await asyncio.sleep(7)
    state.reset()


async def finalizar_servicio_personalizado():
    """Personalizado: registra con precio del servicio (pagado en mostrador), notifica admin y espera 7s."""
    nuevo_id = await database_web.registrar_venta_async(
        servicio=state.servicio_seleccionado.nombre,
        monto=state.servicio_seleccionado.precio,
        ingresado=0,
        cambio=0,
        equipo="N/A",
        duracion=state.servicio_seleccionado.duracion_min,
        nombre_cliente=state.nombre_cliente,
        peso_kg=state.peso_ingresado,
        modalidad="personalizado",
    )
    state.procesar_exito(nuevo_id)
    notificar_admin()
    await asyncio.sleep(7)
    state.reset()


# ──────────────────────────────────────────────────────────────────────────────
#  ADMIN LOGIN   /admin/login
# ──────────────────────────────────────────────────────────────────────────────
@ui.page("/admin/login")
def admin_login():
    ui.add_head_html(FONTS_HTML + ADMIN_CSS)
    with ui.element("div").classes("login-wrap"):
        with ui.element("div").classes("login-card"):
            ui.image("/media/logo_slogan.png").style(
                "width:70px;height:70px;object-fit:contain;margin:0 auto 16px;display:block;"
            )
            ui.html('<div class="login-title">Panel EcoLuna</div>')
            ui.html('<div class="login-sub">Accede con tu cuenta de operador</div>')

            user_input = (
                ui.input("Usuario").props("outlined dense").classes("w-full mb-3")
            )
            pass_input = (
                ui.input("Contraseña")
                .props("outlined dense type=password")
                .classes("w-full mb-5")
            )

            def intentar_login():
                u = user_input.value.strip()
                p = pass_input.value.strip()
                if u in USUARIOS and USUARIOS[u] == p:
                    app.storage.user["authenticated"] = True
                    app.storage.user["usuario"] = u
                    ui.navigate.to("/admin")
                else:
                    ui.notify("Usuario o contraseña incorrectos.", type="negative")
                    pass_input.value = ""

            ui.button("Ingresar", on_click=intentar_login).props(
                "color=primary"
            ).classes("w-full text-lg font-bold py-3")


# ──────────────────────────────────────────────────────────────────────────────
#  ADMIN DASHBOARD   /admin
# ──────────────────────────────────────────────────────────────────────────────
@ui.page("/admin")
async def admin_dashboard():
    if not esta_autenticado():
        ui.navigate.to("/admin/login")
        return

    ui.add_head_html(FONTS_HTML + ADMIN_CSS)

    # Header
    with ui.element("div").props("id=admin-header"):
        with ui.element("div").props("id=admin-header-inner"):
            with ui.element("div").classes("logo-area"):
                ui.image("/media/logo_slogan.png")
                with ui.element("div"):
                    ui.html('<div class="admin-title">Panel de Administración</div>')
                    ui.html('<div class="admin-subtitle">Lavandería EcoLuna</div>')
            _render_user_chip()

    with ui.element("div").props("id=admin-content"):
        ui.html(
            '<h2 style="font-size:1.5rem;font-weight:800;color:#1e293b;margin-bottom:6px;display:flex;align-items:center;gap:10px;">'
            '<img src="/media/icons/wave.svg" style="width:32px;height:32px;">'
            "Bienvenido</h2>"
        )
        ui.html(
            f'<p style="color:#64748b;margin-bottom:32px;">Selecciona el módulo de trabajo, <strong>{usuario_actual()}</strong>.</p>'
        )

        with ui.element("div").classes("dash-grid"):
            with (
                ui.element("div")
                .classes("dash-card")
                .on("click", lambda: ui.navigate.to("/admin/autoservicio"))
            ):
                with ui.element("div").classes("dash-card-icon"):
                    ui.image("/media/icons/leaf.svg").style(
                        "width:64px;height:64px;object-fit:contain;"
                    )
                ui.html('<div class="dash-card-title">Lavado de Autoservicio</div>')
                ui.html(
                    '<div class="dash-card-sub">Asignar máquinas y gestionar pedidos del kiosko</div>'
                )

            with (
                ui.element("div")
                .classes("dash-card")
                .on("click", lambda: ui.navigate.to("/admin/personalizado"))
            ):
                with ui.element("div").classes("dash-card-icon"):
                    ui.image("/media/icons/shirt.svg").style(
                        "width:64px;height:64px;object-fit:contain;"
                    )
                ui.html('<div class="dash-card-title">Servicio Personalizado</div>')
                ui.html(
                    '<div class="dash-card-sub">Tablero kanban de lavado, secado y doblado</div>'
                )

        def cerrar_sesion():
            app.storage.user["authenticated"] = False
            app.storage.user["usuario"] = ""
            ui.navigate.to("/admin/login")

        ui.button("Cerrar sesión", on_click=cerrar_sesion).props(
            "flat color=negative"
        ).classes("mt-8")


# ──────────────────────────────────────────────────────────────────────────────
#  PANEL AUTOSERVICIO   /admin/autoservicio
# ──────────────────────────────────────────────────────────────────────────────
@ui.page("/admin/autoservicio")
async def admin_autoservicio():
    if redirigir_si_no_autenticado():
        return

    ui.add_head_html(FONTS_HTML + ADMIN_CSS)

    # ── Bypass Dialog ──
    async def ejecutar_bypass():
        pwd = input_bypass_pwd.value
        if pwd == os.getenv("BYPASS_PASSWORD", "admin123"):
            nuevo_id = await database_web.registrar_venta_async(
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
    with ui.dialog() as dialogo_cambio_usuario, ui.card().style("min-width:320px;"):
        ui.label("Cambiar operador en turno").classes(
            "text-lg font-bold text-slate-800 mb-2"
        )
        sel_usuario = ui.select(
            list(USUARIOS.keys()), label="Selecciona usuario", value=usuario_actual()
        ).classes("w-full")
        input_cambio_pwd = (
            ui.input("Contraseña").props("type=password").classes("w-full mt-3 mb-4")
        )

        def confirmar_cambio_usuario():
            u = sel_usuario.value
            p = input_cambio_pwd.value
            if u in USUARIOS and USUARIOS[u] == p:
                app.storage.user["usuario"] = u
                ui.notify(f"Sesión cambiada a {u}", type="positive")
                dialogo_cambio_usuario.close()
                input_cambio_pwd.value = ""
                ui.navigate.to("/admin/autoservicio")
            else:
                ui.notify("Contraseña incorrecta", type="negative")

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancelar", on_click=dialogo_cambio_usuario.close).props("flat")
            ui.button("Confirmar", on_click=confirmar_cambio_usuario).props(
                "color=primary"
            )

    # ── Header ──
    with ui.element("div").props("id=admin-header"):
        with ui.element("div").props("id=admin-header-inner"):
            with ui.element("div").classes("logo-area"):
                ui.image("/media/logo_slogan.png")
                with ui.element("div"):
                    ui.html(
                        '<div class="admin-title" style="display:flex;align-items:center;gap:8px;">'
                        '<img src="/media/icons/leaf.svg" style="width:28px;height:28px;">'
                        "Autoservicio</div>"
                    )
                    ui.html('<div class="admin-subtitle">Lavandería EcoLuna</div>')
            with ui.element("div").style("display:flex;align-items:center;gap:12px;"):
                ui.button(
                    "Cortesía / Bypass",
                    on_click=dialogo_bypass.open,
                ).props(
                    "icon=img:/media/icons/ticket.svg outline color=primary size=sm"
                ).classes("font-bold")
                ui.button(
                    "← Dashboard", on_click=lambda: ui.navigate.to("/admin")
                ).props("flat size=sm")
                _render_user_chip(dialogo_cambio_usuario)

    import nicegui as _ng

    page_client = _ng.context.client
    _admin_clients[page_client.id] = page_client
    page_client.on_disconnect(lambda c=page_client: _admin_clients.pop(c.id, None))

    @ui.refreshable
    async def vista_ordenes():
        with ui.element("div").props("id=admin-content").style("width:100%;"):
            ventas = await database_web.obtener_ventas_activas_async()
            pendientes = [v for v in ventas if v["estado"] == "Pendiente"]
            en_proceso = [v for v in ventas if v["estado"] == "En proceso"]

            # ─ Pendientes ─
            ui.html(
                f"""
                <div class="seccion-header">
                    <img src="/media/icons/circle-yellow.svg" style="width:18px;height:18px;vertical-align:middle;margin-right:6px;">
                    Órdenes Pendientes
                    <span class="badge badge-pendiente">{len(pendientes)}</span>
                </div>
            """
            )
            if not pendientes:
                ui.html(
                    '<div class="empty-state">'
                    '<img src="/media/icons/box.svg" style="width:48px;height:48px;opacity:0.5;">'
                    "<p>No hay órdenes pendientes</p></div>"
                )
            else:
                for v in pendientes:
                    _render_auto_pendiente(v, en_proceso)

            # ─ En Proceso ─
            ui.html(f"""
                <div class="seccion-header" style="margin-top:30px;">
                    <img src="/media/icons/circle-orange.svg" style="width:18px;height:18px;vertical-align:middle;margin-right:6px;">
                    En Proceso
                    <span class="badge badge-en-proceso">{len(en_proceso)}</span>
                </div>
            """)
            if not en_proceso:
                ui.html(
                    '<div class="empty-state">'
                    '<img src="/media/icons/sleep.svg" style="width:48px;height:48px;opacity:0.5;">'
                    "<p>Ninguna máquina en uso</p></div>"
                )
            else:
                for v in en_proceso:
                    _render_auto_en_proceso(v, vista_ordenes)

    def _badge_servicio(tipo):
        cls = (
            "badge-lavar" if "Lavar" in tipo or "Autolavado" in tipo else "badge-secar"
        )
        return f'<span class="orden-servicio-badge {cls}">{tipo}</span>'

    def _render_auto_pendiente(v, en_proceso):
        nombre = v.get("nombre_cliente") or "Sin nombre"
        peso = v.get("peso_kg", 0) or 0
        with ui.element("div").classes("orden-card"):
            with ui.element("div").style("flex:1;min-width:0;"):
                ui.html(
                    f'<div class="orden-numero">Orden #{v["id_transaccion"]}</div>{_badge_servicio(v["tipo_servicio"])}'
                )
                ui.html(f'<div class="orden-nombre">{nombre}</div>')
                ui.html(
                    f'<div class="orden-meta">{v["fecha_hora"]} · {peso} kg · Pagado: <strong>${v["monto_pagado"]}</strong></div>'
                )
            with ui.element("div").style("flex-shrink:0;"):
                ui.html('<div class="maquina-label">Asignar a:</div>')
                with ui.element("div").classes("maquinas-row"):
                    for equipo_id, equipo in hardware.EQUIPOS.items():
                        en_uso = any(
                            p["id_equipo"] == equipo["nombre"] for p in en_proceso
                        )
                        supera = peso > equipo["capacidad_kg"]
                        if en_uso:
                            with (
                                ui.element("div")
                                .classes("btn-maquina btn-disabled")
                                .style(
                                    "display:inline-flex;align-items:center;gap:6px;"
                                )
                            ):
                                ui.image("/media/icons/gear.svg").style(
                                    "width:16px;height:16px;"
                                )
                                ui.html(f"{equipo['nombre']} (En uso)")
                        elif supera:
                            with (
                                ui.element("div")
                                .classes("btn-maquina btn-disabled")
                                .style(
                                    "display:inline-flex;align-items:center;gap:6px;"
                                )
                                .tooltip(
                                    f"Supera capacidad: {peso}kg > {equipo['capacidad_kg']}kg"
                                )
                            ):
                                ui.image("/media/icons/warning.svg").style(
                                    "width:16px;height:16px;"
                                )
                                ui.html(
                                    f"{equipo['nombre']} ({equipo['capacidad_kg']}kg max)"
                                )
                        else:
                            with (
                                ui.element("div")
                                .classes("btn-maquina btn-iniciar")
                                .style(
                                    "display:inline-flex;align-items:center;gap:6px;cursor:pointer;"
                                )
                                .on(
                                    "click",
                                    lambda e, venta=v, eid=equipo_id, en=equipo["nombre"]: (
                                        asyncio.create_task(
                                            iniciar_maquina(
                                                venta, en, eid, vista_ordenes
                                            )
                                        )
                                    ),
                                )
                            ):
                                ui.image("/media/icons/gear.svg").style(
                                    "width:16px;height:16px;filter:brightness(0) invert(1);"
                                )
                                ui.html(f"{equipo['nombre']}")

    def _render_auto_en_proceso(v, ref_ordenes):
        nombre = v.get("nombre_cliente") or "Sin nombre"
        minutos_txt = ""
        if v.get("inicio_servicio"):
            try:
                from datetime import datetime as dt

                inicio = dt.strptime(v["inicio_servicio"], "%Y-%m-%d %H:%M:%S")
                mins = int((dt.now() - inicio).total_seconds() / 60)
                minutos_txt = f" · ⏱ {mins} min"
            except Exception:
                pass

        with ui.element("div").classes("orden-card en-proceso"):
            with ui.element("div").style("flex:1;min-width:0;"):
                ui.html(
                    f'<div class="orden-numero">Orden #{v["id_transaccion"]}</div>{_badge_servicio(v["tipo_servicio"])} '
                    f'<span style="font-size:0.78rem;color:#b45309;font-weight:700;display:inline-flex;align-items:center;gap:4px;">'
                    f'<img src="/media/icons/gear.svg" style="width:14px;height:14px;"> {v["id_equipo"]}</span>'
                )
                ui.html(f'<div class="orden-nombre">{nombre}</div>')
                ui.html(
                    f'<div class="orden-meta">{v["fecha_hora"]}{minutos_txt} · Pagado: <strong>${v["monto_pagado"]}</strong></div>'
                )
            with ui.element("div").style(
                "flex-shrink:0;display:flex;flex-direction:column;gap:8px;align-items:flex-end;"
            ):
                ui.label("✅ Finalizar").classes("btn-maquina btn-finalizar").on(
                    "click",
                    lambda e, venta=v: asyncio.create_task(
                        finalizar_orden(venta, ref_ordenes)
                    ),
                )
                ui.label("⏸ Cancelar").classes("btn-maquina btn-pausar").on(
                    "click",
                    lambda e, venta=v: asyncio.create_task(
                        cancelar_orden(venta, ref_ordenes)
                    ),
                )

    async def iniciar_maquina(venta, nombre_maquina, equipo_id, ref):
        await hardware.activar_lavadora(equipo_id)
        await database_web.marcar_en_proceso_async(
            venta["id_transaccion"], nombre_maquina
        )
        with page_client:
            ui.notify(
                f"▶ {nombre_maquina} iniciada — {venta.get('nombre_cliente', 'Orden')} #{venta['id_transaccion']}",
                type="positive",
                position="top",
            )
        await ref.refresh()

    async def finalizar_orden(venta, ref):
        await database_web.marcar_completado_async(
            venta["id_transaccion"], venta["id_equipo"]
        )
        with page_client:
            ui.notify(
                f"✅ Orden #{venta['id_transaccion']} completada",
                type="positive",
                position="top",
            )
        await ref.refresh()

    async def cancelar_orden(venta, ref):
        equipo_id = next(
            (
                eid
                for eid, eq in hardware.EQUIPOS.items()
                if eq["nombre"] == venta.get("id_equipo", "")
            ),
            None,
        )
        if equipo_id:
            await hardware.activar_lavadora(equipo_id)
        await database_web.marcar_completado_async(
            venta["id_transaccion"], venta["id_equipo"]
        )
        with page_client:
            ui.notify(
                f"⏸ Orden #{venta['id_transaccion']} cancelada",
                type="warning",
                position="top",
            )
        await ref.refresh()

    await vista_ordenes()
    registrar_callback_admin(vista_ordenes.refresh)
    page_client.on_disconnect(lambda: remover_callback_admin(vista_ordenes.refresh))


# ──────────────────────────────────────────────────────────────────────────────
#  PANEL PERSONALIZADO (KANBAN)   /admin/personalizado
# ──────────────────────────────────────────────────────────────────────────────
@ui.page("/admin/personalizado")
async def admin_personalizado():
    if redirigir_si_no_autenticado():
        return

    ui.add_head_html(FONTS_HTML + ADMIN_CSS)

    # ── Cambio de usuario Dialog ──
    with ui.dialog() as dialogo_cambio_usuario_p, ui.card().style("min-width:320px;"):
        ui.label("Cambiar operador en turno").classes(
            "text-lg font-bold text-slate-800 mb-2"
        )
        sel_usuario_p = ui.select(
            list(USUARIOS.keys()), label="Selecciona usuario", value=usuario_actual()
        ).classes("w-full")
        input_cambio_pwd_p = (
            ui.input("Contraseña").props("type=password").classes("w-full mt-3 mb-4")
        )

        def confirmar_cambio_usuario_p():
            u = sel_usuario_p.value
            p = input_cambio_pwd_p.value
            if u in USUARIOS and USUARIOS[u] == p:
                app.storage.user["usuario"] = u
                ui.notify(f"Sesión cambiada a {u}", type="positive")
                dialogo_cambio_usuario_p.close()
                input_cambio_pwd_p.value = ""
            else:
                ui.notify("Contraseña incorrecta", type="negative")

        with ui.row().classes("w-full justify-end"):
            ui.button("Cancelar", on_click=dialogo_cambio_usuario_p.close).props("flat")
            ui.button("Confirmar", on_click=confirmar_cambio_usuario_p).props(
                "color=primary"
            )

    # ── Header ──
    with ui.element("div").props("id=admin-header"):
        with ui.element("div").props("id=admin-header-inner"):
            with ui.element("div").classes("logo-area"):
                ui.image("/media/logo_slogan.png")
                with ui.element("div"):
                    ui.html(
                        '<div class="admin-title" style="display:flex;align-items:center;gap:8px;">'
                        '<img src="/media/icons/shirt.svg" style="width:28px;height:28px;">'
                        "Servicio Personalizado</div>"
                    )
                    ui.html('<div class="admin-subtitle">Lavandería EcoLuna</div>')
            with ui.element("div").style("display:flex;align-items:center;gap:12px;"):
                ui.button(
                    "← Dashboard", on_click=lambda: ui.navigate.to("/admin")
                ).props("flat size=sm")
                _render_user_chip(dialogo_cambio_usuario_p)

    import nicegui as _ng_p

    page_client_p = _ng_p.context.client
    _admin_clients[page_client_p.id] = page_client_p
    page_client_p.on_disconnect(lambda c=page_client_p: _admin_clients.pop(c.id, None))

    @ui.refreshable
    async def vista_kanban():
        with ui.element("div").props("id=admin-content").style("width:100%;"):
            ordenes = await database_web.obtener_ordenes_personalizadas_async()

            ETAPAS_INFO = [
                ("Recibido", "/media/icons/inbox.svg", "#eff6ff", "#3b82f6"),
                ("En Proceso", "/media/icons/gear.svg", "#fff7ed", "#f59e0b"),
                ("Alistando", "/media/icons/basket.svg", "#f0fdf4", "#22c55e"),
                ("Listo para Entrega", "/media/icons/box.svg", "#fdf4ff", "#a855f7"),
                ("Entregado", "/media/icons/box.svg", "#f0fdf4", "#16a34a"),
            ]

            with ui.element("div").classes("kanban-board"):
                for etapa_nombre, icono_path, bg, color in ETAPAS_INFO:
                    cards_etapa = [
                        o for o in ordenes if o.get("etapa_kanban") == etapa_nombre
                    ]
                    with (
                        ui.element("div")
                        .classes("kanban-col")
                        .style(f"background:{bg};")
                    ):
                        with (
                            ui.element("div")
                            .classes("kanban-col-title")
                            .style(
                                f"color:{color};display:flex;align-items:center;gap:6px;"
                            )
                        ):
                            ui.image(icono_path).style(
                                "width:18px;height:18px;object-fit:contain;"
                            )
                            ui.html(
                                f'{etapa_nombre} <span style="font-weight:500;font-size:0.8rem;opacity:0.6;">({len(cards_etapa)})</span>'
                            )
                        for orden in cards_etapa:
                            _render_kanban_card(orden, etapa_nombre, vista_kanban)

    def _render_kanban_card(orden, etapa_actual, ref):
        from database_web import ETAPAS_KANBAN

        nombre = orden.get("nombre_cliente") or "Sin nombre"
        peso = orden.get("peso_kg", 0) or 0
        notas = orden.get("notas") or ""
        servicio = orden.get("tipo_servicio", "")

        with ui.element("div").classes("kanban-card"):
            ui.html(f'<div class="kanban-card-nombre">{nombre}</div>')
            ui.html(
                f'<div class="kanban-card-meta">#{orden["id_transaccion"]} · {servicio} · {peso} kg</div>'
            )
            ui.html(f'<div class="kanban-card-meta">{orden["fecha_hora"]}</div>')
            if notas:
                ui.html(
                    f'<div class="kanban-card-notas" style="display:flex;align-items:flex-start;gap:6px;">'
                    f'<img src="/media/icons/notes.svg" style="width:14px;height:14px;margin-top:2px;">'
                    f"<span>{notas}</span></div>"
                )

            # Acciones
            with ui.row().classes("gap-1 mt-2 flex-wrap"):
                idx_actual = (
                    ETAPAS_KANBAN.index(etapa_actual)
                    if etapa_actual in ETAPAS_KANBAN
                    else 0
                )

                # Avanzar etapa
                if idx_actual < len(ETAPAS_KANBAN) - 1:
                    siguiente = ETAPAS_KANBAN[idx_actual + 1]

                    # Si se avanza a "En Proceso", pedir máquina
                    if siguiente == "En Proceso":

                        async def abrir_asignar_maquina(o=orden, ref=ref):
                            equipo_disponibles = {
                                eid: eq
                                for eid, eq in hardware.EQUIPOS.items()
                                if (o.get("peso_kg") or 0) <= eq["capacidad_kg"]
                            }
                            with page_client_p:
                                with (
                                    ui.dialog() as d_asignar,
                                    ui.card().style("min-width:320px;"),
                                ):
                                    ui.label("Asignar máquina").classes(
                                        "text-lg font-bold mb-2"
                                    )
                                    opts = {
                                        eq["nombre"]: eid
                                        for eid, eq in equipo_disponibles.items()
                                    }
                                    sel_eq = ui.select(
                                        list(opts.keys()), label="Máquina"
                                    ).classes("w-full")
                                    with ui.row().classes("w-full justify-end mt-3"):
                                        ui.button(
                                            "Cancelar", on_click=d_asignar.close
                                        ).props("flat")

                                        async def confirmar_asignar():
                                            eid = opts.get(sel_eq.value)
                                            await hardware.activar_lavadora(eid)
                                            await database_web.actualizar_etapa_kanban_async(
                                                o["id_transaccion"],
                                                "En Proceso",
                                                equipo_id=sel_eq.value,
                                            )
                                            with page_client_p:
                                                d_asignar.close()
                                            await ref.refresh()

                                        ui.button(
                                            "Iniciar", on_click=confirmar_asignar
                                        ).props("color=green")
                                    d_asignar.open()

                        ui.button(
                            f"→ {siguiente}", on_click=abrir_asignar_maquina
                        ).props("size=xs color=primary outline").classes("text-xs")
                    else:

                        async def avanzar(o=orden, sig=siguiente, ref=ref):
                            await database_web.actualizar_etapa_kanban_async(
                                o["id_transaccion"], sig
                            )
                            await ref.refresh()

                        ui.button(f"→ {siguiente}", on_click=avanzar).props(
                            "size=xs color=primary outline"
                        ).classes("text-xs")

                # Notas
                async def abrir_notas(o=orden, ref=ref):
                    with page_client_p:
                        with (
                            ui.dialog() as d_notas,
                            ui.card().style("min-width:360px;"),
                        ):
                            ui.label(
                                f"Notas — {o.get('nombre_cliente')} #{o['id_transaccion']}"
                            ).classes("font-bold mb-2")
                            txt = (
                                ui.textarea("Notas", value=o.get("notas") or "")
                                .classes("w-full")
                                .style("min-height:120px;")
                            )
                            with ui.row().classes("w-full justify-end mt-2"):
                                ui.button("Cancelar", on_click=d_notas.close).props(
                                    "flat"
                                )

                                async def guardar_notas():
                                    await database_web.actualizar_notas_async(
                                        o["id_transaccion"], txt.value
                                    )
                                    with page_client_p:
                                        d_notas.close()
                                    await ref.refresh()

                                ui.button("Guardar", on_click=guardar_notas).props(
                                    "color=primary"
                                )
                            d_notas.open()

                ui.button("Notas", on_click=abrir_notas).props(
                    "icon=img:/media/icons/notes.svg size=xs flat"
                ).classes("text-xs")

    await vista_kanban()
    registrar_callback_admin(vista_kanban.refresh)
    page_client_p.on_disconnect(lambda: remover_callback_admin(vista_kanban.refresh))


# ── Shared UI ──────────────────────────────────────────────────────────────────
def _render_user_chip(dialogo_cambio=None):
    u = usuario_actual()
    if dialogo_cambio:
        with ui.element("div").classes("user-chip").on("click", dialogo_cambio.open):
            ui.html(
                f'<img src="/media/icons/user.svg" style="width:16px;height:16px;vertical-align:middle;margin-right:4px;">'
                f'{u} <span style="opacity:0.5;margin-left:4px;">▼</span>'
            )
    else:
        with ui.element("div").classes("user-chip"):
            ui.html(
                f'<img src="/media/icons/user.svg" style="width:16px;height:16px;vertical-align:middle;margin-right:4px;">'
                f"{u}"
            )


# ──────────────────────────────────────────────────────────────────────────────
app.on_shutdown(hardware.limpiar_pines)

if __name__ in {"__main__", "__mp_main__"}:
    try:
        ui.run(
            title="EcoLuna Kiosko",
            port=8000,
            favicon="../media/logo_slogan.png",
            reload=False,
            show=False,
            storage_secret="ecoluna_kiosko_secret_2025",
        )
    except KeyboardInterrupt:
        print("\nStop app by KeyboardInterrupt.\n")
