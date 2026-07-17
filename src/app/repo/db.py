"""Conexión, migraciones y seeds de la base de datos.

`init_db()` es idempotente: crea tablas, aplica migraciones aditivas y siembra
catálogos solo si están vacíos. Los datos existentes nunca se tocan.
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH: Optional[Path] = None
_TEST_PATH: Optional[Path] = None

_ESQUEMA = """
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
    modalidad TEXT DEFAULT 'autoservicio',
    numero_transaccion_terminal TEXT DEFAULT '',
    validado_por TEXT DEFAULT '',
    mp_order_id TEXT DEFAULT ''
);

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
);

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
);

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
);

CREATE TABLE IF NOT EXISTS _backup_default (
    tabla TEXT PRIMARY KEY,
    datos TEXT NOT NULL,
    created_at TEXT NOT NULL,
    nota TEXT DEFAULT ''
);

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
);

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
);

CREATE INDEX IF NOT EXISTS idx_mov_corte ON movimientos_caja(corte_id);
CREATE INDEX IF NOT EXISTS idx_cortes_estado ON cortes_caja(estado);
"""

_MIGRACIONES_ADITIVAS = [
    ("transacciones", "peso_kg", "REAL    DEFAULT 0"),
    ("transacciones", "notas", "TEXT    DEFAULT ''"),
    ("transacciones", "etapa_kanban", "TEXT    DEFAULT NULL"),
    ("transacciones", "modalidad", "TEXT    DEFAULT 'autoservicio'"),
    ("transacciones", "numero_transaccion_terminal", "TEXT    DEFAULT ''"),
    ("transacciones", "validado_por", "TEXT    DEFAULT ''"),
    ("transacciones", "mp_order_id", "TEXT    DEFAULT ''"),
]

_SERVICIOS_SEED = [
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

_MAQUINAS_SEED = [
    ("lavasecadora_1", "Lavasecadora 1", "mixto", 5, 17, "pulso", 25, 1, 1),
    ("lavasecadora_2", "Lavasecadora 2", "mixto", 5, 18, "pulso", 25, 1, 2),
    ("lavasecadora_3", "Lavasecadora 3", "mixto", 5, 4, "sostenido", 25, 1, 3),
    ("secadora_1", "Secadora 1", "secado", 5, 23, "sostenido", 40, 1, 4),
]


def usar_path_test(path: Path) -> None:
    """Redirige la conexión a un archivo temporal (solo para tests)."""
    global DB_PATH, _TEST_PATH
    _TEST_PATH = path
    DB_PATH = path


def _path() -> Path:
    if _TEST_PATH is not None:
        return _TEST_PATH
    if DB_PATH is None:
        from app.config import DB_PATH as _cfg

        return _cfg
    return DB_PATH


def init_db() -> None:
    """Crea archivo, aplica migraciones y siembra catálogos vacíos. Idempotente."""
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    cursor = conn.cursor()
    cursor.executescript(_ESQUEMA)

    for tabla, col, definicion in _MIGRACIONES_ADITIVAS:
        cursor.execute(f"PRAGMA table_info({tabla})")
        existentes = {row[1] for row in cursor.fetchall()}
        if col not in existentes:
            cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {definicion}")

    _sembrar_si_vacio(
        cursor,
        "servicios",
        _SERVICIOS_SEED,
        [
            "codigo",
            "nombre",
            "modalidad",
            "icono",
            "tipo_calculo",
            "precio_fijo",
            "tarifa_por_kg",
            "duracion_min",
            "limite_kg",
            "tipos_equipo",
            "orden",
            "activo",
        ],
    )

    _sembrar_segmentaciones(cursor)
    _sembrar_si_vacio(
        cursor,
        "maquinas",
        _MAQUINAS_SEED,
        [
            "codigo",
            "nombre",
            "tipo",
            "capacidad_kg",
            "gpio",
            "modo",
            "duracion_max_min",
            "activa",
            "orden",
        ],
    )

    _sembrar_backup_inicial(cursor)

    conn.commit()
    conn.close()


def _sembrar_si_vacio(cursor, tabla: str, filas: list, columnas: list) -> None:
    cursor.execute(f"SELECT COUNT(*) FROM {tabla}")
    if cursor.fetchone()[0] != 0:
        return
    if not filas:
        return
    placeholders = ",".join(["?"] * len(columnas))
    cols_csv = ",".join(columnas)
    cursor.executemany(
        f"INSERT INTO {tabla} ({cols_csv}) VALUES ({placeholders})",
        filas,
    )


def _sembrar_segmentaciones(cursor) -> None:
    cursor.execute("SELECT COUNT(*) FROM segmentaciones")
    if cursor.fetchone()[0] != 0:
        return
    cursor.execute("SELECT id, codigo FROM servicios")
    srv_id = {row[1]: row[0] for row in cursor.fetchall()}
    seg_seed: list = []
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


def _sembrar_backup_inicial(cursor) -> None:
    cursor.execute("SELECT COUNT(*) FROM _backup_default")
    if cursor.fetchone()[0] != 0:
        return
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for tabla in ("servicios", "segmentaciones", "maquinas"):
        cursor.execute(f"SELECT * FROM {tabla}")
        cols = [d[0] for d in cursor.description]
        filas = [dict(zip(cols, r)) for r in cursor.fetchall()]
        cursor.execute(
            "INSERT INTO _backup_default (tabla, datos, created_at, nota) VALUES (?, ?, ?, ?)",
            (
                tabla,
                json.dumps(filas, default=str, ensure_ascii=False),
                ahora,
                "Snapshot inicial de fábrica",
            ),
        )


def conectar() -> sqlite3.Connection:
    """Abre una conexión con Row factory y WAL activo. Cierra con conn.close()."""
    path = _path()
    conn = sqlite3.connect(path, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn


async def run_in_executor(func, *args, **kwargs):
    """Ejecuta una función bloqueante en el threadpool del event loop."""
    import asyncio

    if kwargs:
        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: func(*args, **kwargs)
        )
    return await asyncio.get_event_loop().run_in_executor(None, func, *args)
