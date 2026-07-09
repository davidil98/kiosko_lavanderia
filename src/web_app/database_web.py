import sqlite3
import os
import json
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
        ("mp_order_id", "TEXT    DEFAULT ''"),
    ]
    cursor.execute("PRAGMA table_info(transacciones)")
    cols_existentes = {row[1] for row in cursor.fetchall()}
    for col_nombre, col_def in columnas_nuevas:
        if col_nombre not in cols_existentes:
            cursor.execute(
                f"ALTER TABLE transacciones ADD COLUMN {col_nombre} {col_def}"
            )
            print(f"DB: Columna '{col_nombre}' añadida.")

    # ── Tabla servicios (catálogo data-driven) ─────────────────────────────
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS servicios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            modalidad TEXT NOT NULL,
            icono TEXT DEFAULT '/media/icons/leaf.svg',
            tipo_calculo TEXT NOT NULL DEFAULT 'fijo',
            precio_fijo INTEGER DEFAULT 0,
            tarifa_por_kg REAL DEFAULT 0,
            duracion_min INTEGER DEFAULT 0,
            limite_kg INTEGER,
            tipos_equipo TEXT DEFAULT '',
            orden INTEGER DEFAULT 0,
            activo INTEGER DEFAULT 1
        )
    """
    )
    # Seed inicial: los 4 servicios existentes como en el código anterior.
    # Solo se insertan si la tabla está vacía (no sobrescribe cambios del superadmin).
    cursor.execute("SELECT COUNT(*) FROM servicios")
    if cursor.fetchone()[0] == 0:
        servicios_seed = [
            (
                "autolavado",
                "Autolavado",
                "autoservicio",
                "/media/icons/leaf.svg",
                "fijo",
                45,
                0,
                45,
                None,
                "mixto,lavado",
                1,
                1,
            ),
            (
                "secado",
                "Secado",
                "autoservicio",
                "/media/icons/wind.svg",
                "fijo",
                50,
                0,
                45,
                None,
                "mixto,secado",
                2,
                1,
            ),
            (
                "pers_ropa",
                "Personalizado – Ropa",
                "personalizado",
                "/media/icons/shirt.svg",
                "por_kg",
                0,
                30,
                60,
                5,
                "",
                3,
                1,
            ),
            (
                "pers_edredon",
                "Personalizado – Edredones",
                "personalizado",
                "/media/icons/bed.svg",
                "fijo",
                150,
                0,
                90,
                5,
                "",
                4,
                1,
            ),
        ]
        cursor.executemany(
            """
            INSERT INTO servicios
                (codigo, nombre, modalidad, icono, tipo_calculo, precio_fijo,
                 tarifa_por_kg, duracion_min, limite_kg, tipos_equipo, orden, activo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            servicios_seed,
        )
        print("DB: Seed inicial de servicios insertado.")

    # ── Tabla segmentaciones (variantes dentro de un servicio) ─────────────
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS segmentaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            servicio_id INTEGER NOT NULL,
            codigo TEXT NOT NULL,
            nombre TEXT NOT NULL,
            descripcion TEXT DEFAULT '',
            tipo_calculo TEXT NOT NULL DEFAULT 'fijo',
            precio_fijo INTEGER DEFAULT 0,
            tarifa_por_kg REAL DEFAULT 0,
            duracion_min INTEGER DEFAULT 0,
            orden INTEGER DEFAULT 0,
            activo INTEGER DEFAULT 1,
            FOREIGN KEY (servicio_id) REFERENCES servicios(id) ON DELETE CASCADE,
            UNIQUE(servicio_id, codigo)
        )
    """
    )
    cursor.execute("SELECT COUNT(*) FROM segmentaciones")
    if cursor.fetchone()[0] == 0:
        # Mapeo codigo servicio -> id
        cursor.execute("SELECT id, codigo FROM servicios")
        srv_id = {row[1]: row[0] for row in cursor.fetchall()}
        seg_seed = []
        if "pers_ropa" in srv_id:
            seg_seed.extend(
                [
                    (
                        srv_id["pers_ropa"],
                        "completo",
                        "Lava + Seca + Dobla",
                        "Servicio completo, listo para guardar",
                        "por_kg",
                        0,
                        30,
                        60,
                        1,
                        1,
                    ),
                    (
                        srv_id["pers_ropa"],
                        "lava_exprime",
                        "Solo Lava + Exprime",
                        "Lavado y centrifugado, sin secado",
                        "por_kg",
                        0,
                        18,
                        35,
                        2,
                        1,
                    ),
                    (
                        srv_id["pers_ropa"],
                        "lava_seca",
                        "Lava + Seca",
                        "Sin doblado, listo para entrega",
                        "por_kg",
                        0,
                        25,
                        50,
                        3,
                        1,
                    ),
                ]
            )
        if "pers_edredon" in srv_id:
            seg_seed.extend(
                [
                    (
                        srv_id["pers_edredon"],
                        "completo",
                        "Lava + Seca",
                        "Lavado y secado completo",
                        "fijo",
                        150,
                        0,
                        90,
                        1,
                        1,
                    ),
                    (
                        srv_id["pers_edredon"],
                        "solo_lava",
                        "Solo Lavado",
                        "Lavado sin secado",
                        "fijo",
                        90,
                        0,
                        60,
                        2,
                        1,
                    ),
                ]
            )
        if seg_seed:
            cursor.executemany(
                """
                INSERT INTO segmentaciones
                    (servicio_id, codigo, nombre, descripcion, tipo_calculo,
                     precio_fijo, tarifa_por_kg, duracion_min, orden, activo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                seg_seed,
            )
            print("DB: Seed inicial de segmentaciones insertado.")

    # ── Tabla maquinas (catálogo de hardware) ─────────────────────────────
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS maquinas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            tipo TEXT NOT NULL,
            capacidad_kg INTEGER NOT NULL DEFAULT 0,
            gpio INTEGER NOT NULL,
            modo TEXT NOT NULL DEFAULT 'pulso',
            duracion_max_min INTEGER DEFAULT 25,
            activa INTEGER DEFAULT 1,
            orden INTEGER DEFAULT 0
        )
    """
    )
    cursor.execute("SELECT COUNT(*) FROM maquinas")
    if cursor.fetchone()[0] == 0:
        # Seed: las 4 máquinas que estaban en hardware.EQUIPOS
        maquinas_seed = [
            (
                "lavasecadora_1",
                "Lavasecadora 1",
                "mixto",
                5,
                17,
                "pulso",
                25,
                1,
                1,
            ),
            (
                "lavasecadora_2",
                "Lavasecadora 2",
                "mixto",
                5,
                18,
                "pulso",
                25,
                1,
                2,
            ),
            (
                "lavasecadora_3",
                "Lavasecadora 3",
                "mixto",
                5,
                4,
                "sostenido",
                25,
                1,
                3,
            ),
            (
                "secadora_1",
                "Secadora 1",
                "secado",
                5,
                23,
                "sostenido",
                40,
                1,
                4,
            ),
        ]
        cursor.executemany(
            """
            INSERT INTO maquinas
                (codigo, nombre, tipo, capacidad_kg, gpio, modo,
                 duracion_max_min, activa, orden)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            maquinas_seed,
        )
        print("DB: Seed inicial de maquinas insertado.")

    # ── Tabla _backup_default (respaldo de fábrica) ──────────────────────
    # Guarda un snapshot de servicios, segmentaciones y maquinas en JSON.
    # Se crea una vez, cuando se inicializa la DB por primera vez.
    # Luego el superadmin puede "Restaurar valores por defecto" desde la UI.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS _backup_default (
            tabla TEXT PRIMARY KEY,
            datos TEXT NOT NULL,
            created_at TEXT NOT NULL,
            nota TEXT DEFAULT ''
        )
    """
    )
    cursor.execute("SELECT COUNT(*) FROM _backup_default")
    if cursor.fetchone()[0] == 0:
        # Tomar snapshot de los seeds recién insertados
        for nombre_tabla in ("servicios", "segmentaciones", "maquinas"):
            cursor.execute(f"SELECT * FROM {nombre_tabla}")
            cols = [d[0] for d in cursor.description]
            rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """
                INSERT INTO _backup_default (tabla, datos, created_at, nota)
                VALUES (?, ?, ?, ?)
            """,
                (
                    nombre_tabla,
                    json.dumps(rows, default=str, ensure_ascii=False),
                    ahora,
                    "Snapshot inicial de fábrica",
                ),
            )
        print("DB: Snapshot inicial de respaldo creado.")

    # ── Tabla cortes_caja (ledger de efectivo) ───────────────────────────
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cortes_caja (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            usuario_apertura TEXT NOT NULL,
            saldo_inicial INTEGER NOT NULL,
            usuario_cierre TEXT,
            saldo_real INTEGER,
            saldo_esperado INTEGER,
            diferencia INTEGER,
            estado TEXT NOT NULL DEFAULT 'abierto',
            notas TEXT DEFAULT '',
            hora_apertura TEXT NOT NULL,
            hora_cierre TEXT
        )
    """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS movimientos_caja (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            corte_id INTEGER NOT NULL,
            fecha_hora TEXT NOT NULL,
            tipo TEXT NOT NULL,
            monto INTEGER NOT NULL,
            concepto TEXT NOT NULL,
            usuario TEXT NOT NULL,
            notas TEXT DEFAULT '',
            auto INTEGER DEFAULT 0,
            FOREIGN KEY (corte_id) REFERENCES cortes_caja(id) ON DELETE CASCADE
        )
    """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_mov_corte ON movimientos_caja(corte_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_cortes_estado ON cortes_caja(estado)"
    )

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


def _marcar_pendiente_pago(id_transaccion, monto, modalidad=None, mp_order_id=None):
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
    if mp_order_id is not None:
        cursor.execute(
            """
            UPDATE transacciones
            SET estado = 'Pendiente-pago', monto_pagado = ?, modalidad = ?, mp_order_id = ?
            WHERE id_transaccion = ? AND estado = 'Procesando-pago'
        """,
            (monto, modalidad, mp_order_id, id_transaccion),
        )
    else:
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


async def marcar_pendiente_pago_async(
    id_transaccion, monto, modalidad=None, mp_order_id=None
):
    return await run_in_executor(
        _marcar_pendiente_pago, id_transaccion, monto, modalidad, mp_order_id
    )


def _obtener_ordenes_point_pendientes():
    """Órdenes 'Pendiente-pago' con mp_order_id asignado (esperando pago en Point)."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM transacciones "
        "WHERE estado = 'Pendiente-pago' AND mp_order_id != '' "
        "ORDER BY id_transaccion ASC"
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


async def obtener_ordenes_point_pendientes_async():
    return await run_in_executor(_obtener_ordenes_point_pendientes)


def _guardar_mp_order_id(id_transaccion, mp_order_id):
    """Guarda el id de la orden Point en una fila recién creada (fallback)."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE transacciones SET mp_order_id = ? WHERE id_transaccion = ?",
        (mp_order_id, id_transaccion),
    )
    conn.commit()
    conn.close()


async def guardar_mp_order_id_async(id_transaccion, mp_order_id):
    await run_in_executor(_guardar_mp_order_id, id_transaccion, mp_order_id)


def _obtener_mp_order_id(id_transaccion):
    """Devuelve el mp_order_id de una transacción, o ''."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT mp_order_id FROM transacciones WHERE id_transaccion = ?",
        (id_transaccion,),
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else ""


async def obtener_mp_order_id_async(id_transaccion):
    return await run_in_executor(_obtener_mp_order_id, id_transaccion)


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


def _actualizar_tipo_servicio(id_transaccion, tipo_servicio):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE transacciones SET tipo_servicio=? WHERE id_transaccion=?",
        (tipo_servicio, id_transaccion),
    )
    conn.commit()
    conn.close()


async def actualizar_tipo_servicio_async(id_transaccion, tipo_servicio):
    await run_in_executor(_actualizar_tipo_servicio, id_transaccion, tipo_servicio)


async def actualizar_notas_async(id_transaccion, notas):
    await run_in_executor(_actualizar_notas, id_transaccion, notas)


# ── Servicios (catálogo data-driven) ─────────────────────────────────────────


def _listar_servicios(solo_activos: bool = True) -> list:
    conn = _get_connection()
    cursor = conn.cursor()
    if solo_activos:
        cursor.execute(
            "SELECT * FROM servicios WHERE activo = 1 ORDER BY orden ASC, id ASC"
        )
    else:
        cursor.execute("SELECT * FROM servicios ORDER BY orden ASC, id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


async def listar_servicios_async(solo_activos: bool = True) -> list:
    return await run_in_executor(_listar_servicios, solo_activos)


def _obtener_servicio_por_codigo(codigo: str) -> dict | None:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM servicios WHERE codigo = ?", (codigo,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


async def obtener_servicio_por_codigo_async(codigo: str) -> dict | None:
    return await run_in_executor(_obtener_servicio_por_codigo, codigo)


def _actualizar_servicio(
    id_servicio,
    nombre,
    tipo_calculo,
    precio_fijo,
    tarifa_por_kg,
    duracion_min,
    limite_kg,
    tipos_equipo,
    activo,
):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE servicios
        SET nombre = ?, tipo_calculo = ?, precio_fijo = ?, tarifa_por_kg = ?,
            duracion_min = ?, limite_kg = ?, tipos_equipo = ?, activo = ?
        WHERE id = ?
    """,
        (
            nombre,
            tipo_calculo,
            precio_fijo,
            tarifa_por_kg,
            duracion_min,
            limite_kg,
            tipos_equipo,
            1 if activo else 0,
            id_servicio,
        ),
    )
    conn.commit()
    conn.close()


async def actualizar_servicio_async(
    id_servicio,
    nombre,
    tipo_calculo,
    precio_fijo,
    tarifa_por_kg,
    duracion_min,
    limite_kg,
    tipos_equipo,
    activo,
):
    await run_in_executor(
        _actualizar_servicio,
        id_servicio,
        nombre,
        tipo_calculo,
        precio_fijo,
        tarifa_por_kg,
        duracion_min,
        limite_kg,
        tipos_equipo,
        activo,
    )


# ── Segmentaciones (variantes de un servicio) ────────────────────────────────


def _listar_segmentaciones(servicio_id=None, solo_activos=True) -> list:
    conn = _get_connection()
    cursor = conn.cursor()
    if servicio_id is not None:
        if solo_activos:
            cursor.execute(
                "SELECT * FROM segmentaciones "
                "WHERE servicio_id = ? AND activo = 1 "
                "ORDER BY orden ASC, id ASC",
                (servicio_id,),
            )
        else:
            cursor.execute(
                "SELECT * FROM segmentaciones WHERE servicio_id = ? "
                "ORDER BY orden ASC, id ASC",
                (servicio_id,),
            )
    else:
        if solo_activos:
            cursor.execute(
                "SELECT * FROM segmentaciones WHERE activo = 1 "
                "ORDER BY servicio_id, orden ASC, id ASC"
            )
        else:
            cursor.execute(
                "SELECT * FROM segmentaciones ORDER BY servicio_id, orden ASC, id ASC"
            )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


async def listar_segmentaciones_async(servicio_id=None, solo_activos=True) -> list:
    return await run_in_executor(_listar_segmentaciones, servicio_id, solo_activos)


def _obtener_segmentacion_por_id(id_seg) -> dict | None:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM segmentaciones WHERE id = ?", (id_seg,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


async def obtener_segmentacion_por_id_async(id_seg) -> dict | None:
    return await run_in_executor(_obtener_segmentacion_por_id, id_seg)


def _actualizar_segmentacion(
    id_seg,
    nombre,
    descripcion,
    tipo_calculo,
    precio_fijo,
    tarifa_por_kg,
    duracion_min,
    activo,
):
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE segmentaciones
        SET nombre = ?, descripcion = ?, tipo_calculo = ?, precio_fijo = ?,
            tarifa_por_kg = ?, duracion_min = ?, activo = ?
        WHERE id = ?
    """,
        (
            nombre,
            descripcion,
            tipo_calculo,
            precio_fijo,
            tarifa_por_kg,
            duracion_min,
            1 if activo else 0,
            id_seg,
        ),
    )
    conn.commit()
    conn.close()


async def actualizar_segmentacion_async(
    id_seg,
    nombre,
    descripcion,
    tipo_calculo,
    precio_fijo,
    tarifa_por_kg,
    duracion_min,
    activo,
):
    await run_in_executor(
        _actualizar_segmentacion,
        id_seg,
        nombre,
        descripcion,
        tipo_calculo,
        precio_fijo,
        tarifa_por_kg,
        duracion_min,
        activo,
    )


# ── Crear / eliminar servicios y segmentaciones ──────────────────────────────


def _crear_servicio(
    codigo,
    nombre,
    modalidad,
    icono,
    tipo_calculo,
    precio_fijo,
    tarifa_por_kg,
    duracion_min,
    limite_kg,
    tipos_equipo,
    orden=99,
    activo=1,
):
    conn = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO servicios
                (codigo, nombre, modalidad, icono, tipo_calculo, precio_fijo,
                 tarifa_por_kg, duracion_min, limite_kg, tipos_equipo, orden, activo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                codigo,
                nombre,
                modalidad,
                icono,
                tipo_calculo,
                precio_fijo,
                tarifa_por_kg,
                duracion_min,
                limite_kg,
                tipos_equipo,
                orden,
                activo,
            ),
        )
        conn.commit()
        new_id = cursor.lastrowid
        return new_id
    except sqlite3.IntegrityError as e:
        return None
    finally:
        conn.close()


async def crear_servicio_async(
    codigo,
    nombre,
    modalidad,
    icono,
    tipo_calculo,
    precio_fijo,
    tarifa_por_kg,
    duracion_min,
    limite_kg,
    tipos_equipo,
    orden=99,
    activo=True,
):
    return await run_in_executor(
        _crear_servicio,
        codigo,
        nombre,
        modalidad,
        icono,
        tipo_calculo,
        precio_fijo,
        tarifa_por_kg,
        duracion_min,
        limite_kg,
        tipos_equipo,
        orden,
        1 if activo else 0,
    )


def _eliminar_servicio_hard(id_servicio) -> bool:
    """Hard delete. Solo si no hay órdenes históricas referenciando este servicio.
    Si hay órdenes, devuelve False y se debe hacer soft delete (activo=0)."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM transacciones WHERE tipo_servicio IN "
        "(SELECT nombre FROM servicios WHERE id = ?) OR "
        "tipo_servicio LIKE (SELECT nombre FROM servicios WHERE id = ?) || ' %'",
        (id_servicio, id_servicio),
    )
    count = cursor.fetchone()[0]
    if count > 0:
        conn.close()
        return False
    # CASCADE borra segmentaciones asociadas
    cursor.execute("DELETE FROM servicios WHERE id = ?", (id_servicio,))
    conn.commit()
    conn.close()
    return True


async def eliminar_servicio_hard_async(id_servicio) -> bool:
    return await run_in_executor(_eliminar_servicio_hard, id_servicio)


def _crear_segmentacion(
    servicio_id,
    codigo,
    nombre,
    descripcion,
    tipo_calculo,
    precio_fijo,
    tarifa_por_kg,
    duracion_min,
    orden=99,
    activo=1,
):
    conn = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO segmentaciones
                (servicio_id, codigo, nombre, descripcion, tipo_calculo,
                 precio_fijo, tarifa_por_kg, duracion_min, orden, activo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                servicio_id,
                codigo,
                nombre,
                descripcion,
                tipo_calculo,
                precio_fijo,
                tarifa_por_kg,
                duracion_min,
                orden,
                activo,
            ),
        )
        conn.commit()
        new_id = cursor.lastrowid
        return new_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


async def crear_segmentacion_async(
    servicio_id,
    codigo,
    nombre,
    descripcion,
    tipo_calculo,
    precio_fijo,
    tarifa_por_kg,
    duracion_min,
    orden=99,
    activo=True,
):
    return await run_in_executor(
        _crear_segmentacion,
        servicio_id,
        codigo,
        nombre,
        descripcion,
        tipo_calculo,
        precio_fijo,
        tarifa_por_kg,
        duracion_min,
        orden,
        1 if activo else 0,
    )


def _eliminar_segmentacion_hard(id_seg) -> bool:
    """Hard delete. Solo si no hay órdenes referenciando esta segmentación."""
    conn = _get_connection()
    cursor = conn.cursor()
    # El nombre de la segmentación se concatena a tipo_servicio en finalizar_pago
    cursor.execute("SELECT nombre FROM segmentaciones WHERE id = ?", (id_seg,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    nombre = row[0]
    cursor.execute(
        "SELECT COUNT(*) FROM transacciones WHERE tipo_servicio LIKE ?",
        (f"% · {nombre}",),
    )
    count = cursor.fetchone()[0]
    if count > 0:
        conn.close()
        return False
    cursor.execute("DELETE FROM segmentaciones WHERE id = ?", (id_seg,))
    conn.commit()
    conn.close()
    return True


async def eliminar_segmentacion_hard_async(id_seg) -> bool:
    return await run_in_executor(_eliminar_segmentacion_hard, id_seg)


# ── Maquinas (catálogo de hardware) ─────────────────────────────────────────


def _listar_maquinas(solo_activas: bool = True) -> list:
    conn = _get_connection()
    cursor = conn.cursor()
    if solo_activas:
        cursor.execute(
            "SELECT * FROM maquinas WHERE activa = 1 ORDER BY orden ASC, id ASC"
        )
    else:
        cursor.execute("SELECT * FROM maquinas ORDER BY orden ASC, id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


async def listar_maquinas_async(solo_activas: bool = True) -> list:
    return await run_in_executor(_listar_maquinas, solo_activas)


def _obtener_maquina_por_codigo(codigo: str) -> dict | None:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM maquinas WHERE codigo = ?", (codigo,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


async def obtener_maquina_por_codigo_async(codigo: str) -> dict | None:
    return await run_in_executor(_obtener_maquina_por_codigo, codigo)


def _crear_maquina(
    codigo, nombre, tipo, capacidad_kg, gpio, modo, duracion_max_min, orden=99, activa=1
):
    conn = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO maquinas
                (codigo, nombre, tipo, capacidad_kg, gpio, modo,
                 duracion_max_min, orden, activa)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                codigo,
                nombre,
                tipo,
                capacidad_kg,
                gpio,
                modo,
                duracion_max_min,
                orden,
                activa,
            ),
        )
        conn.commit()
        new_id = cursor.lastrowid
        return new_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


async def crear_maquina_async(
    codigo,
    nombre,
    tipo,
    capacidad_kg,
    gpio,
    modo,
    duracion_max_min,
    orden=99,
    activa=True,
):
    return await run_in_executor(
        _crear_maquina,
        codigo,
        nombre,
        tipo,
        capacidad_kg,
        gpio,
        modo,
        duracion_max_min,
        orden,
        1 if activa else 0,
    )


def _actualizar_maquina(
    id_maquina,
    nombre,
    tipo,
    capacidad_kg,
    gpio,
    modo,
    duracion_max_min,
    orden,
    activa,
):
    conn = _get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            UPDATE maquinas
            SET nombre = ?, tipo = ?, capacidad_kg = ?, gpio = ?, modo = ?,
                duracion_max_min = ?, orden = ?, activa = ?
            WHERE id = ?
        """,
            (
                nombre,
                tipo,
                capacidad_kg,
                gpio,
                modo,
                duracion_max_min,
                orden,
                1 if activa else 0,
                id_maquina,
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


async def actualizar_maquina_async(
    id_maquina,
    nombre,
    tipo,
    capacidad_kg,
    gpio,
    modo,
    duracion_max_min,
    orden,
    activa,
):
    return await run_in_executor(
        _actualizar_maquina,
        id_maquina,
        nombre,
        tipo,
        capacidad_kg,
        gpio,
        modo,
        duracion_max_min,
        orden,
        activa,
    )


def _eliminar_maquina_hard(id_maquina) -> bool:
    """Hard delete solo si no hay órdenes referenciando esta máquina."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nombre FROM maquinas WHERE id = ?", (id_maquina,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    nombre = row[0]
    cursor.execute(
        "SELECT COUNT(*) FROM transacciones WHERE id_equipo = ? AND "
        "id_equipo != '' AND id_equipo IS NOT NULL",
        (nombre,),
    )
    count = cursor.fetchone()[0]
    if count > 0:
        conn.close()
        return False
    cursor.execute("DELETE FROM maquinas WHERE id = ?", (id_maquina,))
    conn.commit()
    conn.close()
    return True


async def eliminar_maquina_hard_async(id_maquina) -> bool:
    return await run_in_executor(_eliminar_maquina_hard, id_maquina)


def _existe_gpio(gpio, id_excluir=None) -> bool:
    """Devuelve True si el GPIO ya está usado por otra máquina."""
    conn = _get_connection()
    cursor = conn.cursor()
    if id_excluir is not None:
        cursor.execute(
            "SELECT COUNT(*) FROM maquinas WHERE gpio = ? AND id != ?",
            (gpio, id_excluir),
        )
    else:
        cursor.execute("SELECT COUNT(*) FROM maquinas WHERE gpio = ?", (gpio,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


async def existe_gpio_async(gpio, id_excluir=None) -> bool:
    return await run_in_executor(_existe_gpio, gpio, id_excluir)


# ── Respaldo de fábrica (default) ────────────────────────────────────────────


def _listar_backups() -> list:
    """Devuelve los snapshots de fábrica guardados."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tabla, created_at, nota FROM _backup_default ORDER BY tabla")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


async def listar_backups_async() -> list:
    return await run_in_executor(_listar_backups)


def _obtener_backup(tabla: str) -> dict | None:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT datos, created_at, nota FROM _backup_default WHERE tabla = ?",
        (tabla,),
    )
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "tabla": tabla,
        "datos": json.loads(row[0]),
        "created_at": row[1],
        "nota": row[2],
    }


async def obtener_backup_async(tabla: str) -> dict | None:
    return await run_in_executor(_obtener_backup, tabla)


def _crear_backup(tabla: str, nota: str = "") -> int:
    """Sobrescribe el snapshot de fábrica con el estado actual de la tabla.
    Devuelve la cantidad de filas guardadas, o -1 si la tabla no existe."""
    tablas_validas = {"servicios", "segmentaciones", "maquinas"}
    if tabla not in tablas_validas:
        return -1
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tabla,)
    )
    if not cursor.fetchone():
        conn.close()
        return -1
    cursor.execute(f"SELECT * FROM {tabla}")
    cols = [d[0] for d in cursor.description]
    rows = [dict(zip(cols, r)) for r in cursor.fetchall()]
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT INTO _backup_default (tabla, datos, created_at, nota)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(tabla) DO UPDATE SET
            datos = excluded.datos,
            created_at = excluded.created_at,
            nota = excluded.nota
    """,
        (
            tabla,
            json.dumps(rows, default=str, ensure_ascii=False),
            ahora,
            nota or f"Respaldo manual",
        ),
    )
    conn.commit()
    conn.close()
    return len(rows)


async def crear_backup_async(tabla: str, nota: str = "") -> int:
    return await run_in_executor(_crear_backup, tabla, nota)


def _restaurar_backup(tabla: str) -> tuple[bool, int]:
    """Restaura la tabla al estado de fábrica. Borra lo actual y reinserta.
    Devuelve (ok, filas_restauradas)."""
    tablas_validas = {"servicios", "segmentaciones", "maquinas"}
    if tabla not in tablas_validas:
        return (False, 0)
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT datos FROM _backup_default WHERE tabla = ?", (tabla,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return (False, 0)
    try:
        filas = json.loads(row[0])
    except (ValueError, TypeError):
        conn.close()
        return (False, 0)
    if not filas:
        conn.close()
        return (True, 0)
    # Detectar columnas a partir de la primera fila
    columnas = list(filas[0].keys())
    placeholders = ",".join(["?"] * len(columnas))
    cols_csv = ",".join(columnas)
    try:
        cursor.execute(f"DELETE FROM {tabla}")
        cursor.executemany(
            f"INSERT INTO {tabla} ({cols_csv}) VALUES ({placeholders})",
            [tuple(f.get(c) for c in columnas) for f in filas],
        )
        conn.commit()
        n = len(filas)
    except Exception as e:
        print(f"[backup] Error restaurando {tabla}: {e}")
        conn.rollback()
        conn.close()
        return (False, 0)
    conn.close()
    return (True, n)


async def restaurar_backup_async(tabla: str) -> tuple[bool, int]:
    return await run_in_executor(_restaurar_backup, tabla)


def _crear_backup_completo(nota: str = "") -> dict:
    """Crea snapshot de las 3 tablas. Devuelve {tabla: n_filas}."""
    resultado = {}
    for t in ("servicios", "segmentaciones", "maquinas"):
        resultado[t] = _crear_backup(t, nota)
    return resultado


async def crear_backup_completo_async(nota: str = "") -> dict:
    return await run_in_executor(_crear_backup_completo, nota)


def _restaurar_backup_completo() -> dict:
    resultado = {}
    for t in ("servicios", "segmentaciones", "maquinas"):
        ok, n = _restaurar_backup(t)
        resultado[t] = {"ok": ok, "filas": n}
    return resultado


async def restaurar_backup_completo_async() -> dict:
    return await run_in_executor(_restaurar_backup_completo)


# ── Reportes analíticos para métricas ────────────────────────────────────────


def _parse_fecha(fecha_str: str) -> str:
    """Acepta 'YYYY-MM-DD' o 'YYYY-MM-DD HH:MM:SS' y devuelve la forma
    con la que se compara en SQL (YYYY-MM-DD HH:MM:SS)."""
    if not fecha_str:
        return "1970-01-01 00:00:00"
    if len(fecha_str) == 10:
        return f"{fecha_str} 00:00:00"
    return fecha_str


def _reporte_uso_por_maquina(fecha_desde: str = "", fecha_hasta: str = "") -> list:
    """Devuelve [{maquina, servicios, kg, minutos}] ordenado por servicios desc."""
    fd = _parse_fecha(fecha_desde)
    fh = _parse_fecha(fecha_hasta) if fecha_hasta else "9999-12-31 23:59:59"
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id_equipo,
               COUNT(*) AS n_servicios,
               COALESCE(SUM(peso_kg), 0) AS total_kg,
               COALESCE(SUM(duracion_estimada_min), 0) AS total_min
        FROM transacciones
        WHERE estado IN ('En proceso', 'Completado', 'Pendiente')
          AND id_equipo IS NOT NULL AND id_equipo != ''
          AND fecha_hora >= ? AND fecha_hora <= ?
        GROUP BY id_equipo
        ORDER BY n_servicios DESC
    """,
        (fd, fh),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


async def reporte_uso_por_maquina_async(fecha_desde="", fecha_hasta="") -> list:
    return await run_in_executor(_reporte_uso_por_maquina, fecha_desde, fecha_hasta)


def _reporte_horas_pico(fecha_desde: str = "", fecha_hasta: str = "") -> list:
    """24 buckets: hora del día (0-23) → número de servicios."""
    fd = _parse_fecha(fecha_desde)
    fh = _parse_fecha(fecha_hasta) if fecha_hasta else "9999-12-31 23:59:59"
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT CAST(strftime('%H', fecha_hora) AS INTEGER) AS hora,
               COUNT(*) AS n
        FROM transacciones
        WHERE fecha_hora >= ? AND fecha_hora <= ?
          AND estado NOT IN ('Pendiente-peso')
        GROUP BY hora
        ORDER BY hora
    """,
        (fd, fh),
    )
    rows = {r[0]: r[1] for r in cursor.fetchall()}
    conn.close()
    return [{"hora": h, "n": rows.get(h, 0)} for h in range(24)]


async def reporte_horas_pico_async(fecha_desde="", fecha_hasta="") -> list:
    return await run_in_executor(_reporte_horas_pico, fecha_desde, fecha_hasta)


def _reporte_dias_pico(fecha_desde: str = "", fecha_hasta: str = "") -> list:
    """7 buckets: día de la semana (0=Dom, 6=Sáb) → número de servicios."""
    fd = _parse_fecha(fecha_desde)
    fh = _parse_fecha(fecha_hasta) if fecha_hasta else "9999-12-31 23:59:59"
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT CAST(strftime('%w', fecha_hora) AS INTEGER) AS dow,
               COUNT(*) AS n
        FROM transacciones
        WHERE fecha_hora >= ? AND fecha_hora <= ?
          AND estado NOT IN ('Pendiente-peso')
        GROUP BY dow
        ORDER BY dow
    """,
        (fd, fh),
    )
    rows = {r[0]: r[1] for r in cursor.fetchall()}
    conn.close()
    nombres = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"]
    return [{"dow": d, "nombre": nombres[d], "n": rows.get(d, 0)} for d in range(7)]


async def reporte_dias_pico_async(fecha_desde="", fecha_hasta="") -> list:
    return await run_in_executor(_reporte_dias_pico, fecha_desde, fecha_hasta)


def _reporte_consumo_promedio(fecha_desde: str = "", fecha_hasta: str = "") -> list:
    """Devuelve [{tipo_servicio, n, kg_prom, kg_total, monto_prom, monto_total}]."""
    fd = _parse_fecha(fecha_desde)
    fh = _parse_fecha(fecha_hasta) if fecha_hasta else "9999-12-31 23:59:59"
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT tipo_servicio,
               COUNT(*) AS n,
               COALESCE(AVG(peso_kg), 0) AS kg_prom,
               COALESCE(SUM(peso_kg), 0) AS kg_total,
               COALESCE(AVG(monto_pagado), 0) AS monto_prom,
               COALESCE(SUM(monto_pagado), 0) AS monto_total
        FROM transacciones
        WHERE fecha_hora >= ? AND fecha_hora <= ?
          AND estado NOT IN ('Pendiente-peso')
          AND tipo_servicio IS NOT NULL AND tipo_servicio != ''
        GROUP BY tipo_servicio
        ORDER BY n DESC
    """,
        (fd, fh),
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "tipo_servicio": r[0],
            "n": r[1],
            "kg_prom": round(r[2] or 0, 2),
            "kg_total": round(r[3] or 0, 2),
            "monto_prom": round(r[4] or 0, 2),
            "monto_total": round(r[5] or 0, 2),
        }
        for r in rows
    ]


async def reporte_consumo_promedio_async(fecha_desde="", fecha_hasta="") -> list:
    return await run_in_executor(_reporte_consumo_promedio, fecha_desde, fecha_hasta)


def _reporte_tasa_pago(fecha_desde: str = "", fecha_hasta: str = "") -> list:
    """Devuelve [{metodo, n, monto_total}] agrupado por mes y método.
    Mapeo: 'monedas' → efectivo, 'point' → tarjeta, 'terminal' → tarjeta,
    'pendiente-pago' / 'mostrador' → efectivo mostrador."""
    fd = _parse_fecha(fecha_desde)
    fh = _parse_fecha(fecha_hasta) if fecha_hasta else "9999-12-31 23:59:59"
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT substr(fecha_hora, 1, 7) AS mes,
               modalidad,
               COUNT(*) AS n,
               COALESCE(SUM(monto_pagado), 0) AS total
        FROM transacciones
        WHERE fecha_hora >= ? AND fecha_hora <= ?
          AND estado IN ('Pendiente', 'En proceso', 'Completado')
          AND modalidad IS NOT NULL AND modalidad != ''
        GROUP BY mes, modalidad
        ORDER BY mes
    """,
        (fd, fh),
    )
    rows = cursor.fetchall()
    conn.close()

    def clasificar(modalidad: str) -> str:
        if not modalidad:
            return "Otros"
        if "monedas" in modalidad:
            return "Efectivo"
        if "point" in modalidad:
            return "Tarjeta (Point)"
        if "terminal" in modalidad:
            return "Tarjeta (Terminal)"
        if "pendiente-pago" in modalidad or "mostrador" in modalidad:
            return "Efectivo (mostrador)"
        return "Otros"

    por_mes = {}
    for mes, mod, n, total in rows:
        metodo = clasificar(mod)
        if mes not in por_mes:
            por_mes[mes] = {
                "mes": mes,
                "Efectivo": 0,
                "Tarjeta (Point)": 0,
                "Tarjeta (Terminal)": 0,
                "Efectivo (mostrador)": 0,
                "Otros": 0,
                "n": 0,
                "monto_total": 0,
            }
        por_mes[mes][metodo] = (por_mes[mes].get(metodo, 0) or 0) + (total or 0)
        por_mes[mes]["n"] += n
        por_mes[mes]["monto_total"] += total or 0
    return sorted(por_mes.values(), key=lambda r: r["mes"])


async def reporte_tasa_pago_async(fecha_desde="", fecha_hasta="") -> list:
    return await run_in_executor(_reporte_tasa_pago, fecha_desde, fecha_hasta)


def _reporte_resumen(fecha_desde: str = "", fecha_hasta: str = "") -> dict:
    """Totales globales para KPI cards."""
    fd = _parse_fecha(fecha_desde)
    fh = _parse_fecha(fecha_hasta) if fecha_hasta else "9999-12-31 23:59:59"
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) AS n_orden,
               COALESCE(SUM(monto_pagado), 0) AS recaudado,
               COALESCE(SUM(peso_kg), 0) AS kg_total,
               COALESCE(AVG(peso_kg), 0) AS kg_prom
        FROM transacciones
        WHERE fecha_hora >= ? AND fecha_hora <= ?
          AND estado NOT IN ('Pendiente-peso')
    """,
        (fd, fh),
    )
    row = cursor.fetchone()
    conn.close()
    return {
        "n_orden": row[0] or 0,
        "recaudado": round(row[1] or 0, 2),
        "kg_total": round(row[2] or 0, 2),
        "kg_prom": round(row[3] or 0, 2),
    }


async def reporte_resumen_async(fecha_desde="", fecha_hasta="") -> dict:
    return await run_in_executor(_reporte_resumen, fecha_desde, fecha_hasta)


# ── Cortes de caja ───────────────────────────────────────────────────────────


def _obtener_corte_activo() -> dict | None:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM cortes_caja WHERE estado = 'abierto' ORDER BY id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


async def obtener_corte_activo_async() -> dict | None:
    return await run_in_executor(_obtener_corte_activo)


def _abrir_corte(fecha: str, usuario: str, saldo_inicial: int) -> dict:
    """Abre un nuevo corte. Si ya hay uno abierto, devuelve error."""
    if saldo_inicial < 0:
        return {"ok": False, "error": "El saldo inicial no puede ser negativo."}
    if _obtener_corte_activo() is not None:
        return {
            "ok": False,
            "error": "Ya hay una caja abierta. Ciérrala antes de abrir otra.",
        }
    conn = _get_connection()
    cursor = conn.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute(
            """
            INSERT INTO cortes_caja
                (fecha, usuario_apertura, saldo_inicial, estado, hora_apertura)
            VALUES (?, ?, ?, 'abierto', ?)
        """,
            (fecha, usuario, saldo_inicial, ahora),
        )
        conn.commit()
        new_id = cursor.lastrowid
    except Exception as e:
        conn.close()
        return {"ok": False, "error": str(e)}
    conn.close()
    return {"ok": True, "id": new_id}


async def abrir_corte_async(fecha: str, usuario: str, saldo_inicial: int) -> dict:
    return await run_in_executor(_abrir_corte, fecha, usuario, saldo_inicial)


def _cerrar_corte(id_corte: int, usuario: str, saldo_real: int, notas: str) -> dict:
    conn = _get_connection()
    cursor = conn.cursor()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if saldo_real < 0:
        conn.close()
        return {"ok": False, "error": "El saldo real no puede ser negativo."}
    cursor.execute(
        "SELECT saldo_inicial FROM cortes_caja WHERE id = ? AND estado = 'abierto'",
        (id_corte,),
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"ok": False, "error": "Corte no encontrado o ya cerrado."}
    saldo_inicial = row[0]
    cursor.execute(
        "SELECT "
        "COALESCE(SUM(CASE WHEN tipo='ingreso' THEN monto ELSE 0 END), 0) AS ingresos, "
        "COALESCE(SUM(CASE WHEN tipo='egreso' THEN monto ELSE 0 END), 0) AS egresos "
        "FROM movimientos_caja WHERE corte_id = ?",
        (id_corte,),
    )
    mov = cursor.fetchone()
    ingresos = mov[0] or 0
    egresos = mov[1] or 0
    saldo_esperado = saldo_inicial + ingresos - egresos
    diferencia = saldo_real - saldo_esperado
    try:
        cursor.execute(
            """
            UPDATE cortes_caja
            SET estado = 'cerrado', usuario_cierre = ?, saldo_real = ?,
                saldo_esperado = ?, diferencia = ?, notas = ?, hora_cierre = ?
            WHERE id = ? AND estado = 'abierto'
        """,
            (usuario, saldo_real, saldo_esperado, diferencia, notas, ahora, id_corte),
        )
        conn.commit()
    except Exception as e:
        conn.close()
        return {"ok": False, "error": str(e)}
    conn.close()
    return {
        "ok": True,
        "id": id_corte,
        "saldo_inicial": saldo_inicial,
        "ingresos": ingresos,
        "egresos": egresos,
        "saldo_esperado": saldo_esperado,
        "saldo_real": saldo_real,
        "diferencia": diferencia,
    }


async def cerrar_corte_async(
    id_corte: int, usuario: str, saldo_real: int, notas: str
) -> dict:
    return await run_in_executor(_cerrar_corte, id_corte, usuario, saldo_real, notas)


def _listar_cortes(limite: int = 30) -> list:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cortes_caja ORDER BY id DESC LIMIT ?", (limite,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


async def listar_cortes_async(limite: int = 30) -> list:
    return await run_in_executor(_listar_cortes, limite)


def _registrar_movimiento(
    corte_id: int,
    tipo: str,
    monto: int,
    concepto: str,
    usuario: str,
    notas: str = "",
    auto: int = 0,
) -> dict:
    if tipo not in ("ingreso", "egreso"):
        return {"ok": False, "error": "Tipo inválido (ingreso|egreso)."}
    if monto <= 0:
        return {"ok": False, "error": "El monto debe ser mayor a 0."}
    if not concepto.strip():
        return {"ok": False, "error": "El concepto es obligatorio."}
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, estado FROM cortes_caja WHERE id = ?", (corte_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"ok": False, "error": "Corte no encontrado."}
    if row[1] != "abierto":
        conn.close()
        return {"ok": False, "error": "La caja está cerrada."}
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute(
            """
            INSERT INTO movimientos_caja
                (corte_id, fecha_hora, tipo, monto, concepto, usuario, notas, auto)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (corte_id, ahora, tipo, monto, concepto.strip(), usuario, notas, auto),
        )
        conn.commit()
        new_id = cursor.lastrowid
    except Exception as e:
        conn.close()
        return {"ok": False, "error": str(e)}
    conn.close()
    return {"ok": True, "id": new_id}


async def registrar_movimiento_async(
    corte_id: int,
    tipo: str,
    monto: int,
    concepto: str,
    usuario: str,
    notas: str = "",
    auto: int = 0,
) -> dict:
    return await run_in_executor(
        _registrar_movimiento, corte_id, tipo, monto, concepto, usuario, notas, auto
    )


def _listar_movimientos(corte_id: int) -> list:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM movimientos_caja WHERE corte_id = ? ORDER BY id ASC",
        (corte_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


async def listar_movimientos_async(corte_id: int) -> list:
    return await run_in_executor(_listar_movimientos, corte_id)
