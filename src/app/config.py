"""Configuración global: paths, constantes, .env.

Lee variables de entorno una sola vez al importar.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
APP_DIR = Path(__file__).resolve().parent
MEDIA_DIR = BASE_DIR / "media"
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = APP_DIR / "static"
DB_PATH = DATA_DIR / "ecoluna_datos.db"

BYPASS_PASSWORD = os.getenv("BYPASS_PASSWORD", "admin123")
MP_ENVIRONMENT = os.getenv("MP_ENVIRONMENT", "prod").lower()
MP_PROD_TOKEN = os.getenv("MP_PROD_TOKEN", "")
MP_TEST_TOKEN = os.getenv("MP_TEST_TOKEN", "")
MP_TERMINAL_ID = os.getenv("MP_TERMINAL_ID", "")

PORT = 8000
TITLE = "EcoLuna Kiosko"
STORAGE_SECRET = "ecoluna_kiosko_secret_2025"
