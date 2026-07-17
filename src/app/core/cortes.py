"""Lógica de cortes de caja.

Capa de dominio sobre `repo/cortes.py`. La UI no toca SQL directamente,
solo llama a estas funciones y muestra los resultados.
"""

from datetime import datetime
from typing import Optional

from app.repo import cortes as repo_cortes


def abrir(fecha: str, usuario: str, saldo_inicial: int) -> dict:
    """Abre un nuevo corte de caja. Si ya hay uno abierto, retorna error."""
    return repo_cortes._abrir(fecha, usuario, saldo_inicial)


def cerrar(id_corte: int, usuario: str, saldo_real: int, notas: str) -> dict:
    """Cierra el corte. Calcula esperado = saldo_inicial + ingresos - egresos
    y diferencia = saldo_real - esperado."""
    return repo_cortes._cerrar(id_corte, usuario, saldo_real, notas)


def registrar_movimiento(
    corte_id: int,
    tipo: str,
    monto: int,
    concepto: str,
    usuario: str,
    notas: str = "",
    auto: int = 0,
) -> dict:
    """Registra un ingreso o egreso en el corte activo."""
    return repo_cortes._registrar_movimiento(
        corte_id,
        tipo,
        monto,
        concepto,
        usuario,
        notas,
        auto,
    )


async def abrir_async(fecha: str, usuario: str, saldo_inicial: int) -> dict:
    return await repo_cortes.abrir(fecha, usuario, saldo_inicial)


async def cerrar_async(
    id_corte: int, usuario: str, saldo_real: int, notas: str
) -> dict:
    return await repo_cortes.cerrar(id_corte, usuario, saldo_real, notas)


async def registrar_movimiento_async(
    corte_id: int,
    tipo: str,
    monto: int,
    concepto: str,
    usuario: str,
    notas: str = "",
    auto: int = 0,
) -> dict:
    return await repo_cortes.registrar_movimiento(
        corte_id,
        tipo,
        monto,
        concepto,
        usuario,
        notas,
        auto,
    )


async def obtener_activo_async() -> Optional[dict]:
    return await repo_cortes.obtener_activo()


async def listar_movimientos_async(corte_id: int) -> list:
    return await repo_cortes.listar_movimientos(corte_id)


async def listar_cerrados_async(limite: int = 30) -> list:
    return await repo_cortes.listar(limite)


def resumen(corte: dict, movimientos: list) -> dict:
    """Calcula ingresos, egresos, esperado, diferencia para un corte.

    `corte` es el dict retornado por `repo.cortes.listar()` o `obtener_activo()`.
    `movimientos` es una lista de `MovimientoCaja` (dataclass) o de dicts.
    """

    def _monto(m) -> int:
        if isinstance(m, dict):
            return m.get("monto", 0) or 0
        return getattr(m, "monto", 0) or 0

    def _tipo(m) -> str:
        if isinstance(m, dict):
            return m.get("tipo", "")
        return getattr(m, "tipo", "")

    ingresos = sum(_monto(m) for m in movimientos if _tipo(m) == "ingreso")
    egresos = sum(_monto(m) for m in movimientos if _tipo(m) == "egreso")
    saldo_inicial = corte.get("saldo_inicial", 0) or 0
    esperado = saldo_inicial + ingresos - egresos
    diferencia = None
    if corte.get("saldo_real") is not None:
        diferencia = (corte.get("saldo_real") or 0) - esperado
    return {
        "saldo_inicial": saldo_inicial,
        "ingresos": ingresos,
        "egresos": egresos,
        "esperado": esperado,
        "saldo_real": corte.get("saldo_real"),
        "diferencia": diferencia,
    }
