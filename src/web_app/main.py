from nicegui import ui
import asyncio
from models import KioskoState, SERVICIOS
import database
import hardware

# --- Configuración Global ---
state = KioskoState()

# Callback de hardware
def on_moneda_ingresada(valor):
    if state.servicio_seleccionado and not state.exito:
        state.ingresar_dinero(valor)

lector_monedas = hardware.LectorMonedas(callback=on_moneda_ingresada)
hardware.init_gpio_lavadoras()

# --- Rutas ---
@ui.page('/')
def kiosko_cliente():
    # Establecemos estilos globales minimalistas y atractivos
    ui.add_head_html('''
        <style>
            body { background-color: #0f172a; color: #ffffff; font-family: 'Inter', Tahoma, sans-serif; margin: 0; padding: 0; }
            .card-servicio { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(10px); border-radius: 20px; padding: 30px; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); cursor: pointer; border: 1px solid rgba(255,255,255,0.1); text-align: center; }
            .card-servicio:hover { transform: translateY(-8px); box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.1); border-color: #3b82f6; background: rgba(30, 41, 59, 0.9); }
            .title { font-size: 3rem; font-weight: 800; background: -webkit-linear-gradient(45deg, #3b82f6, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; margin-bottom: 10px; }
            .subtitle { font-size: 1.5rem; color: #94a3b8; text-align: center; font-weight: 500; }
            .price { font-size: 2.5rem; font-weight: bold; color: #f8fafc; margin-top: 15px; }
            .glass-panel { background: rgba(15, 23, 42, 0.6); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.05); border-radius: 24px; }
        </style>
    ''')
    
    # Refreshable UI section
    @ui.refreshable
    def vista_principal():
        with ui.column().classes('w-full h-screen items-center justify-center p-8 relative'):
            
            # Decoración de fondo suave
            ui.html('<div style="position:absolute; top:-10%; left:-10%; width:40%; height:40%; background:radial-gradient(circle, rgba(59,130,246,0.15) 0%, transparent 70%); z-index:-1;"></div>')
            ui.html('<div style="position:absolute; bottom:-10%; right:-10%; width:40%; height:40%; background:radial-gradient(circle, rgba(139,92,246,0.15) 0%, transparent 70%); z-index:-1;"></div>')
            
            if not hardware.HARDWARE_AVAILABLE:
                def handle_keyboard(e):
                    if e.action.keydown:
                        if e.key in ['1', '2', '5', '0']: # '0' representa $10
                            val = 10 if e.key == '0' else int(e.key)
                            lector_monedas.simular_moneda(val)
                            ui.notify(f'🪙 Simulación: ${val}', position='top', type='info')
                ui.keyboard(on_key=handle_keyboard)
                
            if not state.servicio_seleccionado:
                # Pantalla 1: Selección de Servicio
                ui.label('Lavandería EcoLuna').classes('title')
                ui.label('Seleccione un servicio para comenzar').classes('subtitle mb-12')
                
                with ui.row().classes('gap-8 w-full justify-center max-w-4xl'):
                    for servicio in SERVICIOS:
                        with ui.card().classes('card-servicio w-72 h-64 flex flex-col justify-center').on('click', lambda s=servicio.nombre: state.seleccionar_servicio(s)):
                            ui.label(servicio.nombre).classes('text-3xl font-bold text-gray-200 mb-2')
                            ui.label(f'${servicio.precio}').classes('price')
                            
                # Simulación de monedas para pruebas si no hay hardware
                if not hardware.HARDWARE_AVAILABLE:
                    ui.label('Simulador de hardware (Solo desarrollo):').classes('mt-16 text-gray-600 text-sm')
                    with ui.row().classes('gap-2'):
                        ui.button('$1', on_click=lambda: lector_monedas.simular_moneda(1)).props('color=grey outline')
                        ui.button('$2', on_click=lambda: lector_monedas.simular_moneda(2)).props('color=grey outline')
                        ui.button('$5', on_click=lambda: lector_monedas.simular_moneda(5)).props('color=grey outline')
                        ui.button('$10', on_click=lambda: lector_monedas.simular_moneda(10)).props('color=grey outline')

            elif state.servicio_seleccionado and not state.exito:
                # Pantalla 2: Pago
                ui.label('Complete su pago').classes('title mb-8')
                with ui.column().classes('glass-panel p-10 w-full max-w-md items-center shadow-2xl'):
                    ui.label(f'Servicio: {state.servicio_seleccionado.nombre}').classes('text-2xl text-gray-300 mb-4 font-semibold')
                    
                    with ui.column().classes('items-center bg-gray-800/50 w-full py-6 rounded-xl mb-8 border border-gray-700'):
                        ui.label('Falta por pagar').classes('text-gray-400 text-sm uppercase tracking-wider mb-1')
                        ui.label(f'${state.get_faltante()}').classes('text-6xl font-bold text-blue-400')
                        
                    ui.label(f'Monto ingresado: ${state.dinero_ingresado}').classes('text-xl text-gray-400 mb-8 font-medium')
                    
                    if state.puede_pagar():
                        state.procesar_exito()
                        asyncio.create_task(finalizar_pago())
                        
                    ui.button('Cancelar y Regresar', on_click=state.reset).classes('w-full h-14 text-lg font-bold').props('color=red-500 rounded-xl')
                    
                # Simulación de monedas para pruebas
                if not hardware.HARDWARE_AVAILABLE:
                    ui.label('Inserte Moneda:').classes('mt-12 text-gray-500')
                    with ui.row().classes('gap-3 mt-4'):
                        for val in [1, 2, 5, 10]:
                            ui.button(f'${val}', on_click=lambda v=val: lector_monedas.simular_moneda(v)).classes('w-16 h-16 text-xl rounded-full bg-slate-800 hover:bg-slate-700 border border-slate-600')

            elif state.exito:
                # Pantalla 3: Éxito
                ui.label('¡Pago Exitoso!').classes('text-6xl font-extrabold text-green-400 mb-6 text-center')
                ui.icon('check_circle', color='green').classes('text-[8rem] mb-10 drop-shadow-[0_0_15px_rgba(74,222,128,0.5)]')
                
                ui.label('Pese su ropa al mostrador').classes('text-3xl text-gray-200 mb-6 text-center font-bold')
                
                cambio = state.get_cambio()
                if cambio > 0:
                    with ui.row().classes('bg-yellow-500/20 px-8 py-4 rounded-2xl border border-yellow-500/30 mb-8'):
                        ui.label(f'No olvide su cambio: ').classes('text-2xl text-yellow-100')
                        ui.label(f'${cambio}').classes('text-3xl font-bold text-yellow-400 ml-2')
                
                ui.label('El sistema se reiniciará en breve...').classes('text-gray-500 text-lg mt-8')

    state.set_callback(vista_principal.refresh)
    vista_principal()

async def finalizar_pago():
    # 1. Registrar en BBDD asíncronamente
    await database.registrar_venta_async(
        servicio=state.servicio_seleccionado.nombre,
        monto=state.servicio_seleccionado.precio,
        ingresado=state.dinero_ingresado,
        cambio=state.get_cambio(),
        equipo='N/A',
        duracion=state.servicio_seleccionado.duracion_min
    )
    # 2. Esperar unos segundos para mostrar la pantalla de éxito
    await asyncio.sleep(6)
    # 3. Resetear kiosko
    state.reset()


@ui.page('/admin')
def admin_panel():
    ui.add_head_html('''
        <style>
            body { background-color: #f1f5f9; color: #1e293b; font-family: 'Inter', sans-serif; margin: 0; }
            .dashboard-card { background: white; border-radius: 16px; padding: 24px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -2px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; transition: transform 0.2s; }
            .dashboard-card:hover { transform: translateY(-2px); box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1); }
            .admin-header { background: #ffffff; border-bottom: 1px solid #e2e8f0; box-shadow: 0 1px 3px 0 rgba(0,0,0,0.1); }
        </style>
    ''')
    
    with ui.row().classes('admin-header w-full p-6 mb-8 items-center justify-between'):
        ui.label('EcoLuna - Panel de Control').classes('text-3xl font-bold text-slate-800 tracking-tight')
        ui.icon('admin_panel_settings', color='slate').classes('text-4xl text-slate-600')
    
    # Contenedor principal
    pendientes_container = ui.column().classes('w-full max-w-6xl mx-auto px-4')
    
    @ui.refreshable
    async def vista_pendientes():
        with pendientes_container:
            ui.label('Transacciones Pendientes (Por Atender)').classes('text-2xl font-bold mb-6 text-slate-700')
            ventas = await database.obtener_ventas_pendientes_async()
            
            if not ventas:
                with ui.column().classes('w-full items-center justify-center py-20 bg-white rounded-2xl border border-dashed border-slate-300'):
                    ui.icon('inventory_2', color='slate').classes('text-6xl text-slate-300 mb-4')
                    ui.label('No hay órdenes pendientes en este momento.').classes('text-slate-500 text-xl font-medium')
                return

            # Tarjetas de transacciones
            for venta in ventas:
                with ui.row().classes('dashboard-card w-full items-center justify-between mb-5'):
                    # Info Venta
                    with ui.column().classes('gap-1'):
                        with ui.row().classes('items-center gap-2'):
                            ui.label(f"Orden #{venta['id_transaccion']}").classes('text-sm font-bold bg-blue-100 text-blue-700 px-3 py-1 rounded-full')
                            ui.label(f"{venta['tipo_servicio']}").classes('text-2xl font-bold text-slate-800')
                        
                        ui.label(f"Fecha: {venta['fecha_hora']}").classes('text-slate-500 text-sm mt-2')
                        with ui.row().classes('items-center gap-4 mt-1'):
                            ui.label(f"Pagado: ${venta['monto_pagado']}").classes('text-slate-700 font-semibold text-lg')
                            ui.label(f"Cambio devuelto: ${venta['cambio_devuelto']}").classes('text-slate-500 text-sm')
                    
                    # Botones de Máquinas
                    with ui.column().classes('items-end'):
                        ui.label('Asignar a máquina:').classes('text-sm text-slate-500 font-medium mb-3')
                        # Layout sugerido por el usuario: Cuarto cuadrado. Lado derecho (3 maquinas), lado izquierdo (3 maquinas).
                        # Aquí el usuario especificó solo los pines para Lavadora 1 (17), Lavadora 2 (18) y Lavadora 3 (4).
                        with ui.row().classes('gap-3'):
                            ui.button('Lavadora 1', icon='local_laundry_service', on_click=lambda v=venta: iniciar_maquina(v, 'Lavadora 1', hardware.PIN_LAVADORA_1)).classes('bg-green-600 hover:bg-green-700 font-bold px-6 py-2 rounded-xl shadow-md transition-colors')
                            ui.button('Lavadora 2', icon='local_laundry_service', on_click=lambda v=venta: iniciar_maquina(v, 'Lavadora 2', hardware.PIN_LAVADORA_2)).classes('bg-green-600 hover:bg-green-700 font-bold px-6 py-2 rounded-xl shadow-md transition-colors')
                            ui.button('Lavadora 3', icon='local_laundry_service', on_click=lambda v=venta: iniciar_maquina(v, 'Lavadora 3', hardware.PIN_LAVADORA_3)).classes('bg-green-600 hover:bg-green-700 font-bold px-6 py-2 rounded-xl shadow-md transition-colors')

    async def iniciar_maquina(venta, nombre_maquina, pin):
        # 1. Enviar pulso asíncrono
        await hardware.activar_lavadora(pin)
        # 2. Actualizar BBDD
        await database.marcar_completado_async(venta['id_transaccion'], nombre_maquina)
        # 3. Notificar y refrescar
        ui.notify(f"Se activó {nombre_maquina} para la Orden #{venta['id_transaccion']}", type='positive', position='top', progress=True)
        vista_pendientes.refresh()

    vista_pendientes()
    
    # Polling para actualizar la vista de admin cada 3 segundos en segundo plano
    ui.timer(3.0, vista_pendientes.refresh)

if __name__ in {"__main__", "__mp_main__"}:
    # Iniciar servidor web asíncrono
    ui.run(title='Lavandería EcoLuna', port=8080, dark=True)
