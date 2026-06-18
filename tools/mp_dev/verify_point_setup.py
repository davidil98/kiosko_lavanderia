"""Verifica la configuración de Store, POS y Terminal Point en Mercado Pago.

Uso:
    cd src/mp_dev && python verify_point_setup.py

El script toma automáticamente el store_id y pos_id de la primera terminal
listada en /terminals/v1/list.
"""

import os
import sys
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


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def main():
    token = _token()
    headers = _headers(token)

    print("=" * 60)
    print("Verificación de configuración Point")
    print(f"Entorno: {ENVIRONMENT}")
    print("=" * 60)

    # 1. Terminales
    print("\n--- Terminales (/terminals/v1/list) ---")
    r = requests.get(f"{BASE_URL}/terminals/v1/list", headers=headers, timeout=15)
    print(f"HTTP {r.status_code}")
    if r.status_code != 200:
        print(r.text)
        sys.exit(1)
    data = r.json()
    terminals = data.get("data", {}).get("terminals", [])
    if not terminals:
        print("[ERROR] No hay terminales vinculadas.")
        sys.exit(1)
    for t in terminals:
        print(f"\nTerminal:")
        for k, v in t.items():
            print(f"  {k}: {v}")

    terminal = terminals[0]
    terminal_id = terminal.get("id")
    pos_id = terminal.get("pos_id")
    store_id = terminal.get("store_id")

    # 2. POS
    print(f"\n--- POS (/pos/{pos_id}) ---")
    r = requests.get(f"{BASE_URL}/pos/{pos_id}", headers=headers, timeout=15)
    print(f"HTTP {r.status_code}")
    if r.status_code == 200:
        pos = r.json()
        for k, v in pos.items():
            print(f"  {k}: {v}")
    else:
        print(r.text)

    # 3. Store
    print(f"\n--- Store (/stores/{store_id}) ---")
    r = requests.get(f"{BASE_URL}/stores/{store_id}", headers=headers, timeout=15)
    print(f"HTTP {r.status_code}")
    if r.status_code == 200:
        store = r.json()
        for k, v in store.items():
            print(f"  {k}: {v}")
    else:
        print(r.text)

    # 4. User
    print("\n--- Cuenta (/users/me) ---")
    r = requests.get(f"{BASE_URL}/users/me", headers=headers, timeout=15)
    print(f"HTTP {r.status_code}")
    if r.status_code == 200:
        user = r.json()
        print(f"  user_id:  {user.get('id')}")
        print(f"  nickname: {user.get('nickname')}")
        print(f"  site_id:  {user.get('site_id')}")

    print("\n" + "=" * 60)
    print("Chequeos recomendados:")
    print("=" * 60)
    print("1. En la terminal física, verifica que esté logueada a esta cuenta de MP.")
    print("2. Verifica que la terminal tenga WiFi estable y acceso a internet.")
    print("3. Asegúrate de que el POS tenga un external_id no vacío.")
    print("4. En el dashboard de MP, confirma que la terminal aparezca 'Activa'.")
    print("5. Si la orden sigue sin llegar, reinicia la terminal y espera 1-2 min.")


if __name__ == "__main__":
    main()
