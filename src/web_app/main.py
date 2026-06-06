from nicegui import ui, app
import asyncio
from models import KioskoState, SERVICIOS, PASOS
import database
import hardware

# ──────────────────────────────────────────────
#  ESTADO GLOBAL
# ──────────────────────────────────────────────
state = KioskoState()

# Callbacks registrados por el panel admin para recibir actualizaciones reactivas
# (una por cada pestaña/conexión admin abierta)
_admin_refresh_callbacks: list = []

def registrar_callback_admin(cb):
    _admin_refresh_callbacks.append(cb)

def remover_callback_admin(cb):
    if cb in _admin_refresh_callbacks:
        _admin_refresh_callbacks.remove(cb)

def notificar_admin():
    """Llamado cuando llega una orden nueva; dispara el refresh en todos los admin conectados."""
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

# ──────────────────────────────────────────────
#  CSS COMPARTIDO
# ──────────────────────────────────────────────
FONTS_HTML = '''
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
'''

# ──────────────────────────────────────────────
#  VISTA CLIENTE   /
# ──────────────────────────────────────────────
@ui.page('/')
def kiosko_cliente():
    ui.add_head_html(FONTS_HTML + '''
        <style>
            * { box-sizing: border-box; }
            html, body {
                margin: 0; padding: 0; width: 100%; height: 100%;
                overflow: hidden; font-family: 'Inter', sans-serif;
                background: #1a1a2e; color: #e2e8f0;
            }

            /* ─── Layout principal ─── */
            #kiosko-root { display: flex; width: 100vw; height: 100vh; }

            /* ─── Sidebar de pasos ─── */
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

            /* ─── Columna derecha ─── */
            #main-col { flex: 1; display: flex; flex-direction: column; min-width: 0; }

            /* ─── Header ─── */
            #header {
                display: flex; align-items: center; justify-content: space-between;
                padding: 8px 18px; background: #16213e;
                border-bottom: 2px solid #0f3460; flex-shrink: 0;
            }
            #header .logo-area { display: flex; align-items: center; gap: 12px; }
            #header .titulo { font-size: 1.3rem; font-weight: 800; color: #e2e8f0; }
            #header .reloj { font-size: 0.82rem; color: #94a3b8; text-align: right; line-height: 1.65; }

            /* ─── Contenido ─── */
            #content {
                flex: 1; display: flex; flex-direction: column;
                align-items: center; justify-content: center;
                padding: 16px; overflow: hidden;
            }
            .instruccion {
                font-size: 1.1rem; color: #94a3b8; margin-bottom: 22px;
                text-align: center; font-weight: 500;
            }

            /* ─── Tarjetas de servicio ─── */
            .card-servicio {
                cursor: pointer; border-radius: 16px;
                background: #16213e; border: 2px solid #0f3460;
                padding: 24px 20px; width: 195px;
                display: flex; flex-direction: column; align-items: center;
                gap: 6px; transition: all 0.22s; user-select: none;
            }
            .card-servicio:hover {
                border-color: #3b82f6; background: #1e3a5f;
                transform: translateY(-4px);
                box-shadow: 0 10px 24px rgba(59,130,246,0.22);
            }
            .card-icono { font-size: 2.6rem; }
            .card-nombre { font-size: 1.25rem; font-weight: 700; color: #e2e8f0; }
            .card-precio { font-size: 1.9rem; font-weight: 800; color: #3b82f6; }

            /* ─── Panel de nombre ─── */
            #nombre-panel {
                background: #16213e; border: 2px solid #0f3460;
                border-radius: 18px; padding: 24px 28px;
                width: 100%; max-width: 480px;
                text-align: center;
            }
            #nombre-panel .nombre-display {
                font-size: 2rem; font-weight: 700; color: #60a5fa;
                min-height: 48px; margin: 10px 0;
                background: #0f172a; border-radius: 10px; padding: 8px 16px;
                letter-spacing: 0.05em; border: 1px solid #1e3a5f;
            }
            /* Teclado táctil */
            .teclado { display: grid; grid-template-columns: repeat(10, 1fr); gap: 5px; margin-top: 14px; }
            .teclado-fila { display: flex; gap: 5px; justify-content: center; margin-bottom: 5px; flex-wrap: nowrap; }
            .tecla {
                background: #1e293b; color: #e2e8f0; border: 1px solid #334155;
                border-radius: 8px; padding: 10px 0; font-size: 0.7rem; font-weight: 600;
                cursor: pointer; min-width: 34px; text-align: center;
                transition: background 0.15s; user-select: none; flex: 1;
            }
            .tecla:hover { background: #2d3f55; }
            .tecla:active { background: #3b82f6; }
            .tecla-wide { flex: 1.8; }
            .tecla-space { flex: 3.5; }
            .btn-confirmar-nombre {
                margin-top: 14px; width: 100%; padding: 13px;
                background: #3b82f6; color: #fff; border: none; border-radius: 12px;
                font-size: 1rem; font-weight: 700; cursor: pointer; transition: background 0.2s;
            }
            .btn-confirmar-nombre:hover { background: #2563eb; }
            .btn-confirmar-nombre:disabled { background: #1e3a5f; color: #475569; cursor: not-allowed; }

            /* ─── Panel de pago ─── */
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
                background: #7f1d1d; color: #fca5a5; border: none; border-radius: 11px;
                font-size: 0.95rem; font-weight: 600; cursor: pointer; transition: background 0.2s;
            }
            .btn-cancelar:hover { background: #991b1b; }

            /* ─── Pantalla de éxito ─── */
            #exito-panel { text-align: center; width: 100%; max-width: 420px; }
            .exito-icono { font-size: 4.5rem; }
            .exito-titulo { font-size: 2rem; font-weight: 800; color: #4ade80; margin: 10px 0 6px; }
            .exito-subtitulo { font-size: 1.1rem; color: #94a3b8; margin-bottom: 14px; }
            .exito-datos {
                background: #16213e; border: 1px solid #0f3460;
                border-radius: 14px; padding: 14px 20px; margin-bottom: 14px;
                text-align: left;
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

            /* ─── Simulador (solo test) ─── */
            #sim-coins {
                position: fixed; bottom: 10px; right: 10px;
                display: flex; gap: 5px; z-index: 999;
            }
        </style>
    ''')

    # Reloj dinámico JS
    ui.add_head_html('''
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
    ''')

    # Buffer del nombre en el cliente (solo para la entrada de teclado táctil)
    nombre_buffer = {'valor': ''}

    @ui.refreshable
    def kiosko_ui():
        with ui.element('div').props('id=kiosko-root'):

            # ══ SIDEBAR ══
            with ui.element('div').props('id=sidebar'):
                ui.html('<div class="sidebar-title">Progreso</div>')
                for i, paso in enumerate(PASOS):
                    if i < state.paso_actual:
                        cls, num = 'paso-item completado', '✓'
                    elif i == state.paso_actual:
                        cls, num = 'paso-item activo', str(i + 1)
                    else:
                        cls, num = 'paso-item', str(i + 1)
                    ui.html(f'<div class="{cls}"><span class="num">{num}</span>{paso}</div>')

            # ══ COLUMNA DERECHA ══
            with ui.element('div').props('id=main-col'):

                # ── HEADER ──
                with ui.element('div').props('id=header'):
                    with ui.element('div').classes('logo-area'):
                        ui.image('/media/logo_slogan.png').style('width:50px;height:50px;object-fit:contain;')
                        ui.html('<span class="titulo">Lavandería EcoLuna</span>')
                    ui.html('<div class="reloj" id="reloj-txt">--/--/----<br>--:--:--</div>')

                # ── CONTENIDO ──
                with ui.element('div').props('id=content'):

                    # Teclado simulado (modo test)
                    if not hardware.HARDWARE_AVAILABLE:
                        def handle_keyboard(e):
                            # 1. Ignorar el evento cuando se suelta la tecla (keyup)
                            if not e.action.keydown:
                                return

                            try:
                                # 2. Extraer el valor en texto de la tecla
                                tecla = e.key.name 
                                
                                # 3. Filtrar solo las teclas que nos interesan (1, 2, 5 y 0)
                                if tecla == '0':
                                    val = 10
                                elif tecla in ['1', '2', '5']:
                                    val = int(tecla)
                                else:
                                    return # Si presionan una letra u otra cosa, ignorar
                                    
                                # 4. Enviar el valor al state
                                on_moneda_ingresada(val)
                                
                            except Exception as ex:
                                # Evita que el programa se rompa si presionan teclas especiales (Shift, Ctrl)
                                print(f'Error: {ex}')
                        ui.keyboard(on_key=handle_keyboard)

                    # ══════════════════════════════
                    #  PASO 0 — SELECCIÓN SERVICIO
                    # ══════════════════════════════
                    if state.paso_actual == 0:
                        ui.html('<p class="instruccion">Selecciona el servicio que deseas utilizar</p>')
                        with ui.element('div').style('display:flex; gap:28px; justify-content:center;'):
                            for servicio in SERVICIOS:
                                icono = '🫧' if servicio.nombre == 'Lavar' else '🌬️'
                                with ui.element('div').style(
                                    'cursor:pointer; border-radius:16px; background:#16213e;'
                                    'border:2px solid #0f3460; padding:24px 20px; width:195px;'
                                    'display:flex; flex-direction:column; align-items:center;'
                                    'gap:6px; transition:all 0.22s; user-select:none;'
                                ).on('click', lambda s=servicio.nombre: state.seleccionar_servicio(s)):
                                    ui.html(f'<span style="font-size:2.6rem;">{icono}</span>')
                                    ui.html(f'<span style="font-size:1.25rem;font-weight:700;color:#e2e8f0;">{servicio.nombre}</span>')
                                    ui.html(f'<span style="font-size:1.9rem;font-weight:800;color:#3b82f6;">${servicio.precio}</span>')

                    # ══════════════════════════════
                    #  PASO 1 — INGRESAR NOMBRE
                    # ══════════════════════════════
                    elif state.paso_actual == 1:
                        
                        # Limpiamos el nombre cada vez que entran a este paso
                        state.nombre_cliente = ""

                        # --- 1. PANEL DE DISPLAY (Usando tu CSS) ---
                        with ui.element('div').props('id=nombre-panel').classes('mx-auto'):
                            ui.label('Ingresa un nombre o apodo para tu orden').style('font-size:1.3rem;color:#94a3b8;margin:0 0 8px;')
                            
                            # Este es el "monitor" que mostrará lo que tecleas. 
                            # Le ponemos el id="nombre-display" para que tome tu diseño del <head>.
                            display_nombre = ui.label('\xa0').props('id=nombre-display').style('font-size:2rem;font-weight:700;color:#FFFFFF;')

                        # --- 2. LÓGICA DEL TECLADO ---
                        def presionar_tecla(tecla):
                            if tecla == '⌫':
                                state.nombre_cliente = state.nombre_cliente[:-1] # Borra 1 letra
                            else:
                                if len(state.nombre_cliente) < 12: # Límite para que no se salga de la pantalla
                                    state.nombre_cliente += tecla
                            
                            # Actualizamos el monitor visual en tiempo real
                            display_nombre.set_text(state.nombre_cliente if state.nombre_cliente else '\xa0')

                        # --- 3. DIBUJAR EL TECLADO EN PANTALLA ---
                        filas = [
                            ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
                            ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'],
                            ['Z', 'X', 'C', 'V', 'B', 'N', 'M', '⌫']
                        ]
                        
                        # Contenedor del teclado (Usamos Tailwind para acomodarlo rápido)
                        with ui.column().classes('w-full max-w-lg mx-auto items-center gap-1 mt-4 p-2 bg-slate-900 rounded-xl'):
                            for fila in filas:
                                with ui.row().classes('w-full justify-center flex-nowrap gap-1'):
                                    for tecla in fila:
                                        color_btn = 'bg-red-900' if tecla == '⌫' else 'bg-slate-700'
                                        
                                        # Cada botón ejecuta la función presionar_tecla()
                                        ui.button(tecla, on_click=lambda t=tecla: presionar_tecla(t)) \
                                          .classes(f'w-10 h-14 text-xl font-bold rounded-lg {color_btn} text-white shadow-md px-1 py-1')
                            
                            # Barra espaciadora
                            with ui.row().classes('w-full justify-center mt-1'):
                                ui.button('ESPACIO', on_click=lambda: presionar_tecla(' ')) \
                                  .classes('w-3/4 h-14 text-xl font-bold bg-slate-700 text-white rounded-lg shadow-md px-0')

                        # --- 4. BOTÓN CONTINUAR ---
                        def ir_a_pago():
                            if state.nombre_cliente.strip() == "":
                                ui.notify('Por favor, ingresa al menos una letra.', type='warning', position='top')
                                return
                            state.paso_actual = 2
                            # Aquí debes llamar a la función que refresca tu UI principal (ej. refrescar_kiosko())
                            kiosko_ui.refresh() # ¡Reemplaza esto con tu función de refresco de pantalla!

                        ui.button('Continuar al Pago', on_click=ir_a_pago).classes('btn-confirmar-nombre max-w-lg mx-auto mt-4')

                    # ══════════════════════════════
                    #  PASO 2 — PAGO
                    # ══════════════════════════════
                    elif state.paso_actual == 2:
                        pct = min(100, int(state.dinero_ingresado / state.servicio_seleccionado.precio * 100))
                        faltante = state.get_faltante()

                        if state.dinero_ingresado > state.servicio_seleccionado.precio and not state.alerta_excedente_mostrada:
                            ui.notify("Has ingresado más dinero del necesario. Por favor, confirma el pago o cancela en la máquina para retirar el excedente y volver a intentar.", type='warning', position='top', timeout=10000, multi_line=True)
                            state.alerta_excedente_mostrada = True

                        if state.puede_pagar() and not state.en_procesamiento:
                            state.en_procesamiento = True
                            asyncio.create_task(finalizar_pago())

                        with ui.element('div').props('id=pago-panel'):
                            ui.html(f'<p style="font-size:0.88rem;color:#94a3b8;margin:0 0 2px;font-weight:600;">Cliente</p>')
                            ui.html(f'<p style="font-size:1.3rem;font-weight:800;color:#e2e8f0;margin:0 0 10px;">{state.nombre_cliente}</p>')
                            ui.html(f'<p style="font-size:0.82rem;color:#64748b;margin:0 0 2px;">Servicio: <strong style="color:#93c5fd;">{state.servicio_seleccionado.nombre}</strong></p>')
                            with ui.element('div').classes('monto-box'):
                                ui.html('<div class="monto-label">Falta por insertar</div>')
                                ui.html(f'<div class="monto-valor">${faltante}</div>')
                                ui.html(f'<div class="monto-sub">Ingresado ${state.dinero_ingresado} de ${state.servicio_seleccionado.precio}</div>')
                            ui.html(f'<div class="progress-bar-bg"><div class="progress-bar-fill" style="width:{pct}%;"></div></div>')
                            ui.html(f'<div class="progress-pct">{pct}% completado — inserte monedas en el dispensador</div>')
                            
                            async def confirmar_cancelacion():
                                if state.dinero_ingresado > 0:
                                    with ui.dialog() as dialog, ui.card():
                                        ui.label("Advertencia").style('font-size: 1.25rem; font-weight: bold; color: #ef4444; margin-bottom: 8px;')
                                        ui.label("Tienes saldo ingresado. ¿Estás seguro de que deseas cancelar? Podrías perder el dinero ingresado y deberás intentar reclamar la devolución.").style('color: #64748b; white-space: normal;')
                                        with ui.row().style('width: 100%; justify-content: flex-end; margin-top: 16px; gap: 8px;'):
                                            ui.button('No, continuar pago', on_click=dialog.close).style('background: #e2e8f0; color: #1e293b;')
                                            ui.button('Sí, regresar y cancelar', on_click=lambda: (dialog.close(), state.reset())).style('background: #ef4444; color: white;')
                                    dialog.open()
                                else:
                                    state.reset()

                            ui.label('✕ Cancelar y regresar (podrías perder saldo)').style(
                                'display:block;width:100%;margin-top:8px;padding:11px;background:#7f1d1d;'
                                'color:#fca5a5;border:none;border-radius:11px;font-size:0.95rem;'
                                'font-weight:600;cursor:pointer;text-align:center;white-space:normal;line-height:1.2;'
                            ).on('click', confirmar_cancelacion)

                        # Simulador de monedas (solo test)
                        if not hardware.HARDWARE_AVAILABLE:
                            with ui.element('div').props('id=sim-coins'):
                                for v in [1, 2, 5, 10]:
                                    ui.element('div').style(
                                        'background:#1e293b;color:#94a3b8;border:1px solid #334155;'
                                        'border-radius:8px;padding:6px 10px;font-size:0.8rem;cursor:pointer;'
                                    ).on('click', lambda val=v: lector_monedas.simular_moneda(val)).text = f'${v}'

                    # ══════════════════════════════
                    #  PASO 3 — ÉXITO
                    # ══════════════════════════════
                    elif state.paso_actual == 3:
                        cambio = state.get_cambio()
                        cambio_html = f'<div class="cambio-box">💰 Su cambio: ${cambio}</div>' if cambio > 0 else ''
                        ui.html(f'''
                            <div id="exito-panel">
                                <div class="exito-icono">✅</div>
                                <div class="exito-titulo">¡Pago Exitoso!</div>
                                <div class="exito-subtitulo">Pese su ropa al mostrador</div>
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
                                        <span class="exito-dato-val">{state.servicio_seleccionado.nombre if state.servicio_seleccionado else ''}</span>
                                    </div>
                                    <div class="exito-dato-row">
                                        <span class="exito-dato-label">Pagado</span>
                                        <span class="exito-dato-val">${state.servicio_seleccionado.precio if state.servicio_seleccionado else 0}</span>
                                    </div>
                                </div>
                                {cambio_html}
                                <div class="reinicio-txt">El sistema se reiniciará automáticamente en breve...</div>
                            </div>
                        ''')

    state.set_callback(kiosko_ui.refresh)
    app.add_static_files('/media', '../media')
    kiosko_ui()


async def finalizar_pago():
    """Registra en BD y notifica al admin de forma reactiva, sin polling."""
    nuevo_id = await database.registrar_venta_async(
        servicio=state.servicio_seleccionado.nombre,
        monto=state.servicio_seleccionado.precio,
        ingresado=state.dinero_ingresado,
        cambio=state.get_cambio(),
        equipo='N/A',
        duracion=state.servicio_seleccionado.duracion_min,
        nombre_cliente=state.nombre_cliente,
    )
    state.procesar_exito(nuevo_id)
    # Señal reactiva al panel admin → refresca solo cuando hay un nuevo pedido
    notificar_admin()
    # Mostrar pantalla de éxito 7 segundos y luego resetear
    await asyncio.sleep(7)
    state.reset()


# ──────────────────────────────────────────────
#  PANEL ADMIN   /admin
# ──────────────────────────────────────────────
@ui.page('/admin')
async def admin_panel():
    ui.add_head_html(FONTS_HTML + '''
        <style>
            * { box-sizing: border-box; }
            body { background: #f1f5f9; font-family: 'Inter', sans-serif; margin: 0; color: #1e293b; }
            .nicegui-content { max-width: none !important; padding: 0 !important; margin: 0 !important; align-items: flex-start !important; justify-content: flex-start !important; }

            /* ─── Header ─── */
            #admin-header {
                background: white; border-bottom: 2px solid #e2e8f0;
                padding: 14px 36px; position: sticky; top: 0; z-index: 10;
                box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            }
            #admin-header-inner {
                max-width: 1200px; margin: 0; width: 100%;
                display: flex; align-items: center; justify-content: space-between;
            }
            .logo-area { display: flex; align-items: center; gap: 14px; }
            .logo-area img { width: 46px; height: 46px; object-fit: contain; }
            .admin-title { font-size: 1.35rem; font-weight: 800; color: #1e293b; margin-right: 25px }
            .admin-subtitle { font-size: 0.8rem; color: #64748b; font-weight: 500; }
            #status-indicator {
                font-size: 0.82rem; color: #64748b;
                display: flex; align-items: center; gap: 8px;
            }
            .dot-live {
                width: 8px; height: 8px; border-radius: 50%; background: #22c55e;
                animation: pulse-green 2s infinite;
            }
            @keyframes pulse-green {
                0%,100% { opacity: 1; } 50% { opacity: 0.3; }
            }

            /* ─── Contenido ─── */
            #admin-content { padding: 28px 36px; max-width: 1200px; margin: 0; }

            /* ─── Sección ─── */
            .seccion-header {
                display: flex; align-items: center; gap: 10px;
                font-size: 0.9rem; font-weight: 700; color: #475569;
                text-transform: uppercase; letter-spacing: 0.07em;
                padding-bottom: 10px; margin-bottom: 16px;
                border-bottom: 2px solid #e2e8f0;
            }
            .badge {
                padding: 2px 12px; border-radius: 999px;
                font-size: 0.78rem; font-weight: 700;
            }
            .badge-pendiente { background: #fef3c7; color: #92400e; }
            .badge-en-proceso { background: #fde8d8; color: #9a3412; }

            /* ─── Tarjeta de orden ─── */
            .orden-card {
                background: white; border-radius: 14px; border: 1px solid #e2e8f0;
                padding: 18px 22px; margin-bottom: 12px;
                display: flex; align-items: center; justify-content: space-between;
                gap: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
                transition: box-shadow 0.2s;
            }
            .orden-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
            .orden-card.en-proceso { border-left: 4px solid #f59e0b; }
            .orden-nombre {
                font-size: 1.3rem; font-weight: 800; color: #1e293b; margin-bottom: 3px;
            }
            .orden-numero {
                display: inline-block; font-size: 0.72rem; font-weight: 700;
                background: #eff6ff; color: #3b82f6;
                padding: 2px 10px; border-radius: 999px; margin-bottom: 6px;
            }
            .orden-servicio-badge {
                display: inline-block; font-size: 0.78rem; font-weight: 700;
                padding: 2px 10px; border-radius: 999px; margin-left: 4px;
            }
            .badge-lavar { background: #dbeafe; color: #1d4ed8; }
            .badge-secar { background: #fce7f3; color: #be185d; }
            .orden-meta { font-size: 0.8rem; color: #94a3b8; margin-top: 4px; }
            .maquina-label { font-size: 0.72rem; color: #94a3b8; font-weight: 600; text-align: right; margin-bottom: 6px; }

            /* Botones */
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

            /* Empty state */
            .empty-state { text-align: center; padding: 40px 0; color: #94a3b8; }
            .empty-state .icon { font-size: 2.8rem; margin-bottom: 10px; }
            .empty-state p { font-size: 0.95rem; font-weight: 500; }
        </style>
    ''')

    app.add_static_files('/media', '../media')

    # ─── Header ───
    ui.html('''
        <div id="admin-header">
            <div id="admin-header-inner">
                <div class="logo-area">
                    <img src="/media/logo_slogan.png" alt="EcoLuna">
                    <div>
                        <div class="admin-title">Panel de Administración</div>
                        <div class="admin-subtitle">Lavandería EcoLuna</div>
                    </div>
                </div>
                <div id="status-indicator">
                    <span class="dot-live"></span>
                    Actualización en tiempo real
                </div>
            </div>
        </div>
    ''')

    @ui.refreshable
    async def vista_ordenes():
        with ui.element('div').props('id=admin-content').style('width:100%;'):
            ventas = await database.obtener_ventas_activas_async()
            pendientes = [v for v in ventas if v['estado'] == 'Pendiente']
            en_proceso = [v for v in ventas if v['estado'] == 'En proceso']

            # ─── PENDIENTES ───
            ui.html(f'''
                <div class="seccion-header">
                    🟡 Órdenes Pendientes
                    <span class="badge badge-pendiente">{len(pendientes)}</span>
                </div>
            ''')
            if not pendientes:
                ui.html('<div class="empty-state"><div class="icon">✅</div><p>No hay órdenes pendientes</p></div>')
            else:
                for v in pendientes:
                    _render_pendiente(v)

            # ─── EN PROCESO ───
            ui.html(f'''
                <div class="seccion-header" style="margin-top:30px;">
                    🟠 En Proceso
                    <span class="badge badge-en-proceso">{len(en_proceso)}</span>
                </div>
            ''')
            if not en_proceso:
                ui.html('<div class="empty-state"><div class="icon">💤</div><p>Ninguna máquina en uso</p></div>')
            else:
                for v in en_proceso:
                    _render_en_proceso(v)

    def _badge_servicio(tipo):
        cls = 'badge-lavar' if 'Lavar' in tipo else 'badge-secar'
        return f'<span class="orden-servicio-badge {cls}">{tipo}</span>'

    def _render_pendiente(v):
        nombre = v.get('nombre_cliente') or 'Sin nombre'
        with ui.element('div').classes('orden-card'):
            with ui.element('div').style('flex:1; min-width:0;'):
                ui.html(f'<div class="orden-numero">Orden #{v["id_transaccion"]}</div>{_badge_servicio(v["tipo_servicio"])}')
                ui.html(f'<div class="orden-nombre">{nombre}</div>')
                ui.html(f'<div class="orden-meta">{v["fecha_hora"]} · Pagado: <strong>${v["monto_pagado"]}</strong></div>')
            with ui.element('div').style('flex-shrink:0;'):
                ui.html('<div class="maquina-label">Asignar a:</div>')
                with ui.element('div').classes('maquinas-row'):
                    MAQUINAS = [
                        ('🫧 Lavadora 1', hardware.PIN_LAVADORA_1, 'Lavadora 1'),
                        ('🫧 Lavadora 2', hardware.PIN_LAVADORA_2, 'Lavadora 2'),
                        ('🫧 Lavadora 3', hardware.PIN_LAVADORA_3, 'Lavadora 3'),
                    ]
                    for label, pin, nombre_m in MAQUINAS:
                        ui.label(label).classes('btn-maquina btn-iniciar').on(
                            'click', lambda e, venta=v, n=nombre_m, p=pin: iniciar_maquina(venta, n, p)
                        )

    def _render_en_proceso(v):
        nombre = v.get('nombre_cliente') or 'Sin nombre'
        minutos_txt = ''
        if v.get('inicio_servicio'):
            try:
                from datetime import datetime as dt
                inicio = dt.strptime(v['inicio_servicio'], "%Y-%m-%d %H:%M:%S")
                mins = int((dt.now() - inicio).total_seconds() / 60)
                minutos_txt = f' · ⏱ {mins} min en proceso'
            except Exception:
                pass

        with ui.element('div').classes('orden-card en-proceso'):
            with ui.element('div').style('flex:1; min-width:0;'):
                ui.html(f'<div class="orden-numero">Orden #{v["id_transaccion"]}</div>{_badge_servicio(v["tipo_servicio"])}<span style="font-size:0.78rem;color:#b45309;font-weight:700;margin-left:6px;">⚙️ {v["id_equipo"]}</span>')
                ui.html(f'<div class="orden-nombre">{nombre}</div>')
                ui.html(f'<div class="orden-meta">{v["fecha_hora"]}{minutos_txt} · Pagado: <strong>${v["monto_pagado"]}</strong></div>')
            with ui.element('div').style('flex-shrink:0; display:flex; flex-direction:column; gap:8px; align-items:flex-end;'):
                ui.label('✅ Finalizar').classes('btn-maquina btn-finalizar').on(
                    'click', lambda e, venta=v: finalizar_orden(venta)
                )
                ui.label('⏸ Pausar / Cancelar').classes('btn-maquina btn-pausar').on(
                    'click', lambda e, venta=v: cancelar_orden(venta)
                )

    async def iniciar_maquina(venta, nombre_maquina, pin):
        await hardware.activar_lavadora(pin)
        await database.marcar_en_proceso_async(venta['id_transaccion'], nombre_maquina)
        ui.notify(f'▶ {nombre_maquina} iniciada — {venta.get("nombre_cliente","Orden")} #{venta["id_transaccion"]}',
                  type='positive', position='top', progress=True)
        await vista_ordenes.refresh()

    async def finalizar_orden(venta):
        await database.marcar_completado_async(venta['id_transaccion'], venta['id_equipo'])
        ui.notify(f'✅ Orden #{venta["id_transaccion"]} completada', type='positive', position='top')
        await vista_ordenes.refresh()

    async def cancelar_orden(venta):
        pin_map = {
            'Lavadora 1': hardware.PIN_LAVADORA_1,
            'Lavadora 2': hardware.PIN_LAVADORA_2,
            'Lavadora 3': hardware.PIN_LAVADORA_3,
        }
        pin = pin_map.get(venta.get('id_equipo', ''), hardware.PIN_LAVADORA_1)
        await hardware.activar_lavadora(pin)
        await database.marcar_completado_async(venta['id_transaccion'], venta['id_equipo'])
        ui.notify(f'⏸ Orden #{venta["id_transaccion"]} pausada y cancelada', type='warning', position='top')
        await vista_ordenes.refresh()

    # Registrar callback reactivo: se llama cuando llega una nueva orden desde el kiosko
    await vista_ordenes()
    registrar_callback_admin(vista_ordenes.refresh)

    # Limpiar el callback cuando la conexión se cierre
    app.on_disconnect(lambda: remover_callback_admin(vista_ordenes.refresh))


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title='Lavandería EcoLuna', port=8080, dark=False, favicon='🫧',
           storage_secret='ecoluna-secret-2024')
