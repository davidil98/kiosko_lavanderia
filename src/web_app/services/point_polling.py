"""Tarea de fondo que vigila órdenes Point pendientes y confirma automáticamente.

Hace polling a Mercado Pago cada 5s para cada orden 'Pendiente-pago' con
mp_order_id asignado. Si el status cambia a 'paid', la orden pasa a 'Pendiente'
y notifica al kiosko y al admin. Si expira o se cancela, borra la local.
"""

import asyncio
from services import mercadopago
import database_web
from services.notifications import notificar_kiosko, notificar_admin

POLL_INTERVAL = 5  # segundos

_polling_task = None
_stopping = False


async def _ciclo_polling():
    """Ciclo principal del polling."""
    print("[Point] Polling iniciado")
    while not _stopping:
        try:
            ordenes = await database_web.obtener_ordenes_point_pendientes_async()
            for orden in ordenes:
                if _stopping:
                    break
                mp_order_id = orden.get("mp_order_id", "")
                if not mp_order_id:
                    continue
                await _revisar_orden(orden, mp_order_id)
        except Exception as e:
            print(f"[Point] Error en ciclo de polling: {e}")
        await asyncio.sleep(POLL_INTERVAL)
    print("[Point] Polling detenido")


async def _revisar_orden(orden: dict, mp_order_id: str):
    """Consulta el estado de una orden Point y actúa según el resultado."""
    id_tx = orden["id_transaccion"]
    data = await asyncio.to_thread(mercadopago.consultar_orden, mp_order_id)
    if not data:
        return  # Error de red, intentar el siguiente ciclo

    status = data.get("status", "unknown")
    if status == "paid":
        folio = _extraer_pago_id(data)
        await database_web.aprobar_pago_terminal_async(id_tx, folio, "point-polling")
        print(f"[Point] Orden #{id_tx} pagada (folio={folio})")
        notificar_admin()
        notificar_kiosko("Pago confirmado. Gracias por tu compra.", "positive")
    elif status in ("expired", "cancelled"):
        await database_web.cancelar_pago_pendiente_async(id_tx, "sistema")
        print(f"[Point] Orden #{id_tx} {status} — eliminada localmente")
        notificar_admin()
        if status == "expired":
            notificar_kiosko("El pago con Point expiró. Intenta de nuevo.", "warning")
        else:
            notificar_kiosko(
                "La orden Point fue cancelada. Intenta de nuevo.", "warning"
            )


def _extraer_pago_id(data: dict) -> str:
    """Extrae el id del pago de la respuesta de MP. Devuelve '' si no hay."""
    try:
        txns = data.get("transactions", {}).get("payments", [])
        if txns:
            return str(txns[0].get("id", ""))
    except (AttributeError, TypeError):
        pass
    return ""


async def iniciar_polling():
    """Inicia la tarea de polling. Llamar después de init_db()."""
    global _polling_task
    if _polling_task is not None and not _polling_task.done():
        return
    _stopping = False
    _polling_task = asyncio.create_task(_ciclo_polling())


async def detener_polling():
    """Detiene el polling limpiamente."""
    global _stopping, _polling_task
    _stopping = True
    if _polling_task is not None:
        _polling_task.cancel()
        try:
            await _polling_task
        except (asyncio.CancelledError, Exception):
            pass
        _polling_task = None
