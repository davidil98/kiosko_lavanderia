import sqlite3
import datetime
import os

DB_PATH = "ecoluna_datos.db"

def inicializar_bd():
    """Crea la base de datos y la tabla si no existen."""
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transacciones (
            id_transaccion INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT,
            tipo_servicio TEXT,
            monto_pagado REAL,
            dinero_ingresado REAL,
            cambio_devuelto REAL,
            id_equipo TEXT,
            duracion_estimada_min INTEGER
        )
    ''')
    conexion.commit()
    conexion.close()

def registrar_venta(servicio, monto, ingresado, cambio, equipo="N/A", duracion=45):
    """Inserta un nuevo registro en la base de datos."""
    conexion = sqlite3.connect(DB_PATH)
    cursor = conexion.cursor()
    
    fecha_actual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute('''
        INSERT INTO transacciones 
        (fecha_hora, tipo_servicio, monto_pagado, dinero_ingresado, cambio_devuelto, id_equipo, duracion_estimada_min)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (fecha_actual, servicio, float(monto), float(ingresado), float(cambio), equipo, int(duracion)))
    
    conexion.commit()
    conexion.close()
    print("Venta registrada en SQLite exitosamente.")