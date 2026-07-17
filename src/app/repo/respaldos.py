"""Repositorio de respaldos de fábrica (snapshot JSON de catálogos)."""

import json
from datetime import datetime
from typing import Optional

from app.repo import db

_TABLAS_VALIDAS = {"servicios", "segmentaciones", "maquinas"}


def _listar() -> list:
    conn = db.conectar()
    rows = conn.execute(
        "SELECT tabla, created_at, nota FROM _backup_default ORDER BY tabla"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


async def listar() -> list:
    return await db.run_in_executor(_listar)


def _obtener(tabla: str) -> Optional[dict]:
    if tabla not in _TABLAS_VALIDAS:
        return None
    conn = db.conectar()
    row = conn.execute(
        "SELECT datos, created_at, nota FROM _backup_default WHERE tabla = ?",
        (tabla,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "tabla": tabla,
        "datos": json.loads(row["datos"]),
        "created_at": row["created_at"],
        "nota": row["nota"],
    }


async def obtener(tabla: str) -> Optional[dict]:
    return await db.run_in_executor(_obtener, tabla)


def _crear(tabla: str, nota: str = "") -> int:
    """Sobrescribe el snapshot con el estado actual. Devuelve filas guardadas,
    o -1 si la tabla no es válida o no existe."""
    if tabla not in _TABLAS_VALIDAS:
        return -1
    conn = db.conectar()
    if not conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (tabla,),
    ).fetchone():
        conn.close()
        return -1
    rows = conn.execute(f"SELECT * FROM {tabla}").fetchall()
    cols = [d[0] for d in conn.execute(f"SELECT * FROM {tabla} LIMIT 0").description]
    filas = [dict(zip(cols, r)) for r in rows]
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
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
            json.dumps(filas, default=str, ensure_ascii=False),
            ahora,
            nota or "Respaldo manual",
        ),
    )
    conn.commit()
    conn.close()
    return len(filas)


async def crear(tabla: str, nota: str = "") -> int:
    return await db.run_in_executor(_crear, tabla, nota)


def _restaurar(tabla: str) -> tuple:
    """Borra y reinserta desde el snapshot. Devuelve (ok, filas_restauradas)."""
    if tabla not in _TABLAS_VALIDAS:
        return (False, 0)
    conn = db.conectar()
    row = conn.execute(
        "SELECT datos FROM _backup_default WHERE tabla = ?", (tabla,)
    ).fetchone()
    if not row:
        conn.close()
        return (False, 0)
    try:
        filas = json.loads(row["datos"])
    except (ValueError, TypeError):
        conn.close()
        return (False, 0)
    if not filas:
        conn.close()
        return (True, 0)
    columnas = list(filas[0].keys())
    placeholders = ",".join(["?"] * len(columnas))
    cols_csv = ",".join(columnas)
    try:
        conn.execute(f"DELETE FROM {tabla}")
        conn.executemany(
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


async def restaurar(tabla: str) -> tuple:
    return await db.run_in_executor(_restaurar, tabla)


def _crear_completo(nota: str = "") -> dict:
    return {t: _crear(t, nota) for t in _TABLAS_VALIDAS}


async def crear_completo(nota: str = "") -> dict:
    return await db.run_in_executor(_crear_completo, nota)


def _restaurar_completo() -> dict:
    return {
        t: {"ok": _restaurar(t)[0], "filas": _restaurar(t)[1]} for t in _TABLAS_VALIDAS
    }


async def restaurar_completo() -> dict:
    return await db.run_in_executor(_restaurar_completo)
