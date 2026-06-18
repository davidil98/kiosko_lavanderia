import sqlite3
import os
from datetime import datetime
import asyncio

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "..",
    "data",
    "ecoluna_datos.db",
)


# FUNCIÓN DE INICIALIZACIÓN
def init_db():
    """Crea el archivo de la base de datos y la estructura si no existen.
    Añade columnas nuevas si no existen (migraciones seguras).
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    cursor = conn.cursor()

    cursor.execute("""
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
    """)

    # Migración segura: añadir columnas si no existen en tablas ya creadas
    columnas_nuevas = [
        ("peso_kg", "REAL    DEFAULT 0"),
        ("notas", "TEXT    DEFAULT ''"),
        ("etapa_kanban", "TEXT    DEFAULT NULL"),
        ("modalidad", "TEXT    DEFAULT 'autoservicio'"),
        ("numero_transaccion_terminal", "TEXT    DEFAULT ''"),
        ("validado_por", "TEXT    DEFAULT ''"),
    ]
    cursor.execute("PRAGMA table_info(transacciones)")
    cols_existentes = {row[1] for row in cursor.fetchall()}
    for col_nombre, col_def in columnas_nuevas:
        if col_nombre not in cols_existentes:
            cursor.execute(
                f"ALTER TABLE transacciones ADD COLUMN {col_nombre} {col_def}"
            )
            print(f"DB: Columna '{col_nombre}' añadida.")

    conn.commit()
    conn.close()
    print("Base de datos verificada/inicializada correctamente.")


def _get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn


async def run_in_executor(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


def _registrar_venta(
    servicio,
    monto,
    ingresado,
    cambio,
    equipo,
    duracion,
    nombre_cliente,
    peso_kg=0.0,
    modalidad="autoservicio",
):
    conn = _get_connection()
    cursor = conn.cursor()
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Las órdenes personalizadas entran directamente en etapa_kanban='Recibido'
    etapa = "Recibido" if modalidad == "personalizado" else None
    cursor.execute(
        """
        INSERT INTO transacciones
            (fecha_hora, tipo_servicio, monto_pagado, dinero_ingresado, cambio_devuelto,
             id_equipo, duracion_estimada_min, estado, nombre_cliente,
             peso_kg, notas, etapa_kanban, modalidad)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pendiente', ?, ?, '', ?, ?)
    """,
        (
            fecha_hora,
            servicio,
            monto,
            ingresado,
            cambio,
            equipo,
            duracion,
            nombre_cliente,
            peso_kg,
            etapa,
            modalidad,
        ),
    )
    conn.commit()
    nuevo_id = cursor.lastrowid
    conn.close()
    return nuevo_id


async def registrar_venta_async(
    servicio,
    monto,
    ingresado,
    cambio,
    equipo,
    duracion,
    nombre_cliente,
    peso_kg=0.0,
    modalidad="autoservicio",
):
    return await run_in_executor(
        _registrar_venta,
        servicio,
        monto,
        ingresado,
        cambio,
        equipo,
        duracion,
        nombre_cliente,
        peso_kg,
        modalidad,
    )


# ── Autoservicio ──────────────────────────────────────────────────────────────


# ── Panel Operativo (bandeja de entrada unificada) ──


def _obtener_ordenes_pendientes_admin():
    """Órdenes que requieren acción administrativa: pendientes de peso o de pago.
    Sin importar modalidad — todas pasan por el operativo."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM transacciones "
        "WHERE estado IN ('Pendiente-peso', 'Procesando-pago', 'Pendiente-pago') "
        "ORDER BY id_transaccion ASC"
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


async def obtener_ordenes_pendientes_admin_async():
    return await run_in_executor(_obtener_ordenes_pendientes_admin)


def _obtener_contadores_pendientes():
    """Cuenta órdenes por tipo para los badges del dashboard."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT estado, COUNT(*) as cnt FROM transacciones "
        "WHERE estado IN ('Pendiente-peso', 'Procesando-pago', 'Pendiente-pago', 'Pendiente', 'En proceso') "
        "GROUP BY estado"
    )
    counts = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return counts


async def obtener_contadores_pendientes_async():
    return await run_in_executor(_obtener_contadores_pendientes)


# ── Panel Autoservicio (solo ejecución: asignar + en proceso) ──


def _obtener_ordenes_autoservicio_asignacion():
    """Órdenes de autoservicio listas para asignar máquina ('Pendiente')
    o ya en ejecución ('En proceso'). Solo autoservicio."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM transacciones "
        "WHERE estado IN ('Pendiente', 'En proceso') "
        "AND (modalidad IS NULL OR modalidad LIKE 'autoservicio%') "
        "ORDER BY id_transaccion ASC"
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


async def obtener_ordenes_autoservicio_asignacion_async():
    return await run_in_executor(_obtener_ordenes_autoservicio_asignacion)


def _obtener_ordenes_en_proceso():
    """Órdenes en estado 'En proceso' (autoservicio o personalizado).
    Usado solo para recuperación tras apagón."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM transacciones WHERE estado = 'En proceso' ORDER BY id_transaccion ASC"
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


async def obtener_ordenes_en_proceso_async():
    return await run_in_executor(_obtener_ordenes_en_proceso)


def _marcar_en_proceso(id_transaccion, id_equipo):
    conn = _get_connection()
    cursor = conn.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE transacciones SET estado = 'En proceso', id_equipo = ?, inicio_servicio = ? WHERE id_transaccion = ?",
        (id_equipo, ahora, id_transaccion),
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
        (id_equipo, id_transaccion),
    )
    conn.commit()
    conn.close()


async def marcar_completado_async(id_transaccion, id_equipo):
    await run_in_executor(_marcar_completado, id_transaccion, id_equipo)


# ── Aprobación manual de peso y pago por terminal (admin) ─────────────────────


def _registrar_venta_pendiente_peso(
    servicio, peso_kg, nombre_cliente, duracion, modalidad
):
    """Crea una orden en estado 'Pendiente-peso' a la espera de validación del admin."""
    conn = _get_connection()
    cursor = conn.cursor()
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    etapa = "Recibido" if modalidad == "personalizado" else None
    cursor.execute(
        """
        INSERT INTO transacciones
            (fecha_hora, tipo_servicio, monto_pagado, dinero_ingresado, cambio_devuelto,
             id_equipo, duracion_estimada_min, estado, nombre_cliente,
             peso_kg, notas, etapa_kanban, modalidad)
        VALUES (?, ?, 0, 0, 0, 'N/A', ?, 'Pendiente-peso', ?, ?, '', ?, ?)
    """,
        (fecha_hora, servicio, duracion, nombre_cliente, peso_kg, etapa, modalidad),
    )
    conn.commit()
    nuevo_id = cursor.lastrowid
    conn.close()
    return nuevo_id


async def registrar_venta_pendiente_peso_async(
    servicio, peso_kg, nombre_cliente, duracion, modalidad
):
    return await run_in_executor(
        _registrar_venta_pendiente_peso,
        servicio,
        peso_kg,
        nombre_cliente,
        duracion,
        modalidad,
    )


def _aprobar_peso(id_transaccion, peso_final, usuario):
    conn = _get_connection()
    cursor = conn.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nota = f"PESO APROBADO por {usuario} a las {ahora}"
    cursor.execute(
        """
        UPDATE transacciones
        SET estado = 'Procesando-pago', peso_kg = ?, notas = ?, validado_por = ?
        WHERE id_transaccion = ? AND estado = 'Pendiente-peso'
    """,
        (peso_final, nota, usuario, id_transaccion),
    )
    conn.commit()
    conn.close()


async def aprobar_peso_async(id_transaccion, peso_final, usuario):
    await run_in_executor(_aprobar_peso, id_transaccion, peso_final, usuario)


def _rechazar_peso(id_transaccion, usuario):
    """Borra la orden 'Pendiente-peso'. Registra en notas no persistente (log)."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM transacciones WHERE id_transaccion = ? AND estado = 'Pendiente-peso'",
        (id_transaccion,),
    )
    conn.commit()
    conn.close()


async def rechazar_peso_async(id_transaccion, usuario):
    await run_in_executor(_rechazar_peso, id_transaccion, usuario)


def _registrar_venta_pendiente_terminal(
    servicio, peso_kg, monto, nombre_cliente, duracion, modalidad
):
    """Crea una orden 'Pendiente-pago' cuando el cliente elige pagar por terminal."""
    conn = _get_connection()
    cursor = conn.cursor()
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    etapa = "Recibido" if modalidad == "personalizado" else None
    cursor.execute(
        """
        INSERT INTO transacciones
            (fecha_hora, tipo_servicio, monto_pagado, dinero_ingresado, cambio_devuelto,
             id_equipo, duracion_estimada_min, estado, nombre_cliente,
             peso_kg, notas, etapa_kanban, modalidad)
        VALUES (?, ?, ?, 0, 0, 'N/A', ?, 'Pendiente-pago', ?, ?, '', ?, ?)
    """,
        (
            fecha_hora,
            servicio,
            monto,
            duracion,
            nombre_cliente,
            peso_kg,
            etapa,
            f"{modalidad}-terminal",
        ),
    )
    conn.commit()
    nuevo_id = cursor.lastrowid
    conn.close()
    return nuevo_id


async def registrar_venta_pendiente_terminal_async(
    servicio, peso_kg, monto, nombre_cliente, duracion, modalidad
):
    return await run_in_executor(
        _registrar_venta_pendiente_terminal,
        servicio,
        peso_kg,
        monto,
        nombre_cliente,
        duracion,
        modalidad,
    )


def _aprobar_pago_terminal(id_transaccion, folio, usuario):
    conn = _get_connection()
    cursor = conn.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nota = f"PAGO TERMINAL confirmado por {usuario} a las {ahora}"
    cursor.execute(
        """
        UPDATE transacciones
        SET estado = 'Pendiente',
            numero_transaccion_terminal = ?,
            notas = ?,
            validado_por = ?
        WHERE id_transaccion = ? AND estado = 'Pendiente-pago'
    """,
        (folio or "", nota, usuario, id_transaccion),
    )
    conn.commit()
    conn.close()


async def aprobar_pago_terminal_async(id_transaccion, folio, usuario):
    await run_in_executor(_aprobar_pago_terminal, id_transaccion, folio, usuario)


def _cancelar_pago_pendiente(id_transaccion, usuario):
    """Borra una orden 'Pendiente-pago' o 'Procesando-pago' si se cancela."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM transacciones WHERE id_transaccion = ? AND estado IN ('Pendiente-pago', 'Procesando-pago')",
        (id_transaccion,),
    )
    conn.commit()
    conn.close()


async def cancelar_pago_pendiente_async(id_transaccion, usuario):
    await run_in_executor(_cancelar_pago_pendiente, id_transaccion, usuario)


def _marcar_pendiente_pago(id_transaccion, monto, modalidad=None):
    """Convierte una orden 'Procesando-pago' en 'Pendiente-pago'.
    Si no se indica modalidad, se deriva automáticamente como {base}-terminal."""
    conn = _get_connection()
    cursor = conn.cursor()
    if modalidad is None:
        cursor.execute(
            "SELECT modalidad FROM transacciones WHERE id_transaccion = ? AND estado = 'Procesando-pago'",
            (id_transaccion,),
        )
        row = cursor.fetchone()
        base = row[0].split("-")[0] if row and row[0] else "autoservicio"
        modalidad = f"{base}-terminal"
    cursor.execute(
        """
        UPDATE transacciones
        SET estado = 'Pendiente-pago', monto_pagado = ?, modalidad = ?
        WHERE id_transaccion = ? AND estado = 'Procesando-pago'
    """,
        (monto, modalidad, id_transaccion),
    )
    actualizado = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return id_transaccion if actualizado else None


async def marcar_pendiente_pago_async(id_transaccion, monto, modalidad=None):
    return await run_in_executor(
        _marcar_pendiente_pago, id_transaccion, monto, modalidad
    )


def _guardar_pago_orden(id_transaccion, metodo, monto, ingresado, cambio, modalidad):
    """Actualiza una orden 'Procesando-pago' → 'Pendiente' con los datos de pago.
    Retorna el id si se actualizó, o None si la orden ya no estaba en ese estado
    (cancelada o ya procesada por el operativo)."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE transacciones
        SET estado = 'Pendiente',
            monto_pagado = ?,
            dinero_ingresado = ?,
            cambio_devuelto = ?,
            modalidad = ?
        WHERE id_transaccion = ? AND estado = 'Procesando-pago'
    """,
        (monto, ingresado, cambio, modalidad, id_transaccion),
    )
    actualizado = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return id_transaccion if actualizado else None


async def guardar_pago_orden_async(
    id_transaccion, metodo, monto, ingresado, cambio, modalidad
):
    return await run_in_executor(
        _guardar_pago_orden,
        id_transaccion,
        metodo,
        monto,
        ingresado,
        cambio,
        modalidad,
    )


# ── Lavado Personalizado (Kanban) ─────────────────────────────────────────────

ETAPAS_KANBAN = [
    "Recibido",
    "En Proceso",
    "Alistando",
    "Listo para Entrega",
    "Entregado",
]


def _obtener_ordenes_personalizadas():
    """Todas las órdenes de tipo personalizado que no están eliminadas."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM transacciones WHERE modalidad LIKE 'personalizado%' ORDER BY id_transaccion ASC"
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


async def obtener_ordenes_personalizadas_async():
    return await run_in_executor(_obtener_ordenes_personalizadas)


def _actualizar_etapa_kanban(id_transaccion, nueva_etapa, equipo_id=None):
    conn = _get_connection()
    cursor = conn.cursor()
    nuevo_estado = "Completado" if nueva_etapa == "Entregado" else "En proceso"
    if equipo_id:
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "UPDATE transacciones SET etapa_kanban=?, estado=?, id_equipo=?, inicio_servicio=? WHERE id_transaccion=?",
            (nueva_etapa, nuevo_estado, equipo_id, ahora, id_transaccion),
        )
    else:
        cursor.execute(
            "UPDATE transacciones SET etapa_kanban=?, estado=? WHERE id_transaccion=?",
            (nueva_etapa, nuevo_estado, id_transaccion),
        )
    conn.commit()
    conn.close()


async def actualizar_etapa_kanban_async(id_transaccion, nueva_etapa, equipo_id=None):
    await run_in_executor(
        _actualizar_etapa_kanban, id_transaccion, nueva_etapa, equipo_id
    )


def _actualizar_notas(id_transaccion, notas):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE transacciones SET notas=? WHERE id_transaccion=?",
        (notas, id_transaccion),
    )
    conn.commit()
    conn.close()


async def actualizar_notas_async(id_transaccion, notas):
    await run_in_executor(_actualizar_notas, id_transaccion, notas)
