import sqlite3
import os
from datetime import datetime
import asyncio

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "data", "ecoluna_datos.db")

# FUNCIÓN DE INICIALIZACIÓN
def init_db():
    """Crea el archivo de la base de datos y la estructura si no existen.
    Añade columnas nuevas si no existen (migraciones seguras).
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    cursor = conn.cursor()
    
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
            inicio_servicio TEXT,
            peso_kg REAL DEFAULT 0,
            notas TEXT DEFAULT '',
            etapa_kanban TEXT DEFAULT NULL,
            modalidad TEXT DEFAULT 'autoservicio'
        )
    ''')

    # Migración segura: añadir columnas si no existen en tablas ya creadas
    columnas_nuevas = [
        ("peso_kg",       "REAL    DEFAULT 0"),
        ("notas",         "TEXT    DEFAULT ''"),
        ("etapa_kanban",  "TEXT    DEFAULT NULL"),
        ("modalidad",     "TEXT    DEFAULT 'autoservicio'"),
    ]
    cursor.execute("PRAGMA table_info(transacciones)")
    cols_existentes = {row[1] for row in cursor.fetchall()}
    for col_nombre, col_def in columnas_nuevas:
        if col_nombre not in cols_existentes:
            cursor.execute(f"ALTER TABLE transacciones ADD COLUMN {col_nombre} {col_def}")
            print(f"DB: Columna '{col_nombre}' añadida.")

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

def _registrar_venta(servicio, monto, ingresado, cambio, equipo, duracion,
                     nombre_cliente, peso_kg=0.0, modalidad='autoservicio'):
    conn = _get_connection()
    cursor = conn.cursor()
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Las órdenes personalizadas entran directamente en etapa_kanban='Recibido'
    etapa = 'Recibido' if modalidad == 'personalizado' else None
    cursor.execute('''
        INSERT INTO transacciones
            (fecha_hora, tipo_servicio, monto_pagado, dinero_ingresado, cambio_devuelto,
             id_equipo, duracion_estimada_min, estado, nombre_cliente,
             peso_kg, notas, etapa_kanban, modalidad)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pendiente', ?, ?, '', ?, ?)
    ''', (fecha_hora, servicio, monto, ingresado, cambio, equipo, duracion,
          nombre_cliente, peso_kg, etapa, modalidad))
    conn.commit()
    nuevo_id = cursor.lastrowid
    conn.close()
    return nuevo_id

async def registrar_venta_async(servicio, monto, ingresado, cambio, equipo, duracion,
                                nombre_cliente, peso_kg=0.0, modalidad='autoservicio'):
    return await run_in_executor(_registrar_venta, servicio, monto, ingresado, cambio,
                                 equipo, duracion, nombre_cliente, peso_kg, modalidad)

# ── Autoservicio ──────────────────────────────────────────────────────────────

def _obtener_ventas_activas():
    """Órdenes de autoservicio Pendientes y En proceso."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM transacciones "
        "WHERE estado IN ('Pendiente', 'En proceso') "
        "AND (modalidad IS NULL OR modalidad = 'autoservicio') "
        "ORDER BY id_transaccion ASC"
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

# ── Lavado Personalizado (Kanban) ─────────────────────────────────────────────

ETAPAS_KANBAN = ['Recibido', 'En Proceso', 'Alistando', 'Listo para Entrega', 'Entregado']

def _obtener_ordenes_personalizadas():
    """Todas las órdenes de tipo personalizado que no están eliminadas."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM transacciones WHERE modalidad = 'personalizado' ORDER BY id_transaccion ASC"
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

async def obtener_ordenes_personalizadas_async():
    return await run_in_executor(_obtener_ordenes_personalizadas)

def _actualizar_etapa_kanban(id_transaccion, nueva_etapa, equipo_id=None):
    conn = _get_connection()
    cursor = conn.cursor()
    nuevo_estado = 'Completado' if nueva_etapa == 'Entregado' else 'En proceso'
    if equipo_id:
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "UPDATE transacciones SET etapa_kanban=?, estado=?, id_equipo=?, inicio_servicio=? WHERE id_transaccion=?",
            (nueva_etapa, nuevo_estado, equipo_id, ahora, id_transaccion)
        )
    else:
        cursor.execute(
            "UPDATE transacciones SET etapa_kanban=?, estado=? WHERE id_transaccion=?",
            (nueva_etapa, nuevo_estado, id_transaccion)
        )
    conn.commit()
    conn.close()

async def actualizar_etapa_kanban_async(id_transaccion, nueva_etapa, equipo_id=None):
    await run_in_executor(_actualizar_etapa_kanban, id_transaccion, nueva_etapa, equipo_id)

def _actualizar_notas(id_transaccion, notas):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE transacciones SET notas=? WHERE id_transaccion=?",
        (notas, id_transaccion)
    )
    conn.commit()
    conn.close()

async def actualizar_notas_async(id_transaccion, notas):
    await run_in_executor(_actualizar_notas, id_transaccion, notas)
