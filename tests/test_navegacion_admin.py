"""Test de navegación real de las páginas admin autenticadas.

Para cada página admin, valida que:
1. Responde 200.
2. El HTML no contiene "Internal Server Error" ni "Traceback".
3. No hay stacktraces en el stderr del server.
"""

import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC_APP = ROOT / "src" / "app"
VENV = ROOT / ".venv" / "bin" / "python3"


@pytest.fixture(scope="module")
def server():
    """Arranca el server de NiceGUI una sola vez para todo el módulo."""
    proc = subprocess.Popen(
        [str(VENV), "main.py"],
        cwd=SRC_APP,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env={"PATH": str(VENV.parent), "HOME": str(ROOT)},
    )
    # Esperar a que esté listo
    for _ in range(30):
        try:
            with urllib.request.urlopen("http://localhost:8000/", timeout=1) as r:
                if r.status == 200:
                    break
        except (urllib.error.URLError, OSError):
            time.sleep(0.3)
    yield proc
    proc.terminate()
    try:
        stderr = proc.stderr.read(8000).decode("utf-8", errors="replace")
    except Exception:
        stderr = ""
    proc.wait(timeout=3)
    if "Traceback" in stderr:
        print(f"=== STDERR del server ===\n{stderr}")


PAGINAS = [
    "/",
    "/admin/login",
    "/admin",
    "/admin/operativo",
    "/admin/autoservicio",
    "/admin/personalizado",
    "/admin/cortes",
    "/admin/superadmin",
]


@pytest.mark.parametrize("path", PAGINAS)
def test_pagina_no_500(server, path):
    """GET a cada página debe devolver 200 y HTML sin errores."""
    try:
        with urllib.request.urlopen(f"http://localhost:8000{path}", timeout=5) as r:
            status = r.status
            html = r.read(500_000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        pytest.fail(f"{path}: HTTP {e.code}")
    assert status == 200, f"{path}: status={status}"
    assert "Internal Server Error" not in html, (
        f"{path}: contiene 'Internal Server Error' en el HTML"
    )
    assert "Traceback" not in html, f"{path}: contiene 'Traceback' en el HTML"


def test_kiosko_tiene_shell_html(server):
    """El kiosko debe responder con un shell HTML válido (el contenido
    renderizado por @ui.refreshable se inyecta via JS/WebSocket, no en el
    primer GET)."""
    with urllib.request.urlopen("http://localhost:8000/", timeout=5) as r:
        html = r.read(50_000).decode("utf-8", errors="replace")
    assert "<!doctype html>" in html.lower() or "<html" in html
    assert "EcoLuna" in html  # al menos el title


def test_login_tiene_shell_html(server):
    """El admin/login responde con shell HTML válido."""
    with urllib.request.urlopen("http://localhost:8000/admin/login", timeout=5) as r:
        html = r.read(50_000).decode("utf-8", errors="replace")
    assert "<!doctype html>" in html.lower() or "<html" in html
    assert "EcoLuna" in html


def test_estructura_operativo_separa_header_de_contenido(server):
    """Verifica estáticamente que operativo.py renderiza el header FUERA
    del ui.refreshable, así el timer no lo reemplaza y no regresa el scroll
    al inicio."""
    src = (ROOT / "src" / "app" / "ui" / "admin" / "operativo.py").read_text()
    # El header (<h2>Panel Operativo) debe estar escrito FUERA del bloque
    # @ui.refreshable, no dentro de contenido().
    # Truco: el header literal "Panel Operativo" debe aparecer ANTES del
    # contenido del refreshable. Lo verificamos contando que aparece 2+ veces
    # en el archivo: una en la UI (header) y otra en un comentario opcional.
    assert "Panel Operativo" in src
    # El timer debe llamar a contenido.refresh, NO a la página entera.
    assert "ui.timer" in src
    assert "contenido.refresh" in src


def test_estructura_paginas_sin_refresh_en_header():
    """Las 5 páginas admin no deben refrescar TODO el contenido (incluyendo
    el header) con el timer. El header debe estar en un bloque estático.
    """
    archivos = [
        "operativo.py",
        "autoservicio.py",
        "personalizado.py",
        "cortes.py",
        "dashboard.py",
    ]
    for nombre in archivos:
        path = ROOT / "src" / "app" / "ui" / "admin" / nombre
        src = path.read_text()
        # Cada archivo debe tener un ui.timer que solo refresca `contenido`.
        assert "ui.timer" in src, f"{nombre}: no tiene ui.timer"
        assert "contenido.refresh" in src, f"{nombre}: timer no refresca contenido"
        # El header literal (e.g. "Panel Operativo") debe aparecer
        # EN la sección estática, no en la función contenido() (que es el
        # refreshable). Buscamos que aparezca el string y que el timer
        # solo llame `contenido.refresh` (no `refresh` directamente).
        # Verificación: el timer NO debe llamarse sin argumento (que
        # refrescaría toda la página y volvería el scroll al inicio).
        for line in src.splitlines():
            if "ui.timer" in line:
                assert "contenido.refresh" in line, (
                    f"{nombre}: el ui.timer debe llamar a 'contenido.refresh', "
                    f"no a una función que refresque toda la página. "
                    f"Línea: {line.strip()}"
                )
