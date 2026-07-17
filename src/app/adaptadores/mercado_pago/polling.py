"""Tarea asyncio que vigila órdenes Point pendientes y confirma automáticamente.

Cada `INTERVALO_S` segundos:
1. Lee órdenes `Pendiente-pago` con `mp_order_id` (Point).
2. Consulta el estado en MP.
3. `paid` → transiciona `PENDIENTE_PAGO → PENDIENTE` y persiste.
4. `expired`/`cancelled` → cancela la orden local.
5. Notifica vía callbacks inyectables (la UI se suscribe por separado).
"""

import asyncio
from typing import Awaitable, Callable, Optional

from app.core.estados import EstadoOrden
from app.core.transiciones import Evento, transiciones_permitidas
from app.repo import transacciones

from . import point

INTERVALO_S = 5

_tarea: Optional[asyncio.Task] = None
_detenido = False

Notificable = Callable[[str, str], Awaitable[None]]


async def _revisar_orden(orden: dict, notificar: Notificable) -> None:
    mp_id = orden.get("mp_order_id", "")
    if not mp_id:
        return
    data = await asyncio.to_thread(point.consultar_orden, mp_id)
    if not data:
        return
    status = data.get("status", "unknown")
    oid = orden["id_transaccion"]

    if status == "paid":
        # Validar que la transición está permitida por la máquina de estados.
        # No es necesario reconstruir el Orden: basta con chequear la tabla.
        if Evento.PAGO_CONFIRMADO not in transiciones_permitidas(
            EstadoOrden.PENDIENTE_PAGO
        ):
            print(f"[Point] Estado inconsistente para #{oid}: {orden.get('estado')}")
            return
        folio = point.extraer_folio_pago(data)
        await transacciones.aprobar_pago_terminal(oid, folio, "point-polling")
        print(f"[Point] Orden #{oid} pagada (folio={folio})")
        await notificar("pago.confirmado", str(oid))
    elif status in ("expired", "cancelled"):
        await transacciones.cancelar_pago_pendiente(oid)
        print(f"[Point] Orden #{oid} {status} — eliminada localmente")
        await notificar("pago.cancelado", str(oid))


async def _ciclo(notificar: Notificable) -> None:
    print("[Point] Polling iniciado")
    while not _detenido:
        try:
            ordenes = await transacciones.listar_point_pendientes()
            for orden in ordenes:
                if _detenido:
                    break
                await _revisar_orden(orden, notificar)
        except Exception as e:
            print(f"[Point] Error en ciclo de polling: {e}")
        await asyncio.sleep(INTERVALO_S)
    print("[Point] Polling detenido")


def iniciar(notificar: Notificable) -> None:
    """Lanza la tarea de polling. Llamar desde un loop asyncio activo (e.g. `on_startup`)."""
    global _tarea, _detenido
    if _tarea is not None and not _tarea.done():
        return
    _detenido = False
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        raise RuntimeError("iniciar() debe llamarse desde un loop asyncio activo")
    _tarea = loop.create_task(_ciclo(notificar))


async def detener() -> None:
    """Detiene la tarea limpiamente. Llamar desde `app.on_shutdown`."""
    global _tarea, _detenido
    _detenido = True
    if _tarea is not None:
        _tarea.cancel()
        try:
            await _tarea
        except (asyncio.CancelledError, Exception):
            pass
        _tarea = None


async def notificar_noop(tipo: str, id_orden: str) -> None:
    """Callback por defecto. Útil para tests y para el kiosko cliente."""
    pass
