"""Tests de humo del entry point: el script arranca sin ModuleNotFoundError
desde cualquier cwd razonable, gracias al sys.path inyectado en main.py.
"""

import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
APP_DIR = SRC / "app"
VENV_PYTHON = ROOT / ".venv" / "bin" / "python3"


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)


def _wait_ready(port: int, timeout: float = 8.0) -> bool:
    """Hace polling hasta que el puerto responda o se agote el tiempo."""
    import socket

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.2)
    return False


@pytest.mark.skipif(not VENV_PYTHON.exists(), reason="venv no encontrado")
def test_main_agrega_src_a_sys_path_desde_src_app():
    """`cd src/app && python main.py` debe arrancar sin ModuleNotFoundError."""
    proc = subprocess.Popen(
        [str(VENV_PYTHON), "main.py"],
        cwd=APP_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={"PATH": str(VENV_PYTHON.parent), "HOME": str(ROOT)},
    )
    try:
        # Si el puerto se abre, el path se resolvió correctamente.
        ready = _wait_ready(8000)
        # Leemos stderr por si hay error temprano
        if not ready:
            time.sleep(0.5)
        stderr = (
            proc.stderr.read(2000).decode("utf-8", errors="replace")
            if proc.stderr
            else ""
        )
        assert "No module named 'app'" not in stderr, (
            f"main.py falló con ModuleNotFoundError:\n{stderr}"
        )
        assert "No module named 'src'" not in stderr
        assert ready, f"Servidor no arrancó. stderr={stderr}"
    finally:
        _stop(proc)


@pytest.mark.skipif(not VENV_PYTHON.exists(), reason="venv no encontrado")
def test_main_agrega_src_a_sys_path_desde_src_app():
    """`cd src/app && python main.py` debe arrancar sin ModuleNotFoundError."""
    log_path = ROOT / "tmp_test_main_src_app.log"
    log_file = open(log_path, "w")
    proc = subprocess.Popen(
        [str(VENV_PYTHON), "main.py"],
        cwd=APP_DIR,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env={"PATH": str(VENV_PYTHON.parent), "HOME": str(ROOT)},
    )
    try:
        ready = _wait_ready(8000, timeout=15)
        log_file.flush()
        log = log_path.read_text() if log_path.exists() else ""
        assert "No module named 'app'" not in log, (
            f"main.py falló con ModuleNotFoundError:\n{log[:2000]}"
        )
        assert "No module named 'src'" not in log, log[:2000]
        assert ready, f"Servidor no arrancó. log={log[:2000]}"
    finally:
        _stop(proc)
        log_file.close()
        try:
            log_path.unlink()
        except OSError:
            pass


@pytest.mark.skipif(not VENV_PYTHON.exists(), reason="venv no encontrado")
def test_main_arranca_desde_kiosko_pago_root():
    """`python src/app/main.py` desde la raíz del proyecto debe funcionar."""
    log_path = ROOT / "tmp_test_main_root.log"
    log_file = open(log_path, "w")
    proc = subprocess.Popen(
        [str(VENV_PYTHON), "src/app/main.py"],
        cwd=ROOT,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        env={"PATH": str(VENV_PYTHON.parent), "HOME": str(ROOT)},
    )
    try:
        ready = _wait_ready(8000, timeout=15)
        log_file.flush()
        log = log_path.read_text() if log_path.exists() else ""
        assert "No module named 'app'" not in log, log[:2000]
        assert ready, f"Servidor no arrancó. log={log[:2000]}"
    finally:
        _stop(proc)
        log_file.close()
        try:
            log_path.unlink()
        except OSError:
            pass


def test_main_docstring_actualizado():
    """El docstring de main.py debe documentar las 3 formas de ejecutar."""
    src = (ROOT / "src" / "app" / "main.py").read_text()
    # Captura el docstring (entre triple quotes al inicio del archivo)
    m = re.match(r'^\s*"""(.*?)"""', src, re.DOTALL)
    assert m is not None, "main.py no tiene docstring"
    doc = m.group(1)
    assert "cd src/app && python main.py" in doc
    assert "python -m app.main" in doc
    assert "python src/app/main.py" in doc


def test_main_tiene_sys_path_setup():
    """main.py debe tener un bloque que asegure `src/` en sys.path."""
    src = (ROOT / "src" / "app" / "main.py").read_text()
    # El bloque debe:
    # 1. Importar sys.
    # 2. Calcular _SRC a partir de __file__.
    # 3. Insertar _SRC en sys.path.
    assert "import sys" in src
    assert "sys.path" in src
    assert "Path(__file__)" in src
    assert "sys.path.insert" in src
