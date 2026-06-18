"""Prueba física de cobro en terminal Point (Mercado Pago).

Este script:
  1. Lista las terminales asociadas a la cuenta.
  2. Crea una orden de cobro tipo 'point' para una terminal específica.
  3. Hace polling del estado hasta que se pague, expire o se cancele.

Uso:
    cd src/mp_dev && python test_point_terminal.py
    cd src/mp_dev && python test_point_terminal.py --terminal-id TERMINAL_ID --amount 35.00

Requiere MP_TEST_TOKEN (o MP_PROD_TOKEN si MP_ENVIRONMENT=prod) en el .env
 del proyecto raíz. La terminal Point debe estar encendida y vinculada.

Nota sobre error 409 (already_queued_order_on_terminal):
  Si la terminal responde 409 aunque no tenga cobros visibles, reinicia la
  terminal, desvincúlala y vuelve a vincularla. Si persiste, el bloqueo está
  del lado de Mercado Pago; contacta a soporte con el terminal_id.
"""

import os
import sys
import uuid
import json
import time
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

BASE_URL = "https://api.mercadopago.com"
ENVIRONMENT = os.getenv("MP_ENVIRONMENT", "test").lower()


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


def list_terminals(token: str):
    print("\n=== Terminales asociadas (/terminals/v1/list) ===")
    url = f"{BASE_URL}/terminals/v1/list"
    r = requests.get(url, headers=_headers(token), timeout=15)
    _print_curl("GET", url, _headers(token))
    print(f"HTTP {r.status_code}")
    print(r.text)
    if r.status_code == 200:
        data = r.json()
        # La respuesta real tiene formato {"data": {"terminals": [...]}}
        terminals = (
            data
            if isinstance(data, list)
            else data.get("data", {}).get("terminals", [])
        )
        print(f"\nTerminales encontradas: {len(terminals)}")
        for t in terminals:
            print("-" * 40)
            print(json.dumps(t, indent=2, ensure_ascii=False))
        return terminals
    return []


def create_point_order(
    token: str,
    terminal_id: str,
    amount: float,
    description: str,
    retry_on_409: bool = True,
) -> dict:
    print("\n=== Crear orden tipo Point (/v1/orders) ===")
    url = f"{BASE_URL}/v1/orders"
    ref = f"ECOLUNA_POINT_{uuid.uuid4().hex[:8]}"
    payload = {
        "type": "point",
        "external_reference": ref,
        "expiration_time": "PT5M",
        "transactions": {"payments": [{"amount": f"{amount:.2f}"}]},
        "config": {
            "point": {
                "terminal_id": terminal_id,
            }
        },
        "description": description,
    }
    headers = _headers(token, idempotency=True)
    _print_curl("POST", url, headers, payload)
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    print(f"HTTP {r.status_code}")
    print(r.text)
    if r.status_code in (200, 201):
        return r.json()
    if r.status_code == 409 and retry_on_409:
        print("\n[INFO] La terminal reporta una orden encolada. Intentando limpiar...")
        clear_queued_orders(token, terminal_id)
        print("\n[INFO] Reintentando crear la orden...")
        return create_point_order(
            token, terminal_id, amount, description, retry_on_409=False
        )
    return {}


def get_order_status(token: str, order_id: str) -> dict:
    url = f"{BASE_URL}/v1/orders/{order_id}"
    r = requests.get(url, headers=_headers(token), timeout=15)
    if r.status_code == 200:
        return r.json()
    print(
        f"[ERROR] No se pudo consultar orden {order_id}: HTTP {r.status_code} {r.text}"
    )
    return {}


def cancel_order(token: str, order_id: str) -> bool:
    print(f"\n=== Cancelar orden {order_id} ===")
    url = f"{BASE_URL}/v1/orders/{order_id}/cancel"
    headers = _headers(token, idempotency=True)
    _print_curl("POST", url, headers)
    r = requests.post(url, headers=headers, timeout=15)
    print(f"HTTP {r.status_code}")
    print(r.text)
    return r.status_code in (200, 201)


def clear_queued_orders(token: str, terminal_id: str) -> int:
    """Intenta cancelar órdenes encoladas.

    Nota: Mercado Pago no expone un endpoint público confiable para listar
    órdenes Point por terminal. Si la terminal sigue reportando 409 después
    de reiniciarla y re-vincularla, el bloqueo suele estar del lado de MP y
    requiere soporte técnico.
    """
    print("\n=== No se pueden listar órdenes Point por terminal ===")
    print(
        "Mercado Pago no expone un endpoint público para buscar órdenes Point "
        "por terminal_id. Si la terminal reporta 409, reiníciala o contacta "
        "a soporte de Mercado Pago con el terminal_id."
    )
    return 0


def poll_order(token: str, order_id: str, timeout: int = 300, interval: int = 5):
    print(f"\n=== Haciendo polling de la orden {order_id} ===")
    print(f"Tiempo máximo: {timeout}s | Intervalo: {interval}s")
    print("Esperando pago en la terminal física...")
    start = time.time()
    while time.time() - start < timeout:
        data = get_order_status(token, order_id)
        status = data.get("status", "unknown")
        print(f"[{int(time.time() - start)}s] status={status}")
        if status == "paid":
            print("\n✅ ¡Pago recibido!")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return data
        if status in ("cancelled", "expired", "error"):
            print(f"\n⚠️ Orden finalizada con estado: {status}")
            return data
        time.sleep(interval)
    print("\n⏰ Tiempo de espera agotado.")
    return {}


def main():
    parser = argparse.ArgumentParser(
        description="Prueba física de cobro en terminal Point de Mercado Pago"
    )
    parser.add_argument(
        "--terminal-id",
        type=str,
        default=None,
        help=(
            "ID real de la terminal Point "
            "(ej: NEWLAND_N950__N950NCC904817363). "
            "Si no lo sabes, omite este argumento y el script listará las terminales."
        ),
    )
    parser.add_argument(
        "--amount",
        type=float,
        default=35.00,
        help="Monto a cobrar (default: 35.00)",
    )
    parser.add_argument(
        "--description",
        type=str,
        default="Ciclo de Lavado EcoLuna",
        help="Descripción del cobro",
    )
    parser.add_argument(
        "--no-poll",
        action="store_true",
        help="No esperar por el pago; solo crear la orden",
    )
    parser.add_argument(
        "--clear-queued",
        action="store_true",
        help="Solo buscar y cancelar órdenes encoladas en la terminal",
    )
    args = parser.parse_args()

    print("Prueba física de terminal Point - EcoLuna")
    print(f"Entorno: {ENVIRONMENT}")

    token = _token()

    terminal_id = args.terminal_id
    if terminal_id in (None, "", "TERMINAL_ID"):
        print("\n[INFO] No se proporcionó un --terminal-id válido.")
        print("Listando terminales disponibles para que copies el ID real...\n")
        terminals = list_terminals(token)
        if terminals:
            # Preferir la primera terminal activa
            terminal_id = terminals[0].get("id") or terminals[0].get("terminal_id")
            print(f"\nUsando terminal detectada: {terminal_id}")
        else:
            print(
                "\n[ERROR] No se detectó ninguna terminal. "
                "Asegúrate de que la Point esté encendida y vinculada, "
                "o proporciona --terminal-id con el ID real."
            )
            sys.exit(1)

    if args.clear_queued:
        cleared = clear_queued_orders(token, terminal_id)
        print(f"\n[INFO] Órdenes canceladas: {cleared}")
        sys.exit(0)

    order = create_point_order(token, terminal_id, args.amount, args.description)
    if not order.get("id"):
        print(
            "\n[ERROR] No se pudo crear la orden. Revisa los mensajes de error arriba."
        )
        sys.exit(1)

    print(f"\n✅ Orden creada: {order['id']}")
    print("La terminal física debería mostrar la pantalla de pago.")

    if args.no_poll:
        print("\n--no-poll activado. Saliendo sin esperar el pago.")
        return

    try:
        poll_order(token, order["id"])
    except KeyboardInterrupt:
        print("\n\n[INTERRUMPIDO] Cancelando orden...")
        cancel_order(token, order["id"])


if __name__ == "__main__":
    main()
