import os
import uuid
import asyncio
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.mercadopago.com"

ENVIRONMENT = os.getenv("MP_ENVIRONMENT", "test").lower()


def _resolve_token() -> str | None:
    if ENVIRONMENT == "prod":
        token = os.getenv("MP_PROD_TOKEN")
        if token:
            return token
        print(
            "[mp_qr] MP_ENVIRONMENT=prod pero MP_PROD_TOKEN no definido; usando MP_TEST_TOKEN."
        )
    return os.getenv("MP_TEST_TOKEN")


_cached_user_id: Optional[int] = None


def _resolve_user_id(token: str) -> int:
    """Obtiene el user_id real de la cuenta usando /users/me.
    Se usa como sponsor en las órdenes QR."""
    global _cached_user_id
    if _cached_user_id is not None:
        return _cached_user_id
    env_user_id = os.getenv("MP_USER_ID")
    if env_user_id:
        try:
            _cached_user_id = int(env_user_id)
            return _cached_user_id
        except ValueError:
            pass
    try:
        resp = requests.get(
            f"{BASE_URL}/users/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if resp.status_code == 200:
            _cached_user_id = resp.json().get("id")
    except Exception as e:
        print(f"[mp_qr] No se pudo obtener user_id: {e}")
    if _cached_user_id is None:
        # Fallback al valor anterior para no romper configuraciones previas
        _cached_user_id = 277917625
    return _cached_user_id


async def crear_orden_qr(monto: float, descripcion: str, external_ref: str) -> dict:
    """Crea una orden con tipo 'qr' en Mercado Pago (in-store QR).
    Retorna el dict completo de la respuesta de MP.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _crear_orden_qr_sync, monto, descripcion, external_ref
    )


def _crear_orden_qr_sync(monto: float, descripcion: str, external_ref: str) -> dict:
    token = _resolve_token()
    if not token:
        raise RuntimeError("No hay token de Mercado Pago configurado en .env")

    # Endpoint correcto para in-store QR v2
    url = f"{BASE_URL}/instore/qr/v2/orders"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": str(uuid.uuid4()),
    }
    payload = {
        "external_reference": external_ref,
        "title": descripcion,
        "description": descripcion,
        "expiration_time": "PT5M",
        "cash_outs": [
            {
                "amount": round(monto, 2),
                "external_reference": external_ref,
            }
        ],
        "sponsor": {"id": _resolve_user_id(token)},
    }
    print(f"[mp_qr] Enviando orden QR ${monto:.2f} | ref={external_ref}")
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    if response.status_code not in (200, 201):
        print(f"[mp_qr] Error {response.status_code} al crear orden: {response.text}")
        response.raise_for_status()
    data = response.json()
    print(
        f"[mp_qr] Orden creada OK | id={data.get('id')} | status={data.get('status')}"
    )
    return data


async def cancelar_orden_qr(orden_id: str) -> bool:
    """Cancela una orden QR en Mercado Pago."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _cancelar_orden_qr_sync, orden_id)


def _cancelar_orden_qr_sync(orden_id: str) -> bool:
    token = _resolve_token()
    if not token:
        print("[mp_qr] No hay token configurado; no se puede cancelar.")
        return False

    url = f"{BASE_URL}/instore/qr/v2/orders/{orden_id}/cancel"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": str(uuid.uuid4()),
    }
    print(f"[mp_qr] Cancelando orden {orden_id}...")
    response = requests.post(url, headers=headers, timeout=15)
    if response.status_code in (200, 201):
        print(f"[mp_qr] Orden {orden_id} cancelada OK")
        return True
    print(f"[mp_qr] Error {response.status_code} al cancelar: {response.text}")
    return False


async def verificar_estado_orden(orden_id: str) -> str:
    """Consulta el estado de la orden. Retorna: open | paid | expired | cancelled | unknown."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _verificar_estado_orden_sync, orden_id)


def _verificar_estado_orden_sync(orden_id: str) -> str:
    token = _resolve_token()
    if not token:
        return "error"
    url = f"{BASE_URL}/instore/qr/v2/orders/{orden_id}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers, timeout=15)
    if response.status_code == 200:
        data = response.json()
        return data.get("status", "unknown")
    print(f"[mp_qr] Error {response.status_code} al consultar: {response.text}")
    return "error"


async def buscar_y_cancelar_ordenes_abiertas(max_ordenes: int = 20) -> int:
    """Busca órdenes en estado 'open' y las cancela. Útil al iniciar el kiosko
    después de un apagón. Retorna la cantidad cancelada."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _buscar_y_cancelar_ordenes_abiertas_sync, max_ordenes
    )


def _buscar_y_cancelar_ordenes_abiertas_sync(max_ordenes: int) -> int:
    token = _resolve_token()
    if not token:
        return 0

    # Listar órdenes recientes; filtrar manualmente las que siguen 'open'.
    # Si la API no está habilitada en la cuenta, este endpoint devuelve 404 o 405.
    # En ese caso, retornamos 0 silenciosamente (no es crítico para la operación normal).
    list_url = f"{BASE_URL}/v1/orders/search"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "status": "open",
        "sort": "date_created",
        "criteria": "desc",
        "limit": max_ordenes,
    }
    try:
        response = requests.post(list_url, headers=headers, json=payload, timeout=15)
        if response.status_code in (404, 405):
            # API no habilitada (in-store QR); no es error crítico
            return 0
        if response.status_code != 200:
            print(f"[mp_qr] No se pudo listar órdenes: HTTP {response.status_code}")
            return 0
        data = response.json()
        orders = data.get("results", data.get("elements", []))
    except Exception as e:
        print(f"[mp_qr] Excepción listando órdenes: {e}")
        return 0

    canceladas = 0
    for o in orders:
        oid = o.get("id")
        if not oid:
            continue
        try:
            cancel_url = f"{BASE_URL}/v1/orders/{oid}/cancel"
            r = requests.post(
                cancel_url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "X-Idempotency-Key": str(uuid.uuid4()),
                },
                timeout=15,
            )
            if r.status_code in (200, 201):
                print(f"[mp_qr] Orden huérfana {oid} cancelada (apagón)")
                canceladas += 1
            else:
                print(f"[mp_qr] No se pudo cancelar {oid}: HTTP {r.status_code}")
        except Exception as e:
            print(f"[mp_qr] Excepción cancelando {oid}: {e}")
    return canceladas


def _preferido_pos(results: list) -> Optional[dict]:
    """Elige el POS más adecuado para el QR estático.
    Preferimos el POS con nombre o external_id 'CAJA01'."""
    for pos in results:
        name = (pos.get("name") or "").strip().upper()
        ext_id = (pos.get("external_id") or "").strip().upper()
        if name == "CAJA01" or ext_id == "CAJA01":
            return pos
    return results[0] if results else None


def obtener_qr_estatico() -> Optional[str]:
    """Obtiene la URL de la imagen QR estática del POS registrado.
    Sirve como fallback cuando el producto 'instore/qr' no está habilitado
    en la cuenta (404 en API). El operador cobra el monto manualmente en la app POS.
    Retorna None si no hay POS registrado."""
    token = _resolve_token()
    if not token:
        return None
    try:
        resp = requests.get(
            f"{BASE_URL}/pos",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        results = data.get("results", [])
        pos = _preferido_pos(results)
        if pos is None:
            return None
        print(
            f"[mp_qr] Usando QR estático del POS: {pos.get('name')} (id={pos.get('id')})"
        )
        return pos.get("qr", {}).get("image")
    except Exception as e:
        print(f"[mp_qr] Error al obtener QR estático: {e}")
        return None


async def obtener_qr_estatico_async() -> Optional[str]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, obtener_qr_estatico)
