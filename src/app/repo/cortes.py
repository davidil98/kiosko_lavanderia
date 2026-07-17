"""Repositorio de cortes de caja y movimientos."""

from datetime import datetime
from typing import Optional

from app.repo import db
from ._row_a import corte_caja, movimiento_caja


# ── Cortes ───────────────────────────────────────────────────────────────────


def _obtener_activo() -> Optional[dict]:
    conn = db.conectar()
    row = conn.execute(
        "SELECT * FROM cortes_caja WHERE estado = 'abierto' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(row) if row else None


async def obtener_activo() -> Optional[dict]:
    return await db.run_in_executor(_obtener_activo)


def _abrir(fecha: str, usuario: str, saldo_inicial: int) -> dict:
    if saldo_inicial < 0:
        return {"ok": False, "error": "El saldo inicial no puede ser negativo."}
    if _obtener_activo() is not None:
        return {
            "ok": False,
            "error": "Ya hay una caja abierta. Ciérrala antes de abrir otra.",
        }
    conn = db.conectar()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur = conn.execute(
            """
            INSERT INTO cortes_caja
                (fecha, usuario_apertura, saldo_inicial, estado, hora_apertura)
            VALUES (?, ?, ?, 'abierto', ?)
            """,
            (fecha, usuario, saldo_inicial, ahora),
        )
        conn.commit()
        new_id = cur.lastrowid
    except Exception as e:
        conn.close()
        return {"ok": False, "error": str(e)}
    conn.close()
    return {"ok": True, "id": new_id}


async def abrir(fecha: str, usuario: str, saldo_inicial: int) -> dict:
    return await db.run_in_executor(_abrir, fecha, usuario, saldo_inicial)


def _cerrar(id_corte: int, usuario: str, saldo_real: int, notas: str) -> dict:
    if saldo_real < 0:
        return {"ok": False, "error": "El saldo real no puede ser negativo."}
    conn = db.conectar()
    row = conn.execute(
        "SELECT saldo_inicial FROM cortes_caja WHERE id = ? AND estado = 'abierto'",
        (id_corte,),
    ).fetchone()
    if not row:
        conn.close()
        return {"ok": False, "error": "Corte no encontrado o ya cerrado."}
    saldo_inicial = row["saldo_inicial"]
    mov = conn.execute(
        "SELECT "
        "COALESCE(SUM(CASE WHEN tipo='ingreso' THEN monto ELSE 0 END), 0) AS ingresos, "
        "COALESCE(SUM(CASE WHEN tipo='egreso' THEN monto ELSE 0 END), 0) AS egresos "
        "FROM movimientos_caja WHERE corte_id = ?",
        (id_corte,),
    ).fetchone()
    ingresos = mov["ingresos"] or 0
    egresos = mov["egresos"] or 0
    saldo_esperado = saldo_inicial + ingresos - egresos
    diferencia = saldo_real - saldo_esperado
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn.execute(
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


async def cerrar(id_corte: int, usuario: str, saldo_real: int, notas: str) -> dict:
    return await db.run_in_executor(_cerrar, id_corte, usuario, saldo_real, notas)


def _listar(limite: int = 30) -> list:
    conn = db.conectar()
    rows = conn.execute(
        "SELECT * FROM cortes_caja ORDER BY id DESC LIMIT ?", (limite,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


async def listar(limite: int = 30) -> list:
    return await db.run_in_executor(_listar, limite)


# ── Movimientos ──────────────────────────────────────────────────────────────


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
    conn = db.conectar()
    row = conn.execute(
        "SELECT id, estado FROM cortes_caja WHERE id = ?", (corte_id,)
    ).fetchone()
    if not row:
        conn.close()
        return {"ok": False, "error": "Corte no encontrado."}
    if row["estado"] != "abierto":
        conn.close()
        return {"ok": False, "error": "La caja está cerrada."}
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cur = conn.execute(
            """
            INSERT INTO movimientos_caja
                (corte_id, fecha_hora, tipo, monto, concepto, usuario, notas, auto)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (corte_id, ahora, tipo, monto, concepto.strip(), usuario, notas, auto),
        )
        conn.commit()
        new_id = cur.lastrowid
    except Exception as e:
        conn.close()
        return {"ok": False, "error": str(e)}
    conn.close()
    return {"ok": True, "id": new_id}


async def registrar_movimiento(
    corte_id: int,
    tipo: str,
    monto: int,
    concepto: str,
    usuario: str,
    notas: str = "",
    auto: int = 0,
) -> dict:
    return await db.run_in_executor(
        _registrar_movimiento, corte_id, tipo, monto, concepto, usuario, notas, auto
    )


def _listar_movimientos(corte_id: int) -> list:
    conn = db.conectar()
    rows = conn.execute(
        "SELECT * FROM movimientos_caja WHERE corte_id = ? ORDER BY id ASC",
        (corte_id,),
    ).fetchall()
    conn.close()
    return [movimiento_caja(r) for r in rows]


async def listar_movimientos(corte_id: int) -> list:
    return await db.run_in_executor(_listar_movimientos, corte_id)
