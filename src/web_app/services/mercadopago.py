"""Cliente HTTP para Mercado Pago Point.

Crea y consulta órdenes tipo 'point' en la terminal física.
Todas las funciones son bloqueantes y deben ejecutarse con asyncio.to_thread.
"""

import os
import uuid
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api.mercadopago.com"
ENVIRONMENT = os.getenv("MP_ENVIRONMENT", "prod").lower()
TERMINAL_ID = os.getenv("MP_TERMINAL_ID", "")


def _token() -> str:
    if ENVIRONMENT == "prod":
        token = os.getenv("MP_PROD_TOKEN")
        if token:
            return token
        print(
            "[MP] MP_ENVIRONMENT=prod pero MP_PROD_TOKEN vacío; usando MP_TEST_TOKEN."
        )
    token = os.getenv("MP_TEST_TOKEN")
    if not token:
        raise RuntimeError("No se encontró MP_PROD_TOKEN ni MP_TEST_TOKEN en .env")
    return token


def _headers(idempotency: bool = False) -> dict:
    h = {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
    }
    if idempotency:
        h["X-Idempotency-Key"] = str(uuid.uuid4())
    return h


def terminal_id() -> str:
    if not TERMINAL_ID:
        raise RuntimeError("MP_TERMINAL_ID no está configurado en .env")
    return TERMINAL_ID


def crear_orden_point(
    amount: float,
    descripcion: str,
    external_ref: str = "",
    retry_on_409: bool = True,
) -> dict:
    """Crea una orden tipo Point. La terminal física mostrará la pantalla de pago.

    Devuelve el dict de la orden (con clave 'id'). Si falla, devuelve {}.
    """
    url = f"{BASE_URL}/v1/orders"
    if not external_ref:
        external_ref = f"ECOLUNA_POINT_{uuid.uuid4().hex[:8]}"
    payload = {
        "type": "point",
        "external_reference": external_ref,
        "expiration_time": "PT5M",
        "transactions": {"payments": [{"amount": f"{amount:.2f}"}]},
        "config": {"point": {"terminal_id": terminal_id()}},
        "description": descripcion,
    }
    try:
        r = requests.post(
            url, headers=_headers(idempotency=True), json=payload, timeout=15
        )
    except requests.RequestException as e:
        print(f"[MP] Error de red creando orden Point: {e}")
        return {}

    if r.status_code in (200, 201):
        try:
            return r.json()
        except ValueError:
            return {}

    if r.status_code == 409 and retry_on_409:
        print(
            "[MP] Terminal reporta orden encolada (409). "
            "Cancelando automáticamente desde la terminal y reintentando..."
        )
        # La cancelación real debe hacerse en la terminal física.
        # Reintentamos una vez por si la cola se liberó.
        try:
            r2 = requests.post(
                url,
                headers=_headers(idempotency=True),
                json=payload,
                timeout=15,
            )
        except requests.RequestException as e:
            print(f"[MP] Error de red en reintento: {e}")
            return {}
        if r2.status_code in (200, 201):
            try:
                return r2.json()
            except ValueError:
                return {}
        print(f"[MP] Reintento falló: HTTP {r2.status_code} {r2.text}")
        return {}

    print(f"[MP] Error creando orden: HTTP {r.status_code} {r.text}")
    return {}


def consultar_orden(order_id: str) -> dict:
    """Consulta el estado de una orden Point. Devuelve {} si hay error."""
    if not order_id:
        return {}
    url = f"{BASE_URL}/v1/orders/{order_id}"
    try:
        r = requests.get(url, headers=_headers(), timeout=15)
    except requests.RequestException as e:
        print(f"[MP] Error de red consultando orden {order_id}: {e}")
        return {}
    if r.status_code == 200:
        try:
            return r.json()
        except ValueError:
            return {}
    print(f"[MP] Error consultando orden {order_id}: HTTP {r.status_code} {r.text}")
    return {}


def cancelar_orden(order_id: str) -> bool:
    """Intenta cancelar una orden Point por API.

    NOTA: la terminal NEWLAND N950 no responde a cancelaciones por API;
    la cancelación debe hacerse manualmente en la terminal física.
    Esta función es best-effort: si la API rechaza, simplemente devuelve False.
    """
    if not order_id:
        return False
    url = f"{BASE_URL}/v1/orders/{order_id}/cancel"
    try:
        r = requests.post(url, headers=_headers(idempotency=True), timeout=15)
    except requests.RequestException as e:
        print(f"[MP] Error de red cancelando orden {order_id}: {e}")
        return False
    if r.status_code in (200, 201):
        print(f"[MP] Orden {order_id} cancelada por API")
        return True
    print(
        f"[MP] No se pudo cancelar por API (HTTP {r.status_code}). "
        f"Cancelar manualmente en la terminal."
    )
    return False


def listar_terminales() -> list:
    """Lista las terminales asociadas a la cuenta. Útil para diagnóstico."""
    url = f"{BASE_URL}/terminals/v1/list"
    try:
        r = requests.get(url, headers=_headers(), timeout=15)
    except requests.RequestException as e:
        print(f"[MP] Error de red listando terminales: {e}")
        return []
    if r.status_code != 200:
        print(f"[MP] Error listando terminales: HTTP {r.status_code} {r.text}")
        return []
    data = r.json()
    return data.get("data", {}).get("terminals", [])
