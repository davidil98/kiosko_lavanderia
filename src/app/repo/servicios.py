"""Repositorio de servicios (catálogo data-driven)."""

import sqlite3
from typing import Optional

from app.repo import db
from ._row_a import servicio


def _listar(solo_activos: bool = True) -> list:
    conn = db.conectar()
    if solo_activos:
        rows = conn.execute(
            "SELECT * FROM servicios WHERE activo = 1 ORDER BY orden ASC, id ASC"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM servicios ORDER BY orden ASC, id ASC"
        ).fetchall()
    conn.close()
    return [servicio(r) for r in rows]


async def listar(solo_activos: bool = True) -> list:
    return await db.run_in_executor(_listar, solo_activos)


def _obtener_por_codigo(codigo: str):
    conn = db.conectar()
    row = conn.execute("SELECT * FROM servicios WHERE codigo = ?", (codigo,)).fetchone()
    conn.close()
    return servicio(row) if row else None


async def obtener_por_codigo(codigo: str):
    return await db.run_in_executor(_obtener_por_codigo, codigo)


def _obtener_por_id(id_servicio: int):
    conn = db.conectar()
    row = conn.execute(
        "SELECT * FROM servicios WHERE id = ?", (id_servicio,)
    ).fetchone()
    conn.close()
    return servicio(row) if row else None


async def obtener_por_id(id_servicio: int):
    return await db.run_in_executor(_obtener_por_id, id_servicio)


def _actualizar(
    id_servicio: int,
    *,
    nombre: str,
    tipo_calculo: str,
    precio_fijo: int,
    tarifa_por_kg: float,
    duracion_min: int,
    limite_kg: Optional[int],
    tipos_equipo: str,
    activo: bool,
) -> None:
    conn = db.conectar()
    conn.execute(
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


async def actualizar(id_servicio: int, **kwargs) -> None:
    await db.run_in_executor(_actualizar, id_servicio, **kwargs)


def _crear(
    *,
    codigo: str,
    nombre: str,
    modalidad: str,
    icono: str,
    tipo_calculo: str,
    precio_fijo: int,
    tarifa_por_kg: float,
    duracion_min: int,
    limite_kg: Optional[int],
    tipos_equipo: str,
    orden: int = 99,
    activo: bool = True,
) -> Optional[int]:
    conn = db.conectar()
    try:
        cur = conn.execute(
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
                1 if activo else 0,
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


def _eliminar_hard(id_servicio: int) -> bool:
    """Borra solo si no hay órdenes históricas referenciando este servicio."""
    conn = db.conectar()
    cur = conn.execute(
        "SELECT COUNT(*) AS c FROM transacciones WHERE tipo_servicio IN "
        "(SELECT nombre FROM servicios WHERE id = ?) OR "
        "tipo_servicio LIKE (SELECT nombre FROM servicios WHERE id = ?) || ' %'",
        (id_servicio, id_servicio),
    )
    if cur.fetchone()["c"] > 0:
        conn.close()
        return False
    conn.execute("DELETE FROM servicios WHERE id = ?", (id_servicio,))
    conn.commit()
    conn.close()
    return True


async def eliminar_hard(id_servicio: int) -> bool:
    return await db.run_in_executor(_eliminar_hard, id_servicio)
