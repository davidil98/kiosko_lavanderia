"""Diagnóstico de integración QR de Mercado Pago.

Este script prueba secuencialmente los endpoints relevantes para determinar
por qué el flujo de QR dinámico (`/instore/qr/v2/orders`) no funciona en la
cuenta configurada, y muestra las alternativas disponibles (QR estático,
legacy in-store, etc.).

Uso:
    cd src/mp_dev && python test_qr_orden.py

Requiere MP_TEST_TOKEN (o MP_PROD_TOKEN si MP_ENVIRONMENT=prod) en el .env
 del proyecto raíz.
"""

import os
import sys
import uuid
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

BASE_URL = "https://api.mercadopago.com"
ENVIRONMENT = os.getenv("MP_ENVIRONMENT", "prod").lower()


def _token() -> str:
    if ENVIRONMENT == "prod":
        token = os.getenv("MP_PROD_TOKEN")
        if token:
            return token
        print(
            "[WARN] MP_ENVIRONMENT=prod pero MP_PROD_TOKEN vacío; usando MP_TEST_TOKEN."
        )
    token = os.getenv("MP_TEST_TOKEN")
    if not token:
        print("[ERROR] No se encontró MP_TEST_TOKEN en .env")
        sys.exit(1)
    return token


def _headers(token: str, idempotency: bool = False) -> dict:
    h = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    if idempotency:
        h["X-Idempotency-Key"] = str(uuid.uuid4())
    return h


def _print_curl(method: str, url: str, headers: dict, payload: dict | None = None):
    print("\n[curl equivalente]")
    header_str = " ".join(f'-H "{k}: {v}"' for k, v in headers.items())
    cmd = f"curl -X {method} {header_str} '{url}'"
    if payload:
        cmd += f" -d '{json.dumps(payload)}'"
    print(cmd)
    print()


def _check_ok(r: requests.Response, expected=(200, 201)) -> bool:
    ok = r.status_code in expected
    status_icon = "✅" if ok else "❌"
    print(f"{status_icon} HTTP {r.status_code}")
    return ok


def step_0_account_info(token: str) -> dict:
    print("\n" + "=" * 60)
    print("PASO 0: Información de la cuenta (/users/me)")
    print("=" * 60)
    url = f"{BASE_URL}/users/me"
    r = requests.get(url, headers=_headers(token), timeout=15)
    _print_curl("GET", url, _headers(token))
    _check_ok(r)
    data = r.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))
    return data


def step_1_pos_list(token: str):
    print("\n" + "=" * 60)
    print("PASO 1: Cajas (POS) registradas (/pos)")
    print("=" * 60)
    url = f"{BASE_URL}/pos"
    r = requests.get(url, headers=_headers(token), timeout=15)
    _print_curl("GET", url, _headers(token))
    if _check_ok(r):
        data = r.json()
        results = data.get("results", [])
        print(f"Cajas encontradas: {len(results)}")
        for pos in results:
            print("-" * 40)
            print(f"  id:          {pos.get('id')}")
            print(f"  external_id: {pos.get('external_id')}")
            print(f"  name:        {pos.get('name')}")
            print(f"  status:      {pos.get('status')}")
            print(f"  fixed_amount:{pos.get('fixed_amount')}")
            qr = pos.get("qr", {})
            print(f"  qr.template: {qr.get('template_document')}")
            print(f"  qr.image:    {qr.get('image')}")
            if qr.get("image"):
                print("  -> Puedes usar este QR.image como fallback estático.")
    else:
        print(r.text)


def step_2_create_qr_v2(token: str, user_id: int) -> dict:
    print("\n" + "=" * 60)
    print("PASO 2: Crear orden QR dinámica (/instore/qr/v2/orders)")
    print("=" * 60)
    url = f"{BASE_URL}/instore/qr/v2/orders"
    ref = f"TEST_QR_{uuid.uuid4().hex[:8]}"
    payload = {
        "external_reference": ref,
        "title": "Test EcoLuna QR",
        "description": "Orden de diagnóstico",
        "expiration_time": "PT5M",
        "cash_outs": [
            {
                "amount": 1.00,
                "external_reference": ref,
            }
        ],
        "sponsor": {"id": user_id},
    }
    headers = _headers(token, idempotency=True)
    _print_curl("POST", url, headers, payload)
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    ok = _check_ok(r)
    print(r.text)
    if ok:
        return r.json()
    return {}


def step_3_get_qr_v2(token: str, order_id: str):
    print("\n" + "=" * 60)
    print("PASO 3: Consultar orden QR creada")
    print("=" * 60)
    url = f"{BASE_URL}/instore/qr/v2/orders/{order_id}"
    r = requests.get(url, headers=_headers(token), timeout=15)
    _print_curl("GET", url, _headers(token))
    _check_ok(r)
    print(r.text)


def step_4_cancel_qr_v2(token: str, order_id: str):
    print("\n" + "=" * 60)
    print("PASO 4: Cancelar orden QR creada")
    print("=" * 60)
    url = f"{BASE_URL}/instore/qr/v2/orders/{order_id}/cancel"
    headers = _headers(token, idempotency=True)
    _print_curl("POST", url, headers)
    r = requests.post(url, headers=headers, timeout=15)
    _check_ok(r)
    print(r.text)


def step_5_legacy_instore(token: str, user_id: int):
    print("\n" + "=" * 60)
    print(
        "PASO 5: Endpoint legacy in-store (/instore/orders/qr/seller/collectors/{user_id}/pos/{external_pos_id}/qrs)"
    )
    print("=" * 60)
    print("Nota: Este endpoint legacy requiere external_pos_id de una caja.")
    # Primero obtenemos un external_pos_id
    pos_resp = requests.get(f"{BASE_URL}/pos", headers=_headers(token), timeout=15)
    if pos_resp.status_code != 200 or not pos_resp.json().get("results"):
        print("No hay cajas (POS) registradas para probar el endpoint legacy.")
        return
    pos = pos_resp.json()["results"][0]
    external_pos_id = pos.get("external_id")
    url = (
        f"{BASE_URL}/instore/orders/qr/seller/collectors/{user_id}"
        f"/pos/{external_pos_id}/qrs"
    )
    ref = f"TEST_LEGACY_{uuid.uuid4().hex[:8]}"
    payload = {
        "external_reference": ref,
        "title": "Test Legacy QR",
        "description": "Diagnóstico",
        "total_amount": 1.00,
        "items": [
            {
                "title": "Lavado",
                "unit_price": 1.00,
                "quantity": 1,
                "unit_measure": "unit",
                "total_amount": 1.00,
            }
        ],
        "cash_out": {"amount": 0},
        "expiration_date": "2030-12-31T23:59:59.000-04:00",
    }
    headers = _headers(token, idempotency=True)
    _print_curl("POST", url, headers, payload)
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    _check_ok(r)
    print(r.text)


def step_6_search_orders(token: str):
    print("\n" + "=" * 60)
    print("PASO 6: Buscar órdenes abiertas (/v1/orders/search)")
    print("=" * 60)
    url = f"{BASE_URL}/v1/orders/search"
    payload = {
        "status": "open",
        "sort": "date_created",
        "criteria": "desc",
        "limit": 5,
    }
    headers = _headers(token)
    _print_curl("POST", url, headers, payload)
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    _check_ok(r)
    print(r.text)


def main():
    print("Diagnóstico QR Mercado Pago")
    print(f"Entorno: {ENVIRONMENT}")
    print(f"Proyecto: {PROJECT_ROOT}")

    token = _token()

    account = step_0_account_info(token)
    user_id = account.get("id")
    if not user_id:
        print("[ERROR] No se pudo obtener el user_id; abortando.")
        sys.exit(1)

    step_1_pos_list(token)
    order = step_2_create_qr_v2(token, user_id)

    if order.get("id"):
        step_3_get_qr_v2(token, order["id"])
        step_4_cancel_qr_v2(token, order["id"])
    else:
        print(
            "\n[RESULTADO] La API de QR dinámico (/instore/qr/v2/orders) no está disponible."
        )
        print(
            "Esto suele significar que el producto 'QR modelo atendido' no está habilitado"
        )
        print(
            "en la cuenta de Mercado Pago. La app debería usar el fallback de QR estático."
        )

    step_5_legacy_instore(token, user_id)
    step_6_search_orders(token)

    print("\n" + "=" * 60)
    print("FIN DEL DIAGNÓSTICO")
    print("=" * 60)


if __name__ == "__main__":
    main()
