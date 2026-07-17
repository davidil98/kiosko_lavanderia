"""Repositorio de segmentaciones (variantes de un servicio)."""

import sqlite3
from typing import Optional

from app.repo import db
from ._row_a import segmentacion


def _listar(servicio_id: Optional[int] = None, solo_activos: bool = True) -> list:
    conn = db.conectar()
    if servicio_id is not None:
        if solo_activos:
            rows = conn.execute(
                "SELECT * FROM segmentaciones WHERE servicio_id = ? AND activo = 1 "
                "ORDER BY orden ASC, id ASC",
                (servicio_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM segmentaciones WHERE servicio_id = ? "
                "ORDER BY orden ASC, id ASC",
                (servicio_id,),
            ).fetchall()
    else:
        if solo_activos:
            rows = conn.execute(
                "SELECT * FROM segmentaciones WHERE activo = 1 "
                "ORDER BY servicio_id, orden ASC, id ASC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM segmentaciones ORDER BY servicio_id, orden ASC, id ASC"
            ).fetchall()
    conn.close()
    return [segmentacion(r) for r in rows]


async def listar(servicio_id: Optional[int] = None, solo_activos: bool = True) -> list:
    return await db.run_in_executor(_listar, servicio_id, solo_activos)


def _obtener_por_id(id_seg: int):
    conn = db.conectar()
    row = conn.execute(
        "SELECT * FROM segmentaciones WHERE id = ?", (id_seg,)
    ).fetchone()
    conn.close()
    return segmentacion(row) if row else None


async def obtener_por_id(id_seg: int):
    return await db.run_in_executor(_obtener_por_id, id_seg)


def _actualizar(
    id_seg: int,
    *,
    nombre: str,
    descripcion: str,
    tipo_calculo: str,
    precio_fijo: int,
    tarifa_por_kg: float,
    duracion_min: int,
    activo: bool,
) -> None:
    conn = db.conectar()
    conn.execute(
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


async def actualizar(id_seg: int, **kwargs) -> None:
    await db.run_in_executor(_actualizar, id_seg, **kwargs)


def _crear(
    *,
    servicio_id: int,
    codigo: str,
    nombre: str,
    descripcion: str,
    tipo_calculo: str,
    precio_fijo: int,
    tarifa_por_kg: float,
    duracion_min: int,
    orden: int = 99,
    activo: bool = True,
) -> Optional[int]:
    conn = db.conectar()
    try:
        cur = conn.execute(
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


def _eliminar_hard(id_seg: int) -> bool:
    """Borra solo si no hay órdenes referenciando esta segmentación."""
    conn = db.conectar()
    row = conn.execute(
        "SELECT nombre FROM segmentaciones WHERE id = ?", (id_seg,)
    ).fetchone()
    if not row:
        conn.close()
        return False
    nombre = row["nombre"]
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM transacciones WHERE tipo_servicio LIKE ?",
        (f"% · {nombre}",),
    ).fetchone()["c"]
    if count > 0:
        conn.close()
        return False
    conn.execute("DELETE FROM segmentaciones WHERE id = ?", (id_seg,))
    conn.commit()
    conn.close()
    return True


async def eliminar_hard(id_seg: int) -> bool:
    return await db.run_in_executor(_eliminar_hard, id_seg)
