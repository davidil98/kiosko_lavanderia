"""Repositorio de transacciones (órdenes).

Convención: cada función tiene una versión `_sync` (bloqueante) y su espejo
`async` que delega a `db.run_in_executor`. La UI solo invoca las `async`.

Nota sobre los strings de estado: la BD pre-v2 usaba "En proceso" y
"Completado"; el nuevo enum `EstadoOrden` usa "En-curso" y "Finalizado".
Por compatibilidad con datos históricos, los strings legacy se mantienen en
las queries SQL. La capa de dominio (core/transiciones) trabaja siempre con
el enum. Los strings del enum deben coincidir con los de la BD para los
estados que sí migraron (ver test_estados_coinciden_con_bd).
"""

from datetime import datetime
from typing import Optional

from app.core.estados import EstadoOrden, EtapaKanban
from app.repo import db
from ._row_a import transaccion_dict


# Estados legacy (no migrados). Mantener tal cual para datos históricos.
_EN_PROCESO = "En proceso"
_COMPLETADO = "Completado"


# ── Creación ─────────────────────────────────────────────────────────────────


def _crear_orden(
    *,
    tipo_servicio: str,
    monto: int,
    dinero_ingresado: int,
    cambio_devuelto: int,
    id_equipo: str,
    duracion_estimada_min: Optional[int],
    nombre_cliente: str,
    peso_kg: float = 0.0,
    modalidad: str = "autoservicio",
    estado: str = "Pendiente",
    etapa_kanban: Optional[str] = None,
) -> int:
    conn = db.conectar()
    cursor = conn.cursor()
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        INSERT INTO transacciones
            (fecha_hora, tipo_servicio, monto_pagado, dinero_ingresado, cambio_devuelto,
             id_equipo, duracion_estimada_min, estado, nombre_cliente,
             peso_kg, notas, etapa_kanban, modalidad)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?)
        """,
        (
            fecha_hora,
            tipo_servicio,
            monto,
            dinero_ingresado,
            cambio_devuelto,
            id_equipo,
            duracion_estimada_min,
            estado,
            nombre_cliente,
            peso_kg,
            etapa_kanban,
            modalidad,
        ),
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


async def crear_orden(**kwargs) -> int:
    return await db.run_in_executor(_crear_orden, **kwargs)


def _crear_orden_pendiente_peso(
    *,
    tipo_servicio: str,
    peso_kg: float,
    nombre_cliente: str,
    duracion_estimada_min: int,
    modalidad: str,
) -> int:
    etapa = EtapaKanban.RECIBIDO.value if modalidad == "personalizado" else None
    return _crear_orden(
        tipo_servicio=tipo_servicio,
        monto=0,
        dinero_ingresado=0,
        cambio_devuelto=0,
        id_equipo="N/A",
        duracion_estimada_min=duracion_estimada_min,
        nombre_cliente=nombre_cliente,
        peso_kg=peso_kg,
        modalidad=modalidad,
        estado=EstadoOrden.PENDIENTE_PESO.value,
        etapa_kanban=etapa,
    )


async def crear_orden_pendiente_peso(**kwargs) -> int:
    return await db.run_in_executor(_crear_orden_pendiente_peso, **kwargs)


def _crear_orden_pendiente_pago(
    *,
    tipo_servicio: str,
    peso_kg: float,
    monto: int,
    nombre_cliente: str,
    duracion_estimada_min: int,
    modalidad: str,
) -> int:
    etapa = EtapaKanban.RECIBIDO.value if modalidad == "personalizado" else None
    return _crear_orden(
        tipo_servicio=tipo_servicio,
        monto=monto,
        dinero_ingresado=0,
        cambio_devuelto=0,
        id_equipo="N/A",
        duracion_estimada_min=duracion_estimada_min,
        nombre_cliente=nombre_cliente,
        peso_kg=peso_kg,
        modalidad=modalidad,
        estado=EstadoOrden.PENDIENTE_PAGO.value,
        etapa_kanban=etapa,
    )


async def crear_orden_pendiente_pago(**kwargs) -> int:
    return await db.run_in_executor(_crear_orden_pendiente_pago, **kwargs)


# ── Consultas del panel operativo ────────────────────────────────────────────


def _listar_pendientes_operativo() -> list:
    conn = db.conectar()
    rows = conn.execute(
        f"SELECT * FROM transacciones "
        f"WHERE estado IN ("
        f"'{EstadoOrden.PENDIENTE_PESO.value}', "
        f"'{EstadoOrden.PROCESANDO_PAGO.value}', "
        f"'{EstadoOrden.PENDIENTE_PAGO.value}') "
        f"ORDER BY id_transaccion ASC"
    ).fetchall()
    conn.close()
    return [transaccion_dict(r) for r in rows]


async def listar_pendientes_operativo() -> list:
    return await db.run_in_executor(_listar_pendientes_operativo)


def _contadores_pendientes() -> dict:
    conn = db.conectar()
    rows = conn.execute(
        f"SELECT estado, COUNT(*) AS cnt FROM transacciones "
        f"WHERE estado IN ("
        f"'{EstadoOrden.PENDIENTE_PESO.value}', "
        f"'{EstadoOrden.PROCESANDO_PAGO.value}', "
        f"'{EstadoOrden.PENDIENTE_PAGO.value}', "
        f"'{EstadoOrden.PENDIENTE.value}', "
        f"'{_EN_PROCESO}') "
        f"GROUP BY estado"
    ).fetchall()
    conn.close()
    return {row["estado"]: row["cnt"] for row in rows}


async def contadores_pendientes() -> dict:
    return await db.run_in_executor(_contadores_pendientes)


# ── Consultas del panel autoservicio ─────────────────────────────────────────


def _listar_para_asignar_autoservicio() -> list:
    conn = db.conectar()
    rows = conn.execute(
        f"SELECT * FROM transacciones "
        f"WHERE estado IN ('{EstadoOrden.PENDIENTE.value}', '{_EN_PROCESO}') "
        f"AND (modalidad IS NULL OR modalidad LIKE 'autoservicio%') "
        f"ORDER BY id_transaccion ASC"
    ).fetchall()
    conn.close()
    return [transaccion_dict(r) for r in rows]


async def listar_para_asignar_autoservicio() -> list:
    return await db.run_in_executor(_listar_para_asignar_autoservicio)


def _listar_en_proceso() -> list:
    conn = db.conectar()
    rows = conn.execute(
        f"SELECT * FROM transacciones WHERE estado = '{_EN_PROCESO}' ORDER BY id_transaccion ASC"
    ).fetchall()
    conn.close()
    return [transaccion_dict(r) for r in rows]


async def listar_en_proceso() -> list:
    return await db.run_in_executor(_listar_en_proceso)


def _marcar_en_proceso(id_transaccion: int, id_equipo: str) -> None:
    conn = db.conectar()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        f"UPDATE transacciones SET estado = '{_EN_PROCESO}', id_equipo = ?, "
        f"inicio_servicio = ? WHERE id_transaccion = ?",
        (id_equipo, ahora, id_transaccion),
    )
    conn.commit()
    conn.close()


async def marcar_en_proceso(id_transaccion: int, id_equipo: str) -> None:
    await db.run_in_executor(_marcar_en_proceso, id_transaccion, id_equipo)


def _marcar_completado(id_transaccion: int, id_equipo: str) -> None:
    conn = db.conectar()
    conn.execute(
        f"UPDATE transacciones SET estado = '{_COMPLETADO}', id_equipo = ? "
        f"WHERE id_transaccion = ?",
        (id_equipo, id_transaccion),
    )
    conn.commit()
    conn.close()


async def marcar_completado(id_transaccion: int, id_equipo: str) -> None:
    await db.run_in_executor(_marcar_completado, id_transaccion, id_equipo)


# ── Asignación de máquina (personalizado) ────────────────────────────────────


def _asignar_maquina_personalizado(
    id_transaccion: int, codigo: str, duracion_min: int
) -> None:
    """Asigna máquina a una orden personalizada.

    No requiere que la orden esté en `EN_CURSO`: el kanban personalizado
    asigna máquina durante `ALISTANDO` (antes del ciclo).
    """
    conn = db.conectar()
    conn.execute(
        "UPDATE transacciones SET id_equipo = ?, duracion_estimada_min = ? "
        "WHERE id_transaccion = ?",
        (codigo, duracion_min, id_transaccion),
    )
    conn.commit()
    conn.close()


async def asignar_maquina_personalizado(
    id_transaccion: int, codigo: str, duracion_min: int
) -> None:
    await db.run_in_executor(
        _asignar_maquina_personalizado, id_transaccion, codigo, duracion_min
    )


def _cancelar_orden(id_transaccion: int, notas: str = "") -> None:
    """Marca una orden como CANCELADO con nota opcional."""
    conn = db.conectar()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nota_final = f"{notas} · {ahora}" if notas else ahora
    conn.execute(
        "UPDATE transacciones SET estado = ?, notas = ? WHERE id_transaccion = ?",
        ("Cancelado", nota_final, id_transaccion),
    )
    conn.commit()
    conn.close()


async def cancelar_orden(id_transaccion: int, notas: str = "") -> None:
    await db.run_in_executor(_cancelar_orden, id_transaccion, notas)


def _obtener_maquina_codigo_de_orden(id_transaccion: int) -> Optional[str]:
    """Devuelve el nombre de la máquina asignada a una orden, o None.

    Útil para liberar la máquina al cancelar/completar.
    """
    conn = db.conectar()
    row = conn.execute(
        "SELECT id_equipo FROM transacciones WHERE id_transaccion = ?",
        (id_transaccion,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    nombre = row["id_equipo"] or ""
    return nombre if nombre else None


async def obtener_maquina_nombre_de_orden(id_transaccion: int) -> Optional[str]:
    return await db.run_in_executor(_obtener_maquina_codigo_de_orden, id_transaccion)


# ── Aprobación / rechazo de peso ─────────────────────────────────────────────


def _aprobar_peso(id_transaccion: int, peso_final: float, usuario: str) -> None:
    conn = db.conectar()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nota = f"PESO APROBADO por {usuario} a las {ahora}"
    conn.execute(
        f"""
        UPDATE transacciones
        SET estado = '{EstadoOrden.PROCESANDO_PAGO.value}', peso_kg = ?, notas = ?, validado_por = ?
        WHERE id_transaccion = ? AND estado = '{EstadoOrden.PENDIENTE_PESO.value}'
        """,
        (peso_final, nota, usuario, id_transaccion),
    )
    conn.commit()
    conn.close()


async def aprobar_peso(id_transaccion: int, peso_final: float, usuario: str) -> None:
    await db.run_in_executor(_aprobar_peso, id_transaccion, peso_final, usuario)


def _rechazar_peso(id_transaccion: int) -> None:
    conn = db.conectar()
    conn.execute(
        f"DELETE FROM transacciones WHERE id_transaccion = ? AND estado = '{EstadoOrden.PENDIENTE_PESO.value}'",
        (id_transaccion,),
    )
    conn.commit()
    conn.close()


async def rechazar_peso(id_transaccion: int) -> None:
    await db.run_in_executor(_rechazar_peso, id_transaccion)


# ── Flujo de pago Point / terminal / mostrador ──────────────────────────────


def _guardar_mp_order_id(id_transaccion: int, mp_order_id: str) -> None:
    conn = db.conectar()
    conn.execute(
        "UPDATE transacciones SET mp_order_id = ? WHERE id_transaccion = ?",
        (mp_order_id, id_transaccion),
    )
    conn.commit()
    conn.close()


async def guardar_mp_order_id(id_transaccion: int, mp_order_id: str) -> None:
    await db.run_in_executor(_guardar_mp_order_id, id_transaccion, mp_order_id)


def _obtener_mp_order_id(id_transaccion: int) -> str:
    conn = db.conectar()
    row = conn.execute(
        "SELECT mp_order_id FROM transacciones WHERE id_transaccion = ?",
        (id_transaccion,),
    ).fetchone()
    conn.close()
    return row["mp_order_id"] if row else ""


async def obtener_mp_order_id(id_transaccion: int) -> str:
    return await db.run_in_executor(_obtener_mp_order_id, id_transaccion)


def _marcar_pendiente_pago(
    id_transaccion: int,
    monto: int,
    modalidad: str,
    mp_order_id: Optional[str] = None,
) -> Optional[int]:
    conn = db.conectar()
    if mp_order_id is not None:
        rows = conn.execute(
            f"""
            UPDATE transacciones
            SET estado = '{EstadoOrden.PENDIENTE_PAGO.value}', monto_pagado = ?, modalidad = ?, mp_order_id = ?
            WHERE id_transaccion = ? AND estado = '{EstadoOrden.PROCESANDO_PAGO.value}'
            """,
            (monto, modalidad, mp_order_id, id_transaccion),
        )
    else:
        rows = conn.execute(
            f"""
            UPDATE transacciones
            SET estado = '{EstadoOrden.PENDIENTE_PAGO.value}', monto_pagado = ?, modalidad = ?
            WHERE id_transaccion = ? AND estado = '{EstadoOrden.PROCESANDO_PAGO.value}'
            """,
            (monto, modalidad, id_transaccion),
        )
    actualizado = rows.rowcount > 0
    conn.commit()
    conn.close()
    return id_transaccion if actualizado else None


async def marcar_pendiente_pago(
    id_transaccion: int, monto: int, modalidad: str, mp_order_id: Optional[str] = None
) -> Optional[int]:
    return await db.run_in_executor(
        _marcar_pendiente_pago, id_transaccion, monto, modalidad, mp_order_id
    )


def _listar_point_pendientes() -> list:
    conn = db.conectar()
    rows = conn.execute(
        f"SELECT * FROM transacciones "
        f"WHERE estado = '{EstadoOrden.PENDIENTE_PAGO.value}' AND mp_order_id != '' "
        f"ORDER BY id_transaccion ASC"
    ).fetchall()
    conn.close()
    return [transaccion_dict(r) for r in rows]


async def listar_point_pendientes() -> list:
    return await db.run_in_executor(_listar_point_pendientes)


def _aprobar_pago_terminal(id_transaccion: int, folio: str, usuario: str) -> None:
    conn = db.conectar()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nota = f"PAGO TERMINAL confirmado por {usuario} a las {ahora}"
    conn.execute(
        f"""
        UPDATE transacciones
        SET estado = '{EstadoOrden.PENDIENTE.value}',
            numero_transaccion_terminal = ?,
            notas = ?,
            validado_por = ?
        WHERE id_transaccion = ? AND estado = '{EstadoOrden.PENDIENTE_PAGO.value}'
        """,
        (folio or "", nota, usuario, id_transaccion),
    )
    conn.commit()
    conn.close()


async def aprobar_pago_terminal(id_transaccion: int, folio: str, usuario: str) -> None:
    await db.run_in_executor(_aprobar_pago_terminal, id_transaccion, folio, usuario)


def _guardar_pago_orden(
    id_transaccion: int, monto: int, ingresado: int, cambio: int, modalidad: str
) -> Optional[int]:
    conn = db.conectar()
    rows = conn.execute(
        f"""
        UPDATE transacciones
        SET estado = '{EstadoOrden.PENDIENTE.value}',
            monto_pagado = ?,
            dinero_ingresado = ?,
            cambio_devuelto = ?,
            modalidad = ?
        WHERE id_transaccion = ? AND estado = '{EstadoOrden.PROCESANDO_PAGO.value}'
        """,
        (monto, ingresado, cambio, modalidad, id_transaccion),
    )
    actualizado = rows.rowcount > 0
    conn.commit()
    conn.close()
    return id_transaccion if actualizado else None


async def guardar_pago_orden(
    id_transaccion: int, monto: int, ingresado: int, cambio: int, modalidad: str
) -> Optional[int]:
    return await db.run_in_executor(
        _guardar_pago_orden, id_transaccion, monto, ingresado, cambio, modalidad
    )


def _cancelar_pago_pendiente(id_transaccion: int) -> None:
    conn = db.conectar()
    conn.execute(
        f"DELETE FROM transacciones WHERE id_transaccion = ? "
        f"AND estado IN ('{EstadoOrden.PENDIENTE_PAGO.value}', "
        f"'{EstadoOrden.PROCESANDO_PAGO.value}')",
        (id_transaccion,),
    )
    conn.commit()
    conn.close()


async def cancelar_pago_pendiente(id_transaccion: int) -> None:
    await db.run_in_executor(_cancelar_pago_pendiente, id_transaccion)


# ── Kanban personalizado ────────────────────────────────────────────────────


def _listar_personalizadas() -> list:
    conn = db.conectar()
    rows = conn.execute(
        "SELECT * FROM transacciones WHERE modalidad LIKE 'personalizado%' "
        "ORDER BY id_transaccion ASC"
    ).fetchall()
    conn.close()
    return [transaccion_dict(r) for r in rows]


async def listar_personalizadas() -> list:
    return await db.run_in_executor(_listar_personalizadas)


def _actualizar_etapa_kanban(
    id_transaccion: int, nueva_etapa: str, equipo_id: Optional[str] = None
) -> None:
    conn = db.conectar()
    nuevo_estado = _COMPLETADO if nueva_etapa == "Entregado" else _EN_PROCESO
    if equipo_id:
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE transacciones SET etapa_kanban=?, estado=?, id_equipo=?, "
            "inicio_servicio=? WHERE id_transaccion=?",
            (nueva_etapa, nuevo_estado, equipo_id, ahora, id_transaccion),
        )
    else:
        conn.execute(
            "UPDATE transacciones SET etapa_kanban=?, estado=? WHERE id_transaccion=?",
            (nueva_etapa, nuevo_estado, id_transaccion),
        )
    conn.commit()
    conn.close()


async def actualizar_etapa_kanban(
    id_transaccion: int, nueva_etapa: str, equipo_id: Optional[str] = None
) -> None:
    await db.run_in_executor(
        _actualizar_etapa_kanban, id_transaccion, nueva_etapa, equipo_id
    )


def _actualizar_notas(id_transaccion: int, notas: str) -> None:
    conn = db.conectar()
    conn.execute(
        "UPDATE transacciones SET notas=? WHERE id_transaccion=?",
        (notas, id_transaccion),
    )
    conn.commit()
    conn.close()


async def actualizar_notas(id_transaccion: int, notas: str) -> None:
    await db.run_in_executor(_actualizar_notas, id_transaccion, notas)


def _actualizar_tipo_servicio(id_transaccion: int, tipo_servicio: str) -> None:
    conn = db.conectar()
    conn.execute(
        "UPDATE transacciones SET tipo_servicio=? WHERE id_transaccion=?",
        (tipo_servicio, id_transaccion),
    )
    conn.commit()
    conn.close()


async def actualizar_tipo_servicio(id_transaccion: int, tipo_servicio: str) -> None:
    await db.run_in_executor(_actualizar_tipo_servicio, id_transaccion, tipo_servicio)


def _eliminar_si_activa(id_transaccion: int) -> bool:
    """Elimina una orden si está en un estado activo del cliente
    (Pendiente-peso, Procesando-pago o Pendiente-pago).
    Devuelve True si se eliminó, False si no se encontró o no era eliminable.
    """
    conn = db.conectar()
    cursor = conn.cursor()
    cursor.execute(
        f"DELETE FROM transacciones WHERE id_transaccion = ? "
        f"AND estado IN ('{EstadoOrden.PENDIENTE_PESO.value}', "
        f"'{EstadoOrden.PROCESANDO_PAGO.value}', "
        f"'{EstadoOrden.PENDIENTE_PAGO.value}')",
        (id_transaccion,),
    )
    eliminado = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return eliminado


async def eliminar_si_activa(id_transaccion: int) -> bool:
    return await db.run_in_executor(_eliminar_si_activa, id_transaccion)


def _obtener_por_id(id_transaccion: int) -> Optional[dict]:
    conn = db.conectar()
    row = conn.execute(
        "SELECT * FROM transacciones WHERE id_transaccion = ?",
        (id_transaccion,),
    ).fetchone()
    conn.close()
    return transaccion_dict(row) if row else None


async def obtener_por_id(id_transaccion: int) -> Optional[dict]:
    return await db.run_in_executor(_obtener_por_id, id_transaccion)


def _obtener_completadas_entre(desde: str) -> list:
    """Lista órdenes con estado 'Completado' o 'En proceso' desde `desde`.
    `desde` es un string ISO 8601 (compatible con `datetime.isoformat()`)."""
    conn = db.conectar()
    rows = conn.execute(
        f"SELECT * FROM transacciones "
        f"WHERE estado IN ('Completado', 'En proceso') "
        f"AND fecha_hora >= ? "
        f"ORDER BY fecha_hora ASC",
        (desde,),
    ).fetchall()
    conn.close()
    return [transaccion_dict(r) for r in rows]


async def obtener_completadas_entre(desde) -> list:
    """Versión async. Acepta `datetime` o string ISO."""
    if hasattr(desde, "isoformat"):
        desde = desde.isoformat()
    return await db.run_in_executor(_obtener_completadas_entre, desde)
