"""Repositorio de máquinas (catálogo de hardware)."""

import sqlite3
from typing import Optional

from app.repo import db
from ._row_a import maquina


def _listar(solo_activas: bool = True) -> list:
    conn = db.conectar()
    if solo_activas:
        rows = conn.execute(
            "SELECT * FROM maquinas WHERE activa = 1 ORDER BY orden ASC, id ASC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM maquinas ORDER BY orden ASC, id ASC"
        ).fetchall()
    conn.close()
    return [maquina(r) for r in rows]


async def listar(solo_activas: bool = True) -> list:
    return await db.run_in_executor(_listar, solo_activas)


def _obtener_por_codigo(codigo: str):
    conn = db.conectar()
    row = conn.execute("SELECT * FROM maquinas WHERE codigo = ?", (codigo,)).fetchone()
    conn.close()
    return maquina(row) if row else None


async def obtener_por_codigo(codigo: str):
    return await db.run_in_executor(_obtener_por_codigo, codigo)


def _obtener_por_id(id_maquina: int):
    conn = db.conectar()
    row = conn.execute("SELECT * FROM maquinas WHERE id = ?", (id_maquina,)).fetchone()
    conn.close()
    return maquina(row) if row else None


async def obtener_por_id(id_maquina: int):
    return await db.run_in_executor(_obtener_por_id, id_maquina)


def _crear(
    *,
    codigo: str,
    nombre: str,
    tipo: str,
    capacidad_kg: int,
    gpio: int,
    modo: str,
    duracion_max_min: int,
    orden: int = 99,
    activa: bool = True,
) -> Optional[int]:
    # Decisión del usuario: no permitir GPIO duplicado.
    if _existe_gpio(gpio):
        return None
    conn = db.conectar()
    try:
        cur = conn.execute(
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
                1 if activa else 0,
            ),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


async def crear(**kwargs) -> Optional[int]:
    return await db.run_in_executor(_crear, **kwargs)


def _actualizar(
    id_maquina: int,
    *,
    nombre: str,
    tipo: str,
    capacidad_kg: int,
    gpio: int,
    modo: str,
    duracion_max_min: int,
    orden: int,
    activa: bool,
) -> bool:
    conn = db.conectar()
    try:
        conn.execute(
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


async def actualizar(id_maquina: int, **kwargs) -> bool:
    return await db.run_in_executor(_actualizar, id_maquina, **kwargs)


def _eliminar_hard(id_maquina: int) -> bool:
    """Borra solo si no hay órdenes referenciando esta máquina."""
    conn = db.conectar()
    row = conn.execute(
        "SELECT nombre FROM maquinas WHERE id = ?", (id_maquina,)
    ).fetchone()
    if not row:
        conn.close()
        return False
    nombre = row["nombre"]
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM transacciones WHERE id_equipo = ? "
        "AND id_equipo != '' AND id_equipo IS NOT NULL",
        (nombre,),
    ).fetchone()["c"]
    if count > 0:
        conn.close()
        return False
    conn.execute("DELETE FROM maquinas WHERE id = ?", (id_maquina,))
    conn.commit()
    conn.close()
    return True


async def eliminar_hard(id_maquina: int) -> bool:
    return await db.run_in_executor(_eliminar_hard, id_maquina)


def _existe_gpio(gpio: int, id_excluir: Optional[int] = None) -> bool:
    conn = db.conectar()
    if id_excluir is not None:
        n = conn.execute(
            "SELECT COUNT(*) AS c FROM maquinas WHERE gpio = ? AND id != ?",
            (gpio, id_excluir),
        ).fetchone()["c"]
    else:
        n = conn.execute(
            "SELECT COUNT(*) AS c FROM maquinas WHERE gpio = ?", (gpio,)
        ).fetchone()["c"]
    conn.close()
    return n > 0


async def existe_gpio(gpio: int, id_excluir: Optional[int] = None) -> bool:
    return await db.run_in_executor(_existe_gpio, gpio, id_excluir)
