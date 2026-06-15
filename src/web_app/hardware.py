import sys
import asyncio
import time
from typing import Callable

TEST_MODE = 'test' in sys.argv

# Attempt to import GPIO libraries if not in test mode
if TEST_MODE:
    HARDWARE_AVAILABLE = False
    print("TEST MODE: Hardware dependencies bypassed.")
else:
    try:
        from gpiozero import Button
        import RPi.GPIO as GPIO
        HARDWARE_AVAILABLE = True
    except ImportError:
        HARDWARE_AVAILABLE = False
        print("Warning: Hardware GPIO libraries not found. Running in simulation mode.")

# --- Monedero ---
PIN_MONEDERO = 21

class LectorMonedas:
    def __init__(self, callback: Callable[[int], None]):
        """Callback recibe el valor de la moneda agregada (1, 2, 5, 10)"""
        self.pulsos = 0
        self.ultimo_tiempo = 0
        self.diccionario_monedas = {2: 1, 4: 2, 6: 5, 8: 10}
        self.callback = callback
        
        if HARDWARE_AVAILABLE:
            try:
                self.monedero = Button(PIN_MONEDERO, bounce_time=0.02)
                self.monedero.when_pressed = self.registrar_pulso
            except Exception as e:
                print(f"Error inicializando monedero: {e}")
                self.monedero = None
        else:
            self.monedero = None
            
        # El loop asíncrono no se puede crear aquí, debe ser invocado cuando la app inicie
        self._running = True

    def start(self):
        asyncio.create_task(self.procesar_ventana_tiempo())

    def registrar_pulso(self):
        self.pulsos += 1
        self.ultimo_tiempo = time.time()
        print(f"Hardware: Pulso detectado. Total temporal: {self.pulsos}")
        
    def simular_moneda(self, valor):
        # Simula el ingreso de una moneda para pruebas sin hardware
        if valor in self.diccionario_monedas.values():
            self.callback(valor)

    async def procesar_ventana_tiempo(self):
        while self._running:
            if self.pulsos > 0 and (time.time() - self.ultimo_tiempo) > 0.3:
                if self.pulsos in self.diccionario_monedas:
                    valor = self.diccionario_monedas[self.pulsos]
                    print(f"Hardware: Moneda validada: ${valor}")
                    # Enviar el callback al event loop principal
                    self.callback(valor)
                else:
                    print(f"Hardware: Error de lectura (Pulsos: {self.pulsos})")
                self.pulsos = 0
            
            await asyncio.sleep(0.1)
            
    def detener(self):
        self._running = False
        if hasattr(self, 'monedero') and self.monedero:
            self.monedero.close()

# --- Lavadoras y Secadoras ---
# Modificar aquí para añadir, quitar o cambiar máquinas.
# tipo: 'mixto' = lava y seca | 'lavado' = solo lava | 'secado' = solo seca
EQUIPOS = {
    "lavasecadora_1": {"nombre": "Lavasecadora 1",  "tipo": "mixto",  "capacidad_kg": 5,  "gpio": 17},
    "lavasecadora_2": {"nombre": "Lavasecadora 2",  "tipo": "mixto",  "capacidad_kg": 5,  "gpio": 18},
    "lavasecadora_3": {"nombre": "Lavasecadora 3",  "tipo": "mixto",  "capacidad_kg": 5,  "gpio": 4},
    "secadora_1":     {"nombre": "Secadora 1",  "tipo": "secado", "capacidad_kg": 5, "gpio": 23},
}

def init_gpio_lavadoras():
    if HARDWARE_AVAILABLE:
        GPIO.setmode(GPIO.BCM)
        for equipo in EQUIPOS.values():
            try:
                GPIO.setup(equipo['gpio'], GPIO.OUT, initial=GPIO.LOW)
            except Exception as e:
                print(f"Error setup pin {equipo['gpio']} ({equipo['nombre']}): {e}")

def limpiar_pines():
    """Libera los pines de la Raspberry Pi al apagar el servidor."""
    if HARDWARE_AVAILABLE:
        try:
            GPIO.cleanup()
            print("🧹 Hardware: Pines GPIO liberados correctamente.")
        except Exception as e:
            print(f"Error al limpiar pines: {e}")

async def activar_lavadora(equipo_id: str):
    """Manda un pulso de 0.5s al equipo dado su ID en el diccionario EQUIPOS."""
    equipo = EQUIPOS.get(equipo_id)
    if not equipo:
        print(f"Hardware: Equipo '{equipo_id}' no encontrado en EQUIPOS.")
        return
    pin = equipo['gpio']
    print(f"Hardware: Iniciando pulso en {equipo['nombre']} (PIN {pin}) por 0.5s...")
    if HARDWARE_AVAILABLE:
        try:
            GPIO.output(pin, GPIO.HIGH)
        except Exception as e:
            print(f"Error activando PIN {pin}: {e}")
            
    await asyncio.sleep(0.5)
    
    if HARDWARE_AVAILABLE:
        try:
            GPIO.output(pin, GPIO.LOW)
        except Exception as e:
            print(f"Error desactivando PIN {pin}: {e}")
    print(f"Hardware: Fin de pulso en {equipo['nombre']} (PIN {pin}).")
