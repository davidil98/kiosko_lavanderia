"""conftest.py — fixtures globales de pytest.

Limpia el storage de NiceGUI antes de los tests E2E para que
el wizard del kiosko empiece siempre en SERVICIO (paso 0).

NiceGUI guarda `storage-general.json` en `<cwd>/.nicegui/` cuando
el servidor se ejecuta desde `src/app/`. Borramos la clave
`kiosko_wizard` del JSON para evitar estado stale entre ejecuciones.
"""

import json
import pathlib

import pytest


def _limpiar_wizard_storage() -> None:
    """Elimina la clave kiosko_wizard de todos los storage-general.json."""
    root = pathlib.Path(__file__).resolve().parent.parent

    candidatos = [
        root / "src" / "app" / ".nicegui" / "storage-general.json",
        root / "src" / ".nicegui" / "storage-general.json",
        root / ".nicegui" / "storage-general.json",
    ]

    for path in candidatos:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if "kiosko_wizard" in data:
                del data["kiosko_wizard"]
                path.write_text(json.dumps(data), encoding="utf-8")
                print(f"[conftest] Wizard limpiado de {path}")
        except Exception as exc:
            print(f"[conftest] No se pudo limpiar {path}: {exc}")


@pytest.fixture(autouse=False)
def wizard_storage_limpio():
    """Fixture: limpia el wizard storage antes de cada test que lo solicite."""
    _limpiar_wizard_storage()
    yield
    # No limpiamos después para poder inspeccionar el estado final


@pytest.fixture(scope="session", autouse=True)
def limpiar_wizard_al_inicio():
    """Limpia el wizard storage UNA VEZ al inicio de toda la suite E2E."""
    _limpiar_wizard_storage()
    yield
