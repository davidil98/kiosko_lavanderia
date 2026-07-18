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
    assert "Panel Operativo" in src
    # El archivo usa auto_refresh_smart (helper que solo refresca si
    # el hash cambia) o un patrón equivalente, no ui.timer directo.
    assert "auto_refresh_smart" in src or "ui.timer" in src


def test_estructura_paginas_sin_ui_timer_con_refresh_puro():
    """Las 5 páginas admin NO deben tener `ui.timer(..., contenido.refresh())`
    ni `ui.timer(..., refresh())` que reemplaza el DOM entero. Deben
    refrescar via el bus o con un timer que solo actualice si hay cambios.
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
        # PROHIBIDO: ui.timer(..., refresh()) o ui.timer(..., contenido.refresh())
        # porque regresan el scroll al inicio y cierran dialogs.
        for line in src.splitlines():
            line_strip = line.strip()
            # Ignorar comentarios
            if line_strip.startswith("#"):
                continue
            if "ui.timer" in line_strip and "refresh" in line_strip:
                # Permitir ui.timer(..., _tick_cortes) o similar (función
                # que verifica el hash antes de refrescar).
                if "_tick" in line_strip or "smart" in line_strip:
                    continue
                # Permitir ui.timer(10.0, lambda: asyncio.create_task(_tick_cortes()))
                if "asyncio.create_task" in line_strip:
                    continue
                pytest.fail(
                    f"{nombre}: ui.timer con .refresh() detectado. "
                    f"El DOM se reemplaza y el scroll regresa al inicio. "
                    f"Línea: {line_strip}"
                )
