"""Lector de monedas con debounce por software.

Aceptador físico en pin 21 (BCM). El hardware envía N pulsos por moneda
(2=$1, 4=$2, 6=$5, 8=$10) y un debounce de 300ms agrupa los pulsos en una
moneda validada. En modo test, ignora GPIO y permite inyectar monedas vía
`simular_moneda(valor)` (que la UI conecta a las teclas 1/2/5/0).
"""

import asyncio
import time
from typing import Callable, Optional

from .gpio import HARDWARE_AVAILABLE, modo_test

PIN_MONEDERO = 21
DEBOUNCE_S = 0.3
POLL_S = 0.1

PULSOS_A_MONEDA: dict[int, int] = {2: 1, 4: 2, 6: 5, 8: 10}


class LectorMonedas:
    def __init__(self, callback: Callable[[int], None]):
        self._callback = callback
        self._pulsos = 0
        self._ultimo_tiempo = 0.0
        self._running = True
        self._boton = None

        if not modo_test():
            try:
                from gpiozero import Button

                self._boton = Button(PIN_MONEDERO, bounce_time=0.02)
                self._boton.when_pressed = self._registrar_pulso
            except Exception as e:
                print(f"[monedero] No se pudo inicializar el pin {PIN_MONEDERO}: {e}")
                self._boton = None

    def start(self) -> None:
        """Lanza la tarea asyncio de agrupación de pulsos. Llamar desde on_startup."""
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self._procesar_ventana())
        except RuntimeError:
            # Si no hay loop todavía (p.ej. tests), se ignora
            pass

    def stop(self) -> None:
        self._running = False
        if self._boton is not None:
            try:
                self._boton.close()
            except Exception:
                pass

    def _registrar_pulso(self) -> None:
        self._pulsos += 1
        self._ultimo_tiempo = time.time()

    def simular_moneda(self, valor: int) -> None:
        """Inyecta una moneda simulada (test mode)."""
        if valor in PULSOS_A_MONEDA.values():
            self._callback(valor)

    async def _procesar_ventana(self) -> None:
        while self._running:
            if self._pulsos > 0 and (time.time() - self._ultimo_tiempo) > DEBOUNCE_S:
                n = self._pulsos
                self._pulsos = 0
                if n in PULSOS_A_MONEDA:
                    self._callback(PULSOS_A_MONEDA[n])
                else:
                    print(f"[monedero] Lectura inválida ({n} pulsos)")
            await asyncio.sleep(POLL_S)
