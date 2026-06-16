from nicegui import ui, app, Client
import asyncio
from models import (
    KioskoState,
    SERVICIOS_AUTO,
    SERVICIOS_PERSONALIZADO,
    PASOS,
    get_limite_kg,
)
from metodos_pago import (
    MetodoPago,
    MetodoMonedas,
    METODOS_PAGO_DISPONIBLES,
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
_kiosko_clients: dict = {}
_kiosko_ui_ref = None


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


state.notificar_admin = notificar_admin


def registrar_kiosko_client(client):
    _kiosko_clients[client.id] = client


def remover_kiosko_client(client):
    _kiosko_clients.pop(client.id, None)


def notificar_kiosko(mensaje: str = "", tipo: str = "positive"):
    """Envía una notificación y refresca todos los kioskos conectados."""
    if _kiosko_ui_ref:
        try:
            _kiosko_ui_ref()
        except Exception:
            pass
    if mensaje:
        for client in list(_kiosko_clients.values()):
            try:
                with client:
                    ui.notify(mensaje, type=tipo, position="top")
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


async def _recuperar_maquinas_sostenidas():
    """Tras un apagón, verifica si hay máquinas en modo sostenido que deban apagarse.
    Marca como completadas las órdenes cuyo tiempo máximo ya haya expirado.
    """
    try:
        ordenes = await database_web.obtener_ordenes_en_proceso_async()
        from datetime import datetime as dt

        ahora = dt.now()
        for orden in ordenes:
            equipo_id = next(
                (
                    eid
                    for eid, eq in hardware.EQUIPOS.items()
                    if eq["nombre"] == orden.get("id_equipo", "")
                ),
                None,
            )
            if not equipo_id:
                continue
            eq = hardware.EQUIPOS[equipo_id]
            if eq.get("modo") != "sostenido":
                continue

            # En personalizado no hay límite fijo; usamos duracion_estimada_min si existe.
            # En autoservicio mantenemos el límite de seguridad 25/40 min.
            es_personalizado = "personalizado" in (orden.get("modalidad") or "")
            if es_personalizado and orden.get("duracion_estimada_min"):
                duracion_max = orden["duracion_estimada_min"]
            else:
                duracion_max = 40 if eq["tipo"] == "secado" else 25

            inicio_str = orden.get("inicio_servicio")
            if inicio_str:
                try:
                    inicio = dt.strptime(inicio_str, "%Y-%m-%d %H:%M:%S")
                    minutos_transcurridos = (ahora - inicio).total_seconds() / 60
                    if minutos_transcurridos >= duracion_max:
                        print(
                            f"[startup] Orden {orden['id_transaccion']} en {eq['nombre']} "
                            f"excedió {duracion_max}min tras apagón. Marcando como completada."
                        )
                        await database_web.marcar_completado_async(
                            orden["id_transaccion"], orden.get("id_equipo", "")
                        )
                    else:
                        # Reprogramar auto-apagado con el tiempo restante
                        restante_min = duracion_max - minutos_transcurridos
                        print(
                            f"[startup] Reprogramando auto-apagado de {eq['nombre']} "
                            f"para orden {orden['id_transaccion']} (restante: {restante_min:.1f}min)"
                        )
                        await hardware.reprogramar_auto_apagado(
                            equipo_id, eq["gpio"], restante_min
                        )
                except Exception as e:
                    print(f"[startup] Error parseando inicio_servicio: {e}")
    except Exception as e:
        print(f"[startup] Error recuperando máquinas sostenidas: {e}")


app.on_startup(_recuperar_maquinas_sostenidas)

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
                    #  PASO 2 — PESAR ROPA / SELECCIÓN DE MÉTODO
                    # ══════════════════════════════
                    elif state.paso_actual == 2:
                        if state.esperando_aprobacion_admin:
                            # ── Sub-estado: esperando aprobación del administrador ──
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
                                "← Regresar",
                                on_click=lambda: asyncio.create_task(
                                    _kiosko_regresar_espera()
                                ),
                            ).classes(
                                "btn-confirmar-nombre max-w-xs mx-auto mt-6"
                            ).style("background:#334155;")
                        elif state.mostrando_metodos_pago:
                            # ── Sub-estado: mostrar métodos de pago ──
                            ui.html('<p class="instruccion">¿Cómo deseas pagar?</p>')
                            es_personalizado = (
                                state.servicio_seleccionado
                                and state.servicio_seleccionado.modalidad
                                == "personalizado"
                            )
                            with ui.element("div").style(
                                "display:flex; gap:24px; flex-wrap:wrap; justify-content:center;"
                            ):
                                for metodo_cls in METODOS_PAGO_DISPONIBLES:
                                    # Los personalizados no pagan con monedas
                                    if (
                                        es_personalizado
                                        and metodo_cls.codigo == "monedas"
                                    ):
                                        continue
                                    with (
                                        ui.element("div")
                                        .classes("card-servicio")
                                        .on(
                                            "click",
                                            lambda cls=metodo_cls: (
                                                seleccionar_metodo_pago(cls)
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

                            # Para servicios personalizados, ofrecer también la opción de pagar en mostrador
                            if es_personalizado:
                                ui.button(
                                    "Pagar en mostrador al recibir",
                                    on_click=lambda: asyncio.create_task(
                                        finalizar_servicio_personalizado()
                                    ),
                                ).classes(
                                    "btn-confirmar-nombre max-w-sm mx-auto mt-4"
                                ).style("background:#a78bfa;")

                            async def _cancelar_desde_metodos_pago():
                                await _eliminar_orden_activa_si_existe(
                                    state.ultimo_id_transaccion
                                )
                                state.ultimo_id_transaccion = None
                                state.reset()
                                notificar_admin()

                            ui.button(
                                "✕ Cancelar orden",
                                on_click=lambda: asyncio.create_task(
                                    _cancelar_desde_metodos_pago()
                                ),
                            ).classes(
                                "btn-confirmar-nombre max-w-xs mx-auto mt-6"
                            ).style("background:#991b1b;color:#fecaca;")
                        else:
                            # ── Estado principal: ingreso de peso ──
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

                                display_peso = ui.label("0 kg").classes(
                                    "numpad-display"
                                )

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

                                async def enviar_peso_a_revision():
                                    if state.peso_ingresado <= 0:
                                        ui.notify(
                                            "Por favor ingresa un peso válido mayor a 0.",
                                            type="warning",
                                        )
                                        return
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

                    # ══════════════════════════════
                    #  PASO 3 — PAGO (delegado al método seleccionado)
                    # ══════════════════════════════
                    elif state.paso_actual == 3:
                        if not state.metodo_pago_instancia:
                            state.metodo_pago_instancia = MetodoMonedas(state)
                            state.metodo_pago_codigo = "monedas"

                        async def _on_cancelar():
                            async def _confirmar_cancelacion():
                                await _eliminar_orden_activa_si_existe(
                                    state.ultimo_id_transaccion
                                )
                                state.ultimo_id_transaccion = None
                                if state.metodo_pago_instancia is not None and hasattr(
                                    state.metodo_pago_instancia, "cancelar"
                                ):
                                    await state.metodo_pago_instancia.cancelar()
                                state.reset()
                                if _kiosko_ui_ref:
                                    _kiosko_ui_ref()
                                notificar_admin()

                            if (
                                state.metodo_pago_codigo == "monedas"
                                and state.dinero_ingresado > 0
                            ):
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
                                                asyncio.create_task(
                                                    _confirmar_cancelacion()
                                                ),
                                            ),
                                            color="red",
                                        )
                                dialog.open()
                                return
                            await _confirmar_cancelacion()

                        async def _on_pago_exitoso():
                            await finalizar_pago()

                        state.metodo_pago_instancia.render_panel(
                            on_cancelar=_on_cancelar,
                            on_pago_exitoso=_on_pago_exitoso,
                        )

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
                                <div class="exito-icono"><img src="/media/icons/check.svg" style="width:64px;height:64px;display:block;margin:0 auto;" onerror="this.style.display='none'"></div>
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
    global _kiosko_ui_ref
    _kiosko_ui_ref = kiosko_ui.refresh
    # Renderizar la UI inicialmente
    kiosko_ui()
    # Registrar el Client del kiosko para notificaciones desde el admin
    import nicegui as _ng

    _kiosko_client = _ng.context.client
    registrar_kiosko_client(_kiosko_client)
    _kiosko_client.on_disconnect(lambda c=_kiosko_client: remover_kiosko_client(c))


async def _eliminar_orden_activa_si_existe(id_transaccion):
    """Borra una orden activa si está en un estado cancelable (peso/pago pendiente)."""
    if not id_transaccion:
        return
    conn = database_web._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM transacciones WHERE id_transaccion = ? AND estado IN ('Pendiente-peso', 'Procesando-pago', 'Pendiente-pago')",
        (id_transaccion,),
    )
    conn.commit()
    conn.close()


async def _kiosko_regresar_espera():
    """El cliente pulsa 'Regresar' desde la pantalla de espera admin.
    Borra la incurrencia correspondiente y devuelve al paso anterior."""
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
        # No limpiamos ultimo_id_transaccion: permite reintentar terminal/monedas
        # (el fallback creará un nuevo registro si el anterior ya no existe)
        state.mostrando_metodos_pago = True
        state.limpiar_espera_admin()
        notificar_admin()


async def finalizar_pago():
    """Registra el pago en la orden 'Pendiente' existente (peso ya aprobado).
    Si no existe, crea un registro nuevo. Notifica admin y espera 7s."""
    metodo = state.metodo_pago_codigo or "monedas"
    es_pers = state.servicio_seleccionado.modalidad == "personalizado"
    modalidad = f"personalizado-{metodo}" if es_pers else f"autoservicio-{metodo}"
    print(
        f"[main] finalizar_pago: cliente={state.nombre_cliente} "
        f"servicio={state.servicio_seleccionado.nombre} metodo={metodo} modalidad={modalidad}"
    )
    ingresado = (
        state.dinero_ingresado
        if metodo == "monedas"
        else state.servicio_seleccionado.precio
    )
    cambio = state.get_cambio() if metodo == "monedas" else 0
    nuevo_id = await database_web.guardar_pago_orden_async(
        state.ultimo_id_transaccion,
        metodo,
        state.servicio_seleccionado.precio,
        ingresado,
        cambio,
        modalidad,
    )
    if nuevo_id is None:
        # Fallback: crear registro nuevo si no había orden Pendiente previa
        nuevo_id = await database_web.registrar_venta_async(
            servicio=state.servicio_seleccionado.nombre,
            monto=state.servicio_seleccionado.precio,
            ingresado=ingresado,
            cambio=cambio,
            equipo="N/A",
            duracion=state.servicio_seleccionado.duracion_min,
            nombre_cliente=state.nombre_cliente,
            peso_kg=state.peso_ingresado,
            modalidad=modalidad,
        )
    state.procesar_exito(nuevo_id)
    notificar_admin()
    await asyncio.sleep(7)
    state.reset()


async def seleccionar_metodo_pago(metodo_cls):
    """Inicializa el método de pago seleccionado y avanza al paso 3."""
    state.metodo_pago_instancia = metodo_cls(state)
    state.metodo_pago_codigo = metodo_cls.codigo
    state.paso_actual = 3
    if _kiosko_ui_ref:
        _kiosko_ui_ref()


async def finalizar_servicio_personalizado():
    """Personalizado: el cliente elige pagar en efectivo en mostrador.
    La orden pasa a 'Pendiente-pago' a espera de que el operador confirme
    el pago recibido."""
    print(
        f"[main] finalizar_servicio_personalizado: cliente={state.nombre_cliente} "
        f"servicio={state.servicio_seleccionado.nombre} esperando_pago_mostrador"
    )
    if state.ultimo_id_transaccion is None:
        ui.notify(
            "No hay una orden activa. Vuelve a ingresar el peso.", type="negative"
        )
        return
    id_orden = await database_web.marcar_pendiente_pago_async(
        state.ultimo_id_transaccion,
        state.servicio_seleccionado.precio,
        modalidad="personalizado-pendiente-pago",
    )
    if id_orden is None:
        # Fallback: crear registro nuevo si no se pudo actualizar
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
            esperando_peso = [v for v in ventas if v["estado"] == "Pendiente-peso"]
            procesando_pago = [
                v
                for v in ventas
                if v["estado"] in ("Procesando-pago", "Pendiente-pago")
            ]
            pendientes = [v for v in ventas if v["estado"] == "Pendiente"]
            en_proceso = [v for v in ventas if v["estado"] == "En proceso"]

            def _render_seccion(icon, titulo, badge_cls, items, render_fn):
                ui.html(
                    f"""
                    <div class="seccion-header">
                        <img src="/media/icons/{icon}.svg" style="width:18px;height:18px;vertical-align:middle;margin-right:6px;">
                        {titulo}
                        <span class="badge {badge_cls}">{len(items)}</span>
                    </div>
                """
                )
                if not items:
                    ui.html(
                        '<div class="empty-state">'
                        '<img src="/media/icons/sleep.svg" style="width:48px;height:48px;opacity:0.5;">'
                        f"<p>Sin órdenes en esta sección</p></div>"
                    )
                else:
                    for v in items:
                        render_fn(v)

            # ─ Esperando validación de peso ─
            _render_seccion(
                "scale",
                "Esperando validación de peso",
                "badge-pendiente",
                esperando_peso,
                _render_esperando_peso,
            )

            # ─ Procesando pago (monedas en kiosko / terminal) ─
            _render_seccion(
                "ticket",
                "Procesando pago",
                "badge-en-proceso",
                procesando_pago,
                _render_procesando_pago,
            )

            # ─ Pendientes ─
            _render_seccion(
                "circle-yellow",
                "Órdenes Pendientes",
                "badge-pendiente",
                pendientes,
                lambda v: _render_auto_pendiente(v, en_proceso),
            )

            # ─ En Proceso ─
            _render_seccion(
                "circle-orange",
                "En Proceso",
                "badge-en-proceso",
                en_proceso,
                lambda v: _render_auto_en_proceso(v, vista_ordenes),
            )

    def _badge_servicio(tipo):
        cls = (
            "badge-lavar" if "Lavar" in tipo or "Autolavado" in tipo else "badge-secar"
        )
        return f'<span class="orden-servicio-badge {cls}">{tipo}</span>'

    def _badge_metodo_pago(modalidad):
        """Devuelve un pequeño badge con el método de pago usado."""
        if not modalidad:
            return ""
        m = modalidad
        if "terminal" in m:
            color_bg, color_fg = "#fce7f3", "#be185d"
            label = "Terminal"
        elif "monedas" in m:
            color_bg, color_fg = "#d1fae5", "#065f46"
            label = "Efectivo"
        elif "pendiente-pago" in m or "mostrador" in m:
            color_bg, color_fg = "#dcfce7", "#166534"
            label = "Efectivo mostrador"
        else:
            color_bg, color_fg = "#e2e8f0", "#475569"
            label = "Otro"
        return f'<span class="orden-servicio-badge" style="background:{color_bg};color:{color_fg};">{label}</span>'

    def _render_esperando_peso(v):
        nombre = v.get("nombre_cliente") or "Sin nombre"
        peso = v.get("peso_kg", 0) or 0
        with (
            ui.element("div")
            .classes("orden-card")
            .style("border-left:4px solid #a855f7;")
        ):
            with ui.element("div").style("flex:1;min-width:0;"):
                ui.html(
                    f'<div class="orden-numero">Orden #{v["id_transaccion"]}</div>'
                    f"{_badge_servicio(v['tipo_servicio'])} "
                    f'<span class="orden-servicio-badge" style="background:#f3e8ff;color:#7e22ce;">Validar peso</span>'
                )
                ui.html(f'<div class="orden-nombre">{nombre}</div>')
                ui.html(
                    f'<div class="orden-meta">{v["fecha_hora"]} · Peso registrado: <strong>{peso} kg</strong></div>'
                )
            with ui.element("div").style(
                "flex-shrink:0;display:flex;flex-direction:column;gap:8px;align-items:flex-end;"
            ):
                ui.label("✓ Aprobar").classes("btn-maquina btn-iniciar").on(
                    "click",
                    lambda e, venta=v: asyncio.create_task(
                        aprobar_peso(venta, vista_ordenes)
                    ),
                )
                ui.label("✕ Rechazar").classes("btn-maquina btn-pausar").on(
                    "click",
                    lambda e, venta=v: asyncio.create_task(
                        rechazar_peso(venta, vista_ordenes)
                    ),
                )

    def _render_procesando_pago(v):
        nombre = v.get("nombre_cliente") or "Sin nombre"
        peso = v.get("peso_kg", 0) or 0
        monto = v.get("monto_pagado", 0) or 0
        modalidad = v.get("modalidad", "")
        es_pago_pendiente = v["estado"] == "Pendiente-pago"
        if "pendiente-pago" in modalidad or "mostrador" in modalidad:
            label = "Efectivo mostrador"
            color = "#16a34a"
        elif "terminal" in modalidad:
            label = "Terminal"
            color = "#f59e0b"
        else:
            label = "En pago"
            color = "#3b82f6"
        folio_input = None
        with (
            ui.element("div")
            .classes("orden-card")
            .style(f"border-left:4px solid {color};")
        ):
            with ui.element("div").style("flex:1;min-width:0;"):
                ui.html(
                    f'<div class="orden-numero">Orden #{v["id_transaccion"]}</div>'
                    f"{_badge_servicio(v['tipo_servicio'])} "
                    f'<span class="orden-servicio-badge" style="background:{color}22;color:{color};">{label}</span> '
                    f"{_badge_metodo_pago(modalidad)}"
                )
                ui.html(f'<div class="orden-nombre">{nombre}</div>')
                ui.html(
                    f'<div class="orden-meta">{v["fecha_hora"]} · {peso} kg · Monto: <strong>${monto}</strong></div>'
                )
                if es_pago_pendiente:
                    folio_input = (
                        ui.input("Folio de transacción (opcional)")
                        .props("outlined dense")
                        .classes("mb-2")
                    )
                    folio_input
            with ui.element("div").style(
                "flex-shrink:0;display:flex;flex-direction:column;gap:8px;align-items:flex-end;"
            ):
                if es_pago_pendiente:
                    ui.label("✓ Confirmar pago").classes("btn-maquina btn-iniciar").on(
                        "click",
                        lambda e, venta=v, inp=folio_input: asyncio.create_task(
                            confirmar_folio(venta, inp, vista_ordenes)
                        ),
                    )
                    ui.label("✕ Cancelar").classes("btn-maquina btn-pausar").on(
                        "click",
                        lambda e, venta=v: asyncio.create_task(
                            cancelar_pago_pendiente(venta, vista_ordenes)
                        ),
                    )

    def _render_auto_pendiente(v, en_proceso):
        nombre = v.get("nombre_cliente") or "Sin nombre"
        peso = v.get("peso_kg", 0) or 0
        modalidad = v.get("modalidad", "")
        with ui.element("div").classes("orden-card"):
            with ui.element("div").style("flex:1;min-width:0;"):
                ui.html(
                    f'<div class="orden-numero">Orden #{v["id_transaccion"]}</div>'
                    f"{_badge_servicio(v['tipo_servicio'])} "
                    f"{_badge_metodo_pago(modalidad)}"
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

        # Detectar si la máquina asignada es de modo sostenido y está activa
        equipo_id = next(
            (
                eid
                for eid, eq in hardware.EQUIPOS.items()
                if eq["nombre"] == v.get("id_equipo", "")
            ),
            None,
        )
        es_sostenido = (
            equipo_id and hardware.EQUIPOS.get(equipo_id, {}).get("modo") == "sostenido"
        )
        seg_restantes = (
            hardware.tiempo_restante_sostenido(equipo_id) if es_sostenido else 0
        )
        timer_txt = ""
        if es_sostenido and seg_restantes > 0:
            m, s = divmod(seg_restantes, 60)
            timer_txt = f" · ⏳ {m:02d}:{s:02d}"

        modalidad = v.get("modalidad", "")
        with ui.element("div").classes("orden-card en-proceso"):
            with ui.element("div").style("flex:1;min-width:0;"):
                ui.html(
                    f'<div class="orden-numero">Orden #{v["id_transaccion"]}</div>'
                    f"{_badge_servicio(v['tipo_servicio'])} "
                    f"{_badge_metodo_pago(modalidad)} "
                    f'<span style="font-size:0.78rem;color:#b45309;font-weight:700;display:inline-flex;align-items:center;gap:4px;">'
                    f'<img src="/media/icons/gear.svg" style="width:14px;height:14px;"> {v["id_equipo"]}</span>'
                )
                ui.html(f'<div class="orden-nombre">{nombre}</div>')
                ui.html(
                    f'<div class="orden-meta">{v["fecha_hora"]}{minutos_txt}{timer_txt} · Pagado: <strong>${v["monto_pagado"]}</strong></div>'
                )
            with ui.element("div").style(
                "flex-shrink:0;display:flex;flex-direction:column;gap:8px;align-items:flex-end;"
            ):
                if es_sostenido:
                    ui.label("⏹ Detener").classes("btn-maquina btn-pausar").on(
                        "click",
                        lambda e, venta=v, eid=equipo_id: asyncio.create_task(
                            detener_maquina_sostenida(venta, eid, ref_ordenes)
                        ),
                    )
                else:
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

    async def aprobar_peso(venta, ref):
        await database_web.aprobar_peso_async(
            venta["id_transaccion"], venta.get("peso_kg", 0), usuario_actual()
        )
        state.peso_ingresado = venta.get("peso_kg", 0)
        state.mostrando_metodos_pago = True
        state.limpiar_espera_admin()
        with page_client:
            ui.notify(
                f"✓ Peso aprobado — {venta.get('nombre_cliente', 'Orden')} #{venta['id_transaccion']}",
                type="positive",
                position="top",
            )
        await ref.refresh()
        notificar_kiosko("Peso aprobado. Selecciona tu método de pago.", "positive")

    async def rechazar_peso(venta, ref):
        await database_web.rechazar_peso_async(
            venta["id_transaccion"], usuario_actual()
        )
        state.peso_ingresado = 0.0
        state.peso_en_revision = 0.0
        state.peso_rechazado_notificado = True
        state.paso_actual = 2
        state.mostrando_metodos_pago = False
        state.limpiar_espera_admin()
        with page_client:
            ui.notify(
                f"↩ Peso rechazado — {venta.get('nombre_cliente', 'Orden')} #{venta['id_transaccion']}",
                type="warning",
                position="top",
            )
        await ref.refresh()
        notificar_kiosko("El administrador pidió volver a pesar.", "warning")

    async def confirmar_folio(venta, folio_input, ref):
        folio = folio_input.value.strip()
        await database_web.aprobar_pago_terminal_async(
            venta["id_transaccion"], folio, usuario_actual()
        )
        state.limpiar_espera_admin()
        state.procesar_exito(venta["id_transaccion"])
        notificar_admin()
        with page_client:
            ui.notify(
                f"✓ Pago confirmado — Orden #{venta['id_transaccion']}",
                type="positive",
                position="top",
            )
        await ref.refresh()
        notificar_kiosko("Pago confirmado. Gracias por tu compra.", "positive")
        await asyncio.sleep(7)
        state.reset()

    async def cancelar_pago_pendiente(venta, ref):
        await database_web.cancelar_pago_pendiente_async(
            venta["id_transaccion"], usuario_actual()
        )
        state.mostrando_metodos_pago = True
        state.limpiar_espera_admin()
        with page_client:
            ui.notify(
                f"✕ Pago cancelado — Orden #{venta['id_transaccion']}",
                type="warning",
                position="top",
            )
        await ref.refresh()
        notificar_kiosko("El pago fue cancelado. Puedes intentar de nuevo.", "warning")

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

    async def detener_maquina_sostenida(venta, equipo_id, ref):
        await hardware.apagar_maquina(equipo_id)
        await database_web.marcar_completado_async(
            venta["id_transaccion"], venta["id_equipo"]
        )
        with page_client:
            ui.notify(
                f"⏹ {venta.get('id_equipo')} detenida — Orden #{venta['id_transaccion']}",
                type="warning",
                position="top",
            )
        await ref.refresh()

    async def finalizar_orden(venta, ref):
        # Apagar máquina si está en modo sostenido
        equipo_id = next(
            (
                eid
                for eid, eq in hardware.EQUIPOS.items()
                if eq["nombre"] == venta.get("id_equipo", "")
            ),
            None,
        )
        if equipo_id and hardware.EQUIPOS[equipo_id].get("modo") == "sostenido":
            await hardware.apagar_maquina(equipo_id)

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
            eq = hardware.EQUIPOS[equipo_id]
            if eq.get("modo") == "sostenido":
                # En modo sostenido, cancelar = apagar la máquina
                await hardware.apagar_maquina(equipo_id)
            else:
                # En modo pulso, mantener comportamiento anterior (pulso)
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

            # Timer para máquinas sostenidas en etapa "En Proceso"
            if etapa_actual == "En Proceso" and orden.get("id_equipo"):
                equipo_id = next(
                    (
                        eid
                        for eid, eq in hardware.EQUIPOS.items()
                        if eq["nombre"] == orden["id_equipo"]
                    ),
                    None,
                )
                if (
                    equipo_id
                    and hardware.EQUIPOS.get(equipo_id, {}).get("modo") == "sostenido"
                ):
                    seg_restantes = hardware.tiempo_restante_sostenido(equipo_id)
                    if seg_restantes > 0:
                        m, s = divmod(seg_restantes, 60)
                        ui.html(
                            f'<div style="font-size:0.8rem;color:#f59e0b;font-weight:700;margin-top:4px;display:flex;align-items:center;gap:4px;">'
                            f'<img src="/media/icons/gear.svg" style="width:14px;height:14px;">'
                            f"⏳ {m:02d}:{s:02d} restantes</div>"
                        )
                    else:
                        ui.html(
                            f'<div style="font-size:0.8rem;color:#ef4444;font-weight:700;margin-top:4px;">'
                            f"Tiempo expirado — finalice la orden</div>"
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

                    # Si se avanza a "En Proceso", ofrecer asignación opcional de máquina
                    if siguiente == "En Proceso":

                        async def abrir_iniciar_personalizado(o=orden, ref=ref):
                            peso = o.get("peso_kg") or 0
                            # En personalizado no hay límite de duración; usamos la del servicio
                            duracion_default = o.get("duracion_estimada_min") or 60

                            with page_client_p:
                                with (
                                    ui.dialog() as d,
                                    ui.card().style("min-width:420px;"),
                                ):
                                    ui.label(
                                        f"Iniciar — {o.get('nombre_cliente')} #{o['id_transaccion']}"
                                    ).classes("text-lg font-bold mb-2")

                                    # Opción A: sin máquina (equipo externo)
                                    async def iniciar_sin_maquina():
                                        await (
                                            database_web.actualizar_etapa_kanban_async(
                                                o["id_transaccion"], "En Proceso"
                                            )
                                        )
                                        d.close()
                                        await ref.refresh()
                                        with page_client_p:
                                            ui.notify(
                                                "Orden iniciada sin máquina del sistema",
                                                type="info",
                                            )

                                    ui.button(
                                        "Iniciar sin máquina (equipo externo)",
                                        on_click=iniciar_sin_maquina,
                                    ).props("flat color=grey").classes("w-full mb-2")

                                    ui.html(
                                        '<div style="border-top:1px solid #e2e8f0;margin:8px 0;"></div>'
                                    )

                                    # Opción B: con máquina del sistema
                                    ui.label("O asignar máquina del sistema:").classes(
                                        "font-semibold mb-1"
                                    )

                                    maquinas_ok = {
                                        eid: eq
                                        for eid, eq in hardware.EQUIPOS.items()
                                        if peso <= eq["capacidad_kg"]
                                    }

                                    if not maquinas_ok:
                                        ui.html(
                                            '<div style="color:#ef4444;">Ninguna máquina tiene capacidad para este peso.</div>'
                                        )
                                    else:
                                        opts_texto = {
                                            f"{eq['nombre']} ({eq['modo']}, máx {eq['capacidad_kg']}kg)": eid
                                            for eid, eq in maquinas_ok.items()
                                        }
                                        sel_maq = ui.select(
                                            list(opts_texto.keys()), label="Máquina"
                                        ).classes("w-full")

                                        sel_tiempo = ui.number(
                                            "Duración (min)",
                                            value=duracion_default,
                                            min=1,
                                            step=1,
                                        ).classes("w-full mt-2")

                                        async def iniciar_con_maquina():
                                            eid = opts_texto.get(sel_maq.value)
                                            if not eid:
                                                ui.notify(
                                                    "Selecciona una máquina",
                                                    type="warning",
                                                )
                                                return
                                            eq = hardware.EQUIPOS[eid]
                                            duracion = int(
                                                sel_tiempo.value or duracion_default
                                            )
                                            if duracion < 1:
                                                ui.notify(
                                                    "La duración debe ser mayor a 0",
                                                    type="warning",
                                                )
                                                return

                                            if hardware.equipo_sostenido_activo(eid):
                                                ui.notify(
                                                    f"{eq['nombre']} ya está en uso.",
                                                    type="warning",
                                                )
                                                return

                                            if eq.get("modo") == "sostenido":
                                                await hardware.activar_lavadora_con_duracion(
                                                    eid, duracion
                                                )
                                            else:
                                                await hardware.activar_lavadora(eid)

                                            await database_web.actualizar_etapa_kanban_async(
                                                o["id_transaccion"],
                                                "En Proceso",
                                                equipo_id=eq["nombre"],
                                            )
                                            d.close()
                                            await ref.refresh()
                                            with page_client_p:
                                                ui.notify(
                                                    f"▶ {eq['nombre']} iniciada por {duracion}min",
                                                    type="positive",
                                                )

                                        with ui.row().classes(
                                            "w-full justify-end mt-3"
                                        ):
                                            ui.button(
                                                "Cancelar", on_click=d.close
                                            ).props("flat")
                                            ui.button(
                                                "Iniciar con máquina",
                                                on_click=iniciar_con_maquina,
                                            ).props("color=green")
                            d.open()

                        ui.button(
                            f"→ {siguiente}", on_click=abrir_iniciar_personalizado
                        ).props("size=xs color=primary outline").classes("text-xs")
                    else:

                        async def avanzar(o=orden, sig=siguiente, ref=ref):
                            # Si salimos de "En Proceso" y hay máquina asignada,
                            # apagarla si es modo sostenido
                            if etapa_actual == "En Proceso" and o.get("id_equipo"):
                                equipo_id = next(
                                    (
                                        eid
                                        for eid, eq in hardware.EQUIPOS.items()
                                        if eq["nombre"] == o["id_equipo"]
                                    ),
                                    None,
                                )
                                if (
                                    equipo_id
                                    and hardware.EQUIPOS.get(equipo_id, {}).get("modo")
                                    == "sostenido"
                                ):
                                    await hardware.apagar_maquina(equipo_id)
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
