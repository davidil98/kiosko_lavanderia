import sys
import asyncio
import time
from typing import Callable

TEST_MODE = "test" in sys.argv

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
        if hasattr(self, "monedero") and self.monedero:
            self.monedero.close()


# --- Lavadoras y Secadoras ---
# Modificar aquí para añadir, quitar o cambiar máquinas.
# tipo: 'mixto' = lava y seca | 'lavado' = solo lava | 'secado' = solo seca
# modo: 'pulso' = HIGH 0.5s (optoacoplador) | 'sostenido' = HIGH continuo hasta apagado
EQUIPOS = {
    "lavasecadora_1": {
        "nombre": "Lavasecadora 1",
        "tipo": "mixto",
        "capacidad_kg": 5,
        "gpio": 17,
        "modo": "pulso",
    },
    "lavasecadora_2": {
        "nombre": "Lavasecadora 2",
        "tipo": "mixto",
        "capacidad_kg": 5,
        "gpio": 18,
        "modo": "pulso",
    },
    "lavasecadora_3": {
        "nombre": "Lavasecadora 3",
        "tipo": "mixto",
        "capacidad_kg": 5,
        "gpio": 4,
        "modo": "sostenido",
    },
    "secadora_1": {
        "nombre": "Secadora 1",
        "tipo": "secado",
        "capacidad_kg": 5,
        "gpio": 23,
        "modo": "sostenido",
    },
}

# Tiempos máximos de seguridad para equipos en modo sostenido (minutos)
DURACION_MAXIMA_SOSTENIDO_MIN = {
    "lavado": 25,
    "secado": 40,
    "mixto": 25,
}

# Estado en memoria de equipos sostenidos activos
# {equipo_id: {"task": asyncio.Task, "inicio": float(timestamp), "duracion_min": int}}
_equipos_sostenidos: dict = {}


def _duracion_maxima_sostenido(tipo: str) -> int:
    """Devuelve el tiempo máximo de seguridad para un equipo sostenido según su tipo."""
    return DURACION_MAXIMA_SOSTENIDO_MIN.get(tipo, 25)


def _bajar_pin(pin: int, nombre: str):
    """Baja un pin de forma segura, loggeando errores."""
    if not HARDWARE_AVAILABLE:
        return
    try:
        GPIO.output(pin, GPIO.LOW)
        print(f"Hardware: Pin de {nombre} (PIN {pin}) bajado.")
    except Exception as e:
        print(f"Error bajando PIN {pin} ({nombre}): {e}")


async def _auto_apagar_maquina(equipo_id: str, pin: int, duracion_min: int):
    """Tarea en background: espera N minutos y baja el pin."""
    try:
        await asyncio.sleep(duracion_min * 60)
        equipo = EQUIPOS.get(equipo_id)
        if equipo:
            print(
                f"Hardware: Auto-apagando {equipo['nombre']} por timeout ({duracion_min}min)"
            )
            _bajar_pin(pin, equipo["nombre"])
    except asyncio.CancelledError:
        pass
    finally:
        _equipos_sostenidos.pop(equipo_id, None)


def init_gpio_lavadoras():
    if HARDWARE_AVAILABLE:
        GPIO.setmode(GPIO.BCM)
        for equipo in EQUIPOS.values():
            try:
                # Inicializar siempre en LOW por seguridad (recuperación tras apagón)
                GPIO.setup(equipo["gpio"], GPIO.OUT, initial=GPIO.LOW)
            except Exception as e:
                print(f"Error setup pin {equipo['gpio']} ({equipo['nombre']}): {e}")


def limpiar_pines():
    """Libera los pines de la Raspberry Pi al apagar el servidor."""
    # Cancelar tareas de auto-apagado pendientes
    for info in list(_equipos_sostenidos.values()):
        task = info.get("task")
        if task and not task.done():
            task.cancel()
    _equipos_sostenidos.clear()

    if HARDWARE_AVAILABLE:
        try:
            GPIO.cleanup()
            print("🧹 Hardware: Pines GPIO liberados correctamente.")
        except Exception as e:
            print(f"Error al limpiar pines: {e}")


async def activar_lavadora(equipo_id: str):
    """Activa una máquina según su modo:
    - 'pulso': HIGH 0.5s (compatibilidad actual)
    - 'sostenido': HIGH continuo, se apaga manualmente o por timeout de seguridad
    """
    equipo = EQUIPOS.get(equipo_id)
    if not equipo:
        print(f"Hardware: Equipo '{equipo_id}' no encontrado en EQUIPOS.")
        return

    pin = equipo["gpio"]
    modo = equipo.get("modo", "pulso")

    # Si ya está activa en modo sostenido, no reactivar
    if equipo_id in _equipos_sostenidos:
        print(f"Hardware: {equipo['nombre']} ya está activa (sostenido). Ignorando.")
        return

    print(f"Hardware: Activando {equipo['nombre']} (PIN {pin}) modo={modo}...")
    if HARDWARE_AVAILABLE:
        try:
            GPIO.output(pin, GPIO.HIGH)
        except Exception as e:
            print(f"Error activando PIN {pin}: {e}")
            return

    if modo == "pulso":
        await asyncio.sleep(0.5)
        _bajar_pin(pin, equipo["nombre"])
        print(f"Hardware: Pulso enviado a {equipo['nombre']}.")
    else:
        # Modo sostenido: programar auto-apagado
        duracion_min = _duracion_maxima_sostenido(equipo["tipo"])
        task = asyncio.create_task(_auto_apagar_maquina(equipo_id, pin, duracion_min))
        _equipos_sostenidos[equipo_id] = {
            "task": task,
            "inicio": time.time(),
            "duracion_min": duracion_min,
        }
        print(
            f"Hardware: {equipo['nombre']} activada en modo sostenido. "
            f"Auto-apagado en {duracion_min} minutos."
        )


async def activar_lavadora_con_duracion(equipo_id: str, duracion_min: int):
    """Como activar_lavadora() pero permite especificar la duración en minutos
    para equipos en modo sostenido. Útil para el panel personalizado donde el
    operador decide el tiempo de uso."""
    equipo = EQUIPOS.get(equipo_id)
    if not equipo:
        print(f"Hardware: Equipo '{equipo_id}' no encontrado en EQUIPOS.")
        return

    pin = equipo["gpio"]
    modo = equipo.get("modo", "pulso")

    if equipo_id in _equipos_sostenidos:
        print(f"Hardware: {equipo['nombre']} ya está activa (sostenido). Ignorando.")
        return

    if HARDWARE_AVAILABLE:
        try:
            GPIO.output(pin, GPIO.HIGH)
        except Exception as e:
            print(f"Error activando PIN {pin}: {e}")
            return

    if modo == "pulso":
        await asyncio.sleep(0.5)
        _bajar_pin(pin, equipo["nombre"])
        print(f"Hardware: Pulso enviado a {equipo['nombre']}.")
    else:
        duracion_min = max(1, int(duracion_min))
        task = asyncio.create_task(_auto_apagar_maquina(equipo_id, pin, duracion_min))
        _equipos_sostenidos[equipo_id] = {
            "task": task,
            "inicio": time.time(),
            "duracion_min": duracion_min,
        }
        print(
            f"Hardware: {equipo['nombre']} activada en modo sostenido. "
            f"Auto-apagado en {duracion_min} minutos."
        )


async def apagar_maquina(equipo_id: str):
    """Baja el pin de una máquina (útil para modo sostenido o emergencias)."""
    equipo = EQUIPOS.get(equipo_id)
    if not equipo:
        print(f"Hardware: Equipo '{equipo_id}' no encontrado en EQUIPOS.")
        return

    pin = equipo["gpio"]
    _bajar_pin(pin, equipo["nombre"])

    info = _equipos_sostenidos.pop(equipo_id, None)
    if info:
        task = info.get("task")
        if task and not task.done():
            task.cancel()
        print(
            f"Hardware: {equipo['nombre']} apagada y tarea de auto-apagado cancelada."
        )


async def reprogramar_auto_apagado(equipo_id: str, pin: int, duracion_min: float):
    """Usado al reiniciar la app para reprogramar el auto-apagado de una máquina
    sostenida que sigue en curso según la BD."""
    # Cancelar tarea previa si existe
    info = _equipos_sostenidos.pop(equipo_id, None)
    if info:
        task = info.get("task")
        if task and not task.done():
            task.cancel()

    duracion_min = max(0, duracion_min)
    task = asyncio.create_task(
        _auto_apagar_maquina(equipo_id, pin, int(duracion_min) + 1)
    )
    _equipos_sostenidos[equipo_id] = {
        "task": task,
        "inicio": time.time(),
        "duracion_min": int(duracion_min) + 1,
    }
    print(
        f"Hardware: Auto-apagado reprogramado para {equipo_id} en {duracion_min:.1f}min"
    )


def equipo_sostenido_activo(equipo_id: str) -> dict | None:
    """Retorna información del equipo sostenido activo o None."""
    return _equipos_sostenidos.get(equipo_id)


def tiempo_restante_sostenido(equipo_id: str) -> int:
    """Retorna segundos restantes de auto-apagado para un equipo sostenido activo."""
    info = _equipos_sostenidos.get(equipo_id)
    if not info:
        return 0
    transcurrido = time.time() - info["inicio"]
    total = info["duracion_min"] * 60
    return max(0, int(total - transcurrido))


def equipo_esta_ocupado(equipo_id: str) -> bool:
    """Verifica si una máquina está ocupada, sin importar la modalidad
    (autoservicio o personalizado). Consulta estado en memoria (sostenido)
    y también la base de datos (pulso en 'En proceso')."""
    if equipo_sostenido_activo(equipo_id):
        return True
    eq = EQUIPOS.get(equipo_id)
    if not eq:
        return False
    nombre = eq["nombre"]
    try:
        import database_web

        conn = database_web._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM transacciones "
            "WHERE estado = 'En proceso' AND id_equipo = ?",
            (nombre,),
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False
