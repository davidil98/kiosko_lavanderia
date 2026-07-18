"""Test E2E con Playwright: navega todas las páginas admin, verifica
que no haya errores de JS, y valida el comportamiento del scroll.
"""

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_APP = ROOT / "src" / "app"
VENV_PYTHON = ROOT / ".venv" / "bin" / "python3"


def _start_server():
    proc = subprocess.Popen(
        [str(VENV_PYTHON), "main.py"],
        cwd=SRC_APP,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env={"PATH": str(VENV_PYTHON.parent), "HOME": str(ROOT)},
    )
    # Esperar a que esté listo
    import urllib.request
    import urllib.error

    for _ in range(30):
        try:
            with urllib.request.urlopen("http://localhost:8000/", timeout=1) as r:
                if r.status == 200:
                    return proc
        except (urllib.error.URLError, OSError):
            time.sleep(0.3)
    return proc


def test_e2e_navegacion_admin_completa():
    """Navega cada página admin, captura errores de JS, verifica contenido,
    y comprueba que el auto-refresh NO regresa al scroll al inicio.
    """
    from playwright.sync_api import sync_playwright

    proc = _start_server()
    errores = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()

            # Capturar errores de consola
            page_errors = []
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))
            page.on(
                "console",
                lambda msg: (
                    page_errors.append(f"console.{msg.type}: {msg.text}")
                    if msg.type == "error"
                    else None
                ),
            )

            # 1. Kiosko
            page.goto("http://localhost:8000/", wait_until="networkidle", timeout=15000)
            assert "EcoLuna" in page.content(), "kiosko: falta 'EcoLuna'"

            # 2. Login
            page.goto(
                "http://localhost:8000/admin/login",
                wait_until="networkidle",
                timeout=15000,
            )
            assert "Panel EcoLuna" in page.content(), "login: falta 'Panel EcoLuna'"
            page.locator("input").nth(0).fill("Moi")
            page.locator("input").nth(1).fill("admin123")
            page.locator("button:has-text('Ingresar')").click()
            page.wait_for_url("**/admin", timeout=10000)

            # 3. Dashboard
            assert "/admin" in page.url, f"no redirigió a /admin: {page.url}"
            content = page.content()
            assert "Bienvenido" in content, "dashboard: falta 'Bienvenido'"

            # 4-7. Cada página admin
            for path, expected in [
                ("/admin/operativo", "Panel Operativo"),
                ("/admin/autoservicio", "Autoservicio"),
                ("/admin/personalizado", "Servicio Personalizado"),
                ("/admin/cortes", "Cortes de Caja"),
            ]:
                page.goto(
                    f"http://localhost:8000{path}",
                    wait_until="networkidle",
                    timeout=15000,
                )
                assert expected in page.content(), f"{path}: falta '{expected}'"

            # 8. Superadmin (la que tenía el bug del NoneType)
            page.goto(
                "http://localhost:8000/admin/superadmin",
                wait_until="networkidle",
                timeout=15000,
            )
            content = page.content()
            assert "Servicios" in content, "superadmin: falta 'Servicios'"

            for tab_text in [
                "Segmentaciones",
                "Máquinas",
                "Calculadora",
                "Métricas",
                "Respaldo",
            ]:
                try:
                    page.locator(f"div[role='tab']:has-text('{tab_text}')").click(
                        timeout=5000
                    )
                    page.wait_for_timeout(500)
                except Exception as e:
                    errores.append(f"superadmin tab '{tab_text}': {e}")

            # ── Verificación del bug del scroll ──
            # Navegar a /admin/operativo, hacer scroll, esperar 4s (1 tick del
            # auto-refresh), y verificar que la posición de scroll NO regresó
            # al inicio. Como no hay órdenes pendientes, el hash no cambia
            # y el DOM NO se debe reemplazar.
            page.goto(
                "http://localhost:8000/admin/operativo",
                wait_until="networkidle",
                timeout=15000,
            )
            # Esperar a que el JS termine de inyectar el contenido
            page.wait_for_timeout(1000)
            # Verificar que hay suficiente contenido para hacer scroll
            scroll_max = page.evaluate(
                "document.body.scrollHeight - window.innerHeight"
            )
            print(
                f"  operativo: scrollHeight={page.evaluate('document.body.scrollHeight')}, viewport={page.evaluate('window.innerHeight')}, scroll_max={scroll_max}"
            )
            if scroll_max > 50:  # Solo si hay contenido scrollable
                # Hacer scroll al 50% del documento
                target_scroll = scroll_max // 2
                page.evaluate(f"window.scrollTo(0, {target_scroll})")
                page.wait_for_timeout(300)  # Que se asiente el scroll
                scroll_inicial = page.evaluate("window.scrollY")
                print(
                    f"  operativo: scroll inicial = {scroll_inicial} (target {target_scroll})"
                )
                # Esperar 4s (más de un tick del auto-refresh de 3s)
                page.wait_for_timeout(4000)
                scroll_post = page.evaluate("window.scrollY")
                print(f"  operativo: scroll post = {scroll_post}")
                assert scroll_post == scroll_inicial, (
                    f"BUG DEL SCROLL: scroll cambió de {scroll_inicial} a {scroll_post} "
                    f"después del auto-refresh"
                )
            else:
                print(
                    "  operativo: no hay contenido scrollable, saltando test de scroll"
                )
            # Hacer scroll hasta el fondo
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            scroll_inicial = page.evaluate("window.scrollY")
            assert scroll_inicial > 0, (
                f"no se pudo scrollear (scrollY={scroll_inicial})"
            )
            # Esperar 4s (más de un tick del auto-refresh de 3s)
            page.wait_for_timeout(4000)
            scroll_post = page.evaluate("window.scrollY")
            assert scroll_post == scroll_inicial, (
                f"BUG DEL SCROLL: scroll cambió de {scroll_inicial} a {scroll_post} "
                f"después del auto-refresh"
            )

            browser.close()

        if page_errors:
            errores.extend(page_errors)

        if errores:
            pytest.fail(f"Errores:\n  " + "\n  ".join(errores))
    finally:
        proc.terminate()
        try:
            stderr = proc.stderr.read(8000).decode("utf-8", errors="replace")
        except Exception:
            stderr = ""
        proc.wait(timeout=3)
        if "TypeError" in stderr or "Traceback" in stderr:
            print(f"=== STDERR del server ===\n{stderr[:3000]}")


import pytest
