import sqlite3
import os
from datetime import datetime
import asyncio

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data", "ecoluna_datos.db")

# FUNCIÓN DE INICIALIZACIÓN
def init_db():
    """Crea el archivo de la base de datos y la estructura si no existen."""
    # Crea la carpeta 'data' si por algún motivo no existe
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    cursor = conn.cursor()
    
    # Creamos la tabla con las nuevas columnas incluidas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transacciones (
            id_transaccion INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT,
            tipo_servicio TEXT,
            monto_pagado INTEGER,
            dinero_ingresado INTEGER,
            cambio_devuelto INTEGER,
            id_equipo TEXT,
            duracion_estimada_min INTEGER,
            estado TEXT DEFAULT 'Pendiente',
            nombre_cliente TEXT DEFAULT 'Cliente',
            inicio_servicio TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("Base de datos verificada/inicializada correctamente.")

def _get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    conn.row_factory = sqlite3.Row
    return conn

async def run_in_executor(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)

def _registrar_venta(servicio, monto, ingresado, cambio, equipo, duracion, nombre_cliente):
    conn = _get_connection()
    cursor = conn.cursor()
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO transacciones
            (fecha_hora, tipo_servicio, monto_pagado, dinero_ingresado, cambio_devuelto,
             id_equipo, duracion_estimada_min, estado, nombre_cliente)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pendiente', ?)
    ''', (fecha_hora, servicio, monto, ingresado, cambio, equipo, duracion, nombre_cliente))
    conn.commit()
    nuevo_id = cursor.lastrowid
    conn.close()
    return nuevo_id

async def registrar_venta_async(servicio, monto, ingresado, cambio, equipo, duracion, nombre_cliente):
    return await run_in_executor(_registrar_venta, servicio, monto, ingresado, cambio, equipo, duracion, nombre_cliente)

def _obtener_ventas_activas():
    """Obtiene ventas Pendientes y En proceso (las que el admin debe ver)."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM transacciones WHERE estado IN ('Pendiente', 'En proceso') ORDER BY id_transaccion ASC"
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

async def obtener_ventas_activas_async():
    return await run_in_executor(_obtener_ventas_activas)

def _marcar_en_proceso(id_transaccion, id_equipo):
    conn = _get_connection()
    cursor = conn.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE transacciones SET estado = 'En proceso', id_equipo = ?, inicio_servicio = ? WHERE id_transaccion = ?",
        (id_equipo, ahora, id_transaccion)
    )
    conn.commit()
    conn.close()

async def marcar_en_proceso_async(id_transaccion, id_equipo):
    await run_in_executor(_marcar_en_proceso, id_transaccion, id_equipo)

def _marcar_completado(id_transaccion, id_equipo):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE transacciones SET estado = 'Completado', id_equipo = ? WHERE id_transaccion = ?",
        (id_equipo, id_transaccion)
    )
    conn.commit()
    conn.close()

async def marcar_completado_async(id_transaccion, id_equipo):
    await run_in_executor(_marcar_completado, id_transaccion, id_equipo)
