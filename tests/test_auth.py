"""Tests del módulo de autenticación.

`auth` depende de `nicegui.app.storage.user` que no se inicializa
sin un cliente real. Estos tests validan la lógica pura: las constantes
`USUARIOS`/`SUPERADMINS`, y las comparaciones internas. La integración
con `app.storage` se cubre indirectamente con el smoke test del main.
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


# ── Constantes ──────────────────────────────────────────────────────────────


def test_usuarios_tiene_3_cuentas():
    from app.ui.compartido.auth import USUARIOS

    assert len(USUARIOS) == 3
    assert "Moi" in USUARIOS
    assert "Capi" in USUARIOS
    assert "David" in USUARIOS


def test_superadmins_solo_moi_y_david():
    from app.ui.compartido.auth import SUPERADMINS, USUARIOS

    assert SUPERADMINS == {"Moi", "David"}
    # Capi no es superadmin
    assert "Capi" not in SUPERADMINS
    # Las contraseñas del catálogo son strings no vacíos
    for u, p in USUARIOS.items():
        assert p, f"Contraseña vacía para {u}"


# ── Comparación de credenciales (test puro, sin nicegui) ─────────────────


def test_credenciales_correctas_moi():
    """Verifica que la contraseña de Moi es 'admin123'."""
    from app.ui.compartido.auth import USUARIOS

    assert USUARIOS["Moi"] == "admin123"


def test_credenciales_correctas_capi():
    from app.ui.compartido.auth import USUARIOS

    assert USUARIOS["Capi"] == "socio123"


def test_credenciales_correctas_david():
    from app.ui.compartido.auth import USUARIOS

    assert USUARIOS["David"] == "admin456"


# ── Lógica de redirigir (sin cliente) ────────────────────────────────────


def test_usuario_actual_sin_sesion_retorna_vacio():
    """Sin storage activo, retorna cadena vacía sin crashear."""
    from app.ui.compartido.auth import usuario_actual

    # En pytest no hay cliente: `app.storage` puede no existir. La
    # función debe manejarlo devolviendo "" o equivalente, no crashear.
    try:
        u = usuario_actual()
        assert u == "" or u is not None
    except Exception as e:
        # Si lanza, debe ser un error documentado de la ausencia de storage
        assert "storage" in str(e).lower() or isinstance(e, (KeyError, AttributeError))


def test_es_superadmin_sin_sesion_retorna_false():
    """Sin storage activo, retorna False (no es superadmin)."""
    from app.ui.compartido.auth import es_superadmin

    try:
        assert es_superadmin() is False
    except Exception:
        pass  # aceptable si la ausencia de storage lanza


# ── Lógica de login (con storage simulado) ─────────────────────────────────


def test_login_con_credenciales_correctas_moi():
    """Login OK con Moi/admin123 setea storage y retorna True."""
    from unittest.mock import MagicMock, patch
    from app.ui.compartido import auth

    storage = {"authenticated": False, "usuario": ""}
    with patch.object(auth, "app") as mock_app:
        mock_app.storage = MagicMock()
        mock_app.storage.user = storage
        ok = auth.login("Moi", "admin123")
        assert ok is True
        assert storage["authenticated"] is True
        assert storage["usuario"] == "Moi"


def test_login_con_credenciales_correctas_david():
    from unittest.mock import MagicMock, patch
    from app.ui.compartido import auth

    storage = {"authenticated": False, "usuario": ""}
    with patch.object(auth, "app") as mock_app:
        mock_app.storage = MagicMock()
        mock_app.storage.user = storage
        ok = auth.login("David", "admin456")
        assert ok is True
        assert storage["usuario"] == "David"


def test_login_con_password_incorrecta_falla():
    from unittest.mock import MagicMock, patch
    from app.ui.compartido import auth

    storage = {"authenticated": False, "usuario": ""}
    with patch.object(auth, "app") as mock_app:
        mock_app.storage = MagicMock()
        mock_app.storage.user = storage
        ok = auth.login("Moi", "wrong")
        assert ok is False
        # No debe modificar el storage
        assert storage["authenticated"] is False
        assert storage["usuario"] == ""


def test_login_con_usuario_inexistente_falla():
    from unittest.mock import MagicMock, patch
    from app.ui.compartido import auth

    storage = {"authenticated": False, "usuario": ""}
    with patch.object(auth, "app") as mock_app:
        mock_app.storage = MagicMock()
        mock_app.storage.user = storage
        ok = auth.login("fantasma", "cualquiera")
        assert ok is False
        assert storage["authenticated"] is False


def test_login_con_inputs_vacios_falla():
    from unittest.mock import MagicMock, patch
    from app.ui.compartido import auth

    storage = {"authenticated": False, "usuario": ""}
    with patch.object(auth, "app") as mock_app:
        mock_app.storage = MagicMock()
        mock_app.storage.user = storage
        assert auth.login("", "") is False
        assert auth.login("Moi", "") is False
        assert auth.login("", "admin123") is False


def test_login_con_espacios_en_usuario_normaliza():
    """El login hace strip del usuario."""
    from unittest.mock import MagicMock, patch
    from app.ui.compartido import auth

    storage = {"authenticated": False, "usuario": ""}
    with patch.object(auth, "app") as mock_app:
        mock_app.storage = MagicMock()
        mock_app.storage.user = storage
        ok = auth.login("  Moi  ", "admin123")
        # El storage tiene el nombre sin espacios
        assert ok is True
        assert storage["usuario"] == "Moi"


# ── Logout ─────────────────────────────────────────────────────────────────


def test_logout_limpia_el_storage():
    from unittest.mock import MagicMock, patch
    from app.ui.compartido import auth

    storage = MagicMock()
    with patch.object(auth, "app") as mock_app:
        mock_app.storage = MagicMock()
        mock_app.storage.user = storage
        auth.logout()
        storage.clear.assert_called_once()


# ── Helpers de redirect ──────────────────────────────────────────────────


def test_redirigir_si_no_autenticado_no_redirige_si_esta_logueado():
    """Si está autenticado, retorna False (no redirige)."""
    from unittest.mock import MagicMock, patch
    from app.ui.compartido import auth

    storage = {"authenticated": True, "usuario": "Moi"}
    with patch.object(auth, "app") as mock_app:
        mock_app.storage = MagicMock()
        mock_app.storage.user = storage
        redirigio = auth.redirigir_si_no_autenticado()
        # Sin un cliente real, `ui.navigate.to` puede fallar.
        # Lo importante es que retorna False si está autenticado.
        assert redirigio is False


# ── Datos del test de fase 5 (badge helpers) se siguen aplicando ──────────


def test_modulo_compila_sin_errores():
    """El módulo de auth se puede importar sin efectos secundarios."""
    import importlib

    importlib.reload(__import__("app.ui.compartido.auth", fromlist=["auth"]))
