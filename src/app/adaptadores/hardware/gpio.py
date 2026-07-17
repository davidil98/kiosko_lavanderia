"""Inicialización y limpieza de pines GPIO de la Raspberry Pi.

Carga `gpiozero` y `RPi.GPIO` solo si están disponibles. En su defecto (modo
test en Mac/PC, o Pi sin librerías) opera en modo simulación: las funciones
existen pero no tocan hardware. Los otros adaptadores de hardware (`monedero.py`,
`maquinas_pin.py`) no importan gpiozero directamente: pasan por aquí.
"""

import os
import sys

TEST_MODE = "test" in sys.argv

HARDWARE_AVAILABLE = False
GPIO = None

if not TEST_MODE:
    try:
        from gpiozero import Button  # noqa: F401  (importado por monedero)
        import RPi.GPIO as _GPIO

        GPIO = _GPIO
        HARDWARE_AVAILABLE = True
    except (ImportError, RuntimeError):
        HARDWARE_AVAILABLE = False
        print("[gpio] gpiozero/RPi.GPIO no disponibles. Modo simulación.")


def modo_test() -> bool:
    return TEST_MODE or not HARDWARE_AVAILABLE


def init_gpio_lavadoras() -> None:
    """Configura todos los pines de máquinas en LOW (estado seguro)."""
    if not HARDWARE_AVAILABLE:
        return
    try:
        GPIO.setmode(GPIO.BCM)
        from app.core.maquinas import EQUIPOS

        for equipo in EQUIPOS.values():
            try:
                GPIO.setup(equipo["gpio"], GPIO.OUT, initial=GPIO.LOW)
            except Exception as e:
                print(
                    f"[gpio] Error setup pin {equipo['gpio']} ({equipo['nombre']}): {e}"
                )
    except Exception as e:
        print(f"[gpio] Error en init_gpio_lavadoras: {e}")


def limpiar_pines() -> None:
    """Libera los pines al apagar la app."""
    if not HARDWARE_AVAILABLE:
        return
    try:
        GPIO.cleanup()
        print("[gpio] Pines liberados.")
    except Exception as e:
        print(f"[gpio] Error al limpiar: {e}")


def set_high(pin: int) -> None:
    """Sube un pin a HIGH. Silencioso en modo test."""
    if not HARDWARE_AVAILABLE:
        return
    try:
        GPIO.output(pin, GPIO.HIGH)
    except Exception as e:
        print(f"[gpio] Error HIGH pin {pin}: {e}")


def set_low(pin: int) -> None:
    """Baja un pin a LOW. Silencioso en modo test."""
    if not HARDWARE_AVAILABLE:
        return
    try:
        GPIO.output(pin, GPIO.LOW)
    except Exception as e:
        print(f"[gpio] Error LOW pin {pin}: {e}")
