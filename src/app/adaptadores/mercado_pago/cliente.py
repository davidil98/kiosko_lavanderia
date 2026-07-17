"""Cliente HTTP para Mercado Pago.

Lee el token de `MP_ENVIRONMENT` (prod|test) y expone headers + helpers.
Las funciones son bloqueantes; los callers las ejecutan con
`asyncio.to_thread` o `db.run_in_executor`.
"""

import os
import uuid

import requests

from app.config import (
    MP_ENVIRONMENT,
    MP_PROD_TOKEN,
    MP_TERMINAL_ID,
    MP_TEST_TOKEN,
)

BASE_URL = "https://api.mercadopago.com"


def token() -> str:
    """Devuelve el token según MP_ENVIRONMENT. Fallback documentado."""
    if MP_ENVIRONMENT == "prod" and MP_PROD_TOKEN:
        return MP_PROD_TOKEN
    if MP_ENVIRONMENT == "prod" and not MP_PROD_TOKEN:
        print(
            "[MP] MP_ENVIRONMENT=prod pero MP_PROD_TOKEN vacío; usando MP_TEST_TOKEN."
        )
    if MP_TEST_TOKEN:
        return MP_TEST_TOKEN
    raise RuntimeError("No se encontró MP_PROD_TOKEN ni MP_TEST_TOKEN en .env")


def terminal_id() -> str:
    if not MP_TERMINAL_ID:
        raise RuntimeError("MP_TERMINAL_ID no está configurado en .env")
    return MP_TERMINAL_ID


def headers(con_idempotency: bool = False) -> dict:
    h = {
        "Authorization": f"Bearer {token()}",
        "Content-Type": "application/json",
    }
    if con_idempotency:
        h["X-Idempotency-Key"] = str(uuid.uuid4())
    return h


def sesion() -> requests.Session:
    """Session con headers comunes. Reutilizable entre requests."""
    s = requests.Session()
    s.headers.update(
        {
            "Authorization": f"Bearer {token()}",
            "Content-Type": "application/json",
        }
    )
    return s
