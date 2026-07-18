"""Entry point de EcoLuna Kiosko (v2).

Levanta el servidor NiceGUI en `http://localhost:8000`.

Uso (cualquiera de las 3 formas funciona, gracias al sys.path inyectado):
    cd src/app && python main.py            # producción (en la Pi con hardware)
    cd src/app && python main.py test       # modo test (sin GPIO)
    cd src     && python -m app.main         # equivalente
    cd src     && python -m app.main test    # equivalente en modo test
    python src/app/main.py                   # también desde la raíz del repo
    python src/app/main.py test              # idem en modo test
"""

# Asegurar que el paquete `app` sea importable cuando se ejecute como
# `python main.py` desde `src/app/`. Python agrega el directorio del script
# a sys.path, no el padre. Esta línea fuerza que `src/` esté disponible.
import sys
from pathlib import Path as _Path

_SRC = _Path(__file__).resolve().parent.parent  # src/app/main.py → src/
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import asyncio
import base64
from pathlib import Path

from nicegui import app, ui

from app.config import (
    DATA_DIR,
    DB_PATH,
    MEDIA_DIR,
    PORT,
    STATIC_DIR,
    STORAGE_SECRET,
    TITLE,
)


from app.adaptadores.hardware.gpio import HARDWARE_AVAILABLE, init_gpio_lavadoras
from app.adaptadores.hardware.monedero import LectorMonedas
from app.adaptadores.mercado_pago import polling as mp_polling
from app.core import loader
from app.core.estados import MetodoPago
from app.core.maquinas import set_cargador
from app.eventos.bus import bus
from app.eventos.tipos import (
    EventoDominio,
    TIPO_ORDEN_CANCELADA,
    TIPO_ORDEN_CREADA,
    TIPO_PAGO_CANCELADO,
    TIPO_PAGO_CONFIRMADO,
    TIPO_PESO_APROBADO,
    TIPO_PESO_RECHAZADO,
    pago_cancelado,
    pago_confirmado,
)
from app.repo import db
from app.repo import maquinas as repo_maquinas
from app.ui.kiosko import pagina as kiosko_pagina
from app.ui.kiosko.wizard import Paso
from app.ui.admin import login as admin_login
from app.ui.admin import dashboard as admin_dashboard


TEST_MODE = "test" in sys.argv


def _favicon_data_url() -> str:
    """Favicon pequeño. El dataURL de un PNG de 100KB inflaba el HTML
    inicial y rompía el WebSocket de NiceGUI con 'Message too long'.
    Usamos un emoji Unicode (4 bytes) que se envía inline."""
    return "🌙"


def _bootstrap() -> None:
    """Carga la DB, los catálogos y arranca hardware + polling."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db.init_db()
    loader.instalar_como_defaults()
    # Cargar catálogo de máquinas (cache en memoria)
    set_cargador(lambda: _cargar_equipos())


def _cargar_equipos() -> dict:
    return {
        m.codigo: {
            "codigo": m.codigo,
            "nombre": m.nombre,
            "tipo": m.tipo,
            "capacidad_kg": m.capacidad_kg,
            "gpio": m.gpio,
            "modo": m.modo,
            "duracion_max_min": m.duracion_max_min,
        }
        for m in repo_maquinas._listar(solo_activas=True)
    }


_mon: LectorMonedas | None = None


def _arrancar_monedero() -> None:
    """En modo test, el monedero recibe pulsos por teclado.
    En la Pi, escucha el pin 21 via gpiozero."""
    global _mon
    _mon = LectorMonedas(_on_moneda)


def _on_moneda(monto: int) -> None:
    """Suma monedas al wizard del kiosko cliente (storage compartido)."""
    from dataclasses import asdict, replace
    from app.ui.kiosko.wizard import WizardKiosko

    raw = app.storage.general.get("kiosko_wizard")
    if raw is None:
        return
    w = WizardKiosko(**raw)
    if w.paso is not Paso.PAGO or w.metodo is not MetodoPago.MONEDAS:
        return
    nuevo = replace(w, dinero=w.dinero + monto)
    app.storage.general["kiosko_wizard"] = asdict(nuevo)
    # Refresco vía bus para que el cliente re-renderice
    bus.publish(
        EventoDominio(
            tipo="kiosko.refresh",
            orden_id=0,
            extra={"motivo": "moneda"},
            cuando=__import__("datetime").datetime.now(),
        )
    )


def _arrancar_polling_mp() -> None:
    """Inicia el polling de Mercado Pago Point."""
    if TEST_MODE:
        return  # En test mode no hay terminal real
    try:
        mp_polling.iniciar(_notificar_mp)
    except RuntimeError as e:
        print(f"[MP] No se pudo iniciar el polling: {e}")


async def _notificar_mp(tipo: str, id_orden: str) -> None:
    """Callback del polling. Publica en el bus global."""
    if tipo == "pago.confirmado":
        bus.publish(pago_confirmado(int(id_orden), folio=""))
    elif tipo == "pago.cancelado":
        bus.publish(pago_cancelado(int(id_orden), motivo="mp"))


@app.on_startup
async def _on_startup() -> None:
    _bootstrap()
    _arrancar_monedero()
    init_gpio_lavadoras()
    _arrancar_polling_mp()


@app.on_shutdown
async def _on_shutdown() -> None:
    await mp_polling.detener()


@app.post("/api/kiosko/moneda")
async def _api_moneda(monto: int) -> dict:
    """Endpoint interno para que el teclado simulado inyecte monedas
    en el kiosko cliente (solo en TEST_MODE)."""
    if not TEST_MODE:
        return {"ok": False, "error": "Solo en modo test"}
    _on_moneda(monto)
    return {"ok": True, "monto": monto}


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if STATIC_DIR.exists():
        app.add_static_files("/static", str(STATIC_DIR))
    if MEDIA_DIR.exists():
        app.add_static_files("/media", str(MEDIA_DIR))

    # Registrar todas las páginas (los @ui.page se importan en sus módulos)
    from app.ui.admin import login as _admin_login
    from app.ui.admin import dashboard as _admin_dashboard
    from app.ui.admin import operativo as _admin_operativo
    from app.ui.admin import autoservicio as _admin_autoservicio
    from app.ui.admin import personalizado as _admin_personalizado
    from app.ui.admin import cortes as _admin_cortes
    from app.ui.admin.superadmin import pagina as _admin_superadmin

    _ = (
        _admin_login,
        _admin_dashboard,
        _admin_operativo,
        _admin_autoservicio,
        _admin_personalizado,
        _admin_cortes,
        _admin_superadmin,
    )  # evita warning de unused

    modo = "TEST" if TEST_MODE else "PROD"
    print(f"[{modo}] Iniciando EcoLuna Kiosko v2 en http://localhost:{PORT}")
    print(f"[{modo}] gpio disponible: {HARDWARE_AVAILABLE}")
    try:
        ui.run(
            title=TITLE,
            port=PORT,
            favicon=_favicon_data_url(),
            reload=False,
            show=False,
            storage_secret=STORAGE_SECRET,
        )
    except KeyboardInterrupt:
        print("\nStop app by KeyboardInterrupt.\n")


if __name__ in {"__main__", "__mp_main__"}:
    main()
