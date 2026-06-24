"""Verificación segura de credenciales y entorno de Mercado Pago.

No imprime el token completo; solo muestra máscara, entorno, user_id,
cajas (POS) y terminales asociadas.

Uso:
    cd src/mp_dev && python verify_mp_env.py
"""

import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
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


def _mask_token(token: str) -> str:
    if len(token) <= 12:
        return "***"
    return f"{token[:8]}...{token[-4:]}"


def main():
    token = _token()
    headers = {"Authorization": f"Bearer {token}"}

    print("=" * 50)
    print("Verificación de entorno Mercado Pago")
    print("=" * 50)
    print(f"MP_ENVIRONMENT: {ENVIRONMENT}")
    print(f"Token usado:    {_mask_token(token)}")

    print("\n--- /users/me ---")
    r = requests.get(f"{BASE_URL}/users/me", headers=headers, timeout=15)
    print(f"HTTP {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"user_id:        {data.get('id')}")
        print(f"nickname:       {data.get('nickname')}")
        print(f"site_id:        {data.get('site_id')}")
        print(f"status:         {data.get('status')}")
    else:
        print(r.text)

    print("\n--- /pos (cajas registradas) ---")
    r = requests.get(f"{BASE_URL}/pos", headers=headers, timeout=15)
    print(f"HTTP {r.status_code}")
    if r.status_code == 200:
        results = r.json().get("results", [])
        print(f"Cajas:          {len(results)}")
        for pos in results:
            print(
                f"  - id={pos.get('id')} external_id={pos.get('external_id')} "
                f"name={pos.get('name')} status={pos.get('status')}"
            )
    else:
        print(r.text)

    print("\n--- /terminals/v1/list ---")
    r = requests.get(f"{BASE_URL}/terminals/v1/list", headers=headers, timeout=15)
    print(f"HTTP {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        terminals = data.get("data", {}).get("terminals", [])
        print(f"Terminales:     {len(terminals)}")
        for t in terminals:
            print(
                f"  - id={t.get('id')} pos_id={t.get('pos_id')} "
                f"external_pos_id={t.get('external_pos_id')} "
                f"mode={t.get('operating_mode')}"
            )
    else:
        print(r.text)

    print("\n" + "=" * 50)
    print("Verificación completada")
    print("=" * 50)


if __name__ == "__main__":
    main()
