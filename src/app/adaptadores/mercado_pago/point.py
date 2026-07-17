"""Operaciones contra la API de Mercado Pago Point (terminal física).

Funciones bloqueantes. Devuelven dicts; en caso de error de red o respuesta
no-2xx, devuelven `{}` o `False` según corresponda.
"""

import uuid
from typing import Optional

import requests

from .cliente import BASE_URL, headers, sesion, terminal_id


def _referencia_externa(external_ref: str = "") -> str:
    return external_ref or f"ECOLUNA_POINT_{uuid.uuid4().hex[:8]}"


def crear_orden_point(
    amount: float,
    descripcion: str,
    external_ref: str = "",
    *,
    reintentar_en_409: bool = True,
) -> dict:
    """Crea una orden tipo Point. Devuelve dict (con clave 'id') o {} si falla."""
    url = f"{BASE_URL}/v1/orders"
    payload = {
        "type": "point",
        "external_reference": _referencia_externa(external_ref),
        "expiration_time": "PT5M",
        "transactions": {"payments": [{"amount": f"{amount:.2f}"}]},
        "config": {"point": {"terminal_id": terminal_id()}},
        "description": descripcion,
    }
    try:
        r = requests.post(
            url, headers=headers(con_idempotency=True), json=payload, timeout=15
        )
    except requests.RequestException as e:
        print(f"[MP] Error de red creando orden Point: {e}")
        return {}

    if r.status_code in (200, 201):
        try:
            return r.json()
        except ValueError:
            return {}

    if r.status_code == 409 and reintentar_en_409:
        print("[MP] 409 (orden encolada en terminal). Reintentando una vez…")
        try:
            r2 = requests.post(
                url, headers=headers(con_idempotency=True), json=payload, timeout=15
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
        r = requests.get(url, headers=headers(), timeout=15)
    except requests.RequestException as e:
        print(f"[MP] Error de red consultando {order_id}: {e}")
        return {}
    if r.status_code == 200:
        try:
            return r.json()
        except ValueError:
            return {}
    print(f"[MP] Error consultando {order_id}: HTTP {r.status_code} {r.text}")
    return {}


def cancelar_orden(order_id: str) -> bool:
    """Best-effort: la N950 no responde a cancelaciones por API.

    Devuelve True si la API confirmó, False si rechazó o si hubo error.
    """
    if not order_id:
        return False
    url = f"{BASE_URL}/v1/orders/{order_id}/cancel"
    try:
        r = requests.post(url, headers=headers(con_idempotency=True), timeout=15)
    except requests.RequestException as e:
        print(f"[MP] Error de red cancelando {order_id}: {e}")
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
    """Lista terminales asociadas a la cuenta. Útil para diagnóstico."""
    url = f"{BASE_URL}/terminals/v1/list"
    try:
        r = requests.get(url, headers=headers(), timeout=15)
    except requests.RequestException as e:
        print(f"[MP] Error de red listando terminales: {e}")
        return []
    if r.status_code != 200:
        print(f"[MP] Error listando terminales: HTTP {r.status_code} {r.text}")
        return []
    return r.json().get("data", {}).get("terminals", [])


def extraer_folio_pago(data: dict) -> str:
    """Extrae el id del pago de la respuesta. '' si no hay."""
    try:
        pagos = data.get("transactions", {}).get("payments", [])
        if pagos:
            return str(pagos[0].get("id", ""))
    except (AttributeError, TypeError):
        pass
    return ""
