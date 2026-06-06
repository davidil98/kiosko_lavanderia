import sqlite3
import os
from datetime import datetime
import asyncio

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data", "ecoluna_datos.db")

def _get_connection():
    # Helper for synchronous sqlite connection
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Helper for async DB calls to avoid blocking NiceGUI
async def run_in_executor(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)

def _registrar_venta(servicio, monto, ingresado, cambio, equipo, duracion):
    conn = _get_connection()
    cursor = conn.cursor()
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO transacciones (fecha_hora, tipo_servicio, monto_pagado, dinero_ingresado, cambio_devuelto, id_equipo, duracion_estimada_min, estado)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pendiente')
    ''', (fecha_hora, servicio, monto, ingresado, cambio, equipo, duracion))
    conn.commit()
    conn.close()

async def registrar_venta_async(servicio, monto, ingresado, cambio, equipo, duracion):
    await run_in_executor(_registrar_venta, servicio, monto, ingresado, cambio, equipo, duracion)

def _obtener_ventas_pendientes():
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transacciones WHERE estado = 'Pendiente' ORDER BY id_transaccion ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

async def obtener_ventas_pendientes_async():
    return await run_in_executor(_obtener_ventas_pendientes)

def _marcar_completado(id_transaccion, id_equipo):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE transacciones SET estado = 'Completado', id_equipo = ? WHERE id_transaccion = ?", (id_equipo, id_transaccion))
    conn.commit()
    conn.close()

async def marcar_completado_async(id_transaccion, id_equipo):
    await run_in_executor(_marcar_completado, id_transaccion, id_equipo)
