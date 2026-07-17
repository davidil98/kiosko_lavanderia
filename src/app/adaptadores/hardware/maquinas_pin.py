"""Control de pines de máquinas (lavadoras / secadoras).

Modo `pulso`: HIGH 0.5s (compatibilidad con la electrónica actual).
Modo `sostenido`: HIGH continuo, con tarea asyncio que apaga a los
`duracion_max_min` minutos como seguro.

Tareas sostenidas activas se guardan en memoria para poder reprogramar
el auto-apagado tras un reinicio (recuperación post-apagón).
"""

import asyncio
import time
from typing import Optional

from app.core.maquinas import EQUIPOS

from .gpio import set_high, set_low


_DURACION_MAX_POR_TIPO: dict[str, int] = {
    "lavado": 25,
    "secado": 40,
    "mixto": 25,
}


def _duracion_max_sostenido(tipo: str) -> int:
    return _DURACION_MAX_POR_TIPO.get(tipo, 25)


def _nombre(codigo: str) -> str:
    eq = EQUIPOS.get(codigo)
    return eq["nombre"] if eq else codigo


_sostenidas: dict[str, dict] = {}
_lock = asyncio.Lock() if hasattr(asyncio, "Lock") else None


async def _auto_apagar(codigo: str, pin: int, duracion_min: int) -> None:
    try:
        await asyncio.sleep(duracion_min * 60)
        set_low(pin)
        print(f"[maquinas_pin] Auto-apagado {codigo} tras {duracion_min} min")
    except asyncio.CancelledError:
        pass
    finally:
        _sostenidas.pop(codigo, None)


async def activar(codigo: str) -> None:
    """Pulso o sostenido según `EQUIPOS[codigo]['modo']`."""
    eq = EQUIPOS.get(codigo)
    if not eq:
        print(f"[maquinas_pin] Equipo '{codigo}' no encontrado")
        return
    if codigo in _sostenidas:
        print(f"[maquinas_pin] {eq['nombre']} ya está activo (sostenido)")
        return

    pin = eq["gpio"]
    modo = eq.get("modo", "pulso")
    set_high(pin)

    if modo == "pulso":
        await asyncio.sleep(0.5)
        set_low(pin)
        print(f"[maquinas_pin] Pulso enviado a {eq['nombre']}")
        return

    duracion = _duracion_max_sostenido(eq["tipo"])
    task = asyncio.create_task(_auto_apagar(codigo, pin, duracion))
    _sostenidas[codigo] = {
        "task": task,
        "inicio": time.time(),
        "duracion_min": duracion,
    }
    print(f"[maquinas_pin] {eq['nombre']} sostenido, auto-apagado en {duracion} min")


async def activar_con_duracion(codigo: str, duracion_min: int) -> None:
    """Como `activar()` pero el operador decide la duración (modo sostenido)."""
    eq = EQUIPOS.get(codigo)
    if not eq:
        return
    if codigo in _sostenidas:
        return

    pin = eq["gpio"]
    modo = eq.get("modo", "pulso")
    set_high(pin)

    if modo == "pulso":
        await asyncio.sleep(0.5)
        set_low(pin)
        return

    duracion = max(1, int(duracion_min))
    task = asyncio.create_task(_auto_apagar(codigo, pin, duracion))
    _sostenidas[codigo] = {
        "task": task,
        "inicio": time.time(),
        "duracion_min": duracion,
    }
    print(f"[maquinas_pin] {eq['nombre']} sostenido {duracion} min (manual)")


async def apagar(codigo: str) -> None:
    eq = EQUIPOS.get(codigo)
    if not eq:
        return
    set_low(eq["gpio"])
    info = _sostenidas.pop(codigo, None)
    if info:
        task = info.get("task")
        if task and not task.done():
            task.cancel()


def sostenida_activa(codigo: str) -> Optional[dict]:
    return _sostenidas.get(codigo)


def tiempo_restante_sostenida(codigo: str) -> int:
    info = _sostenidas.get(codigo)
    if not info:
        return 0
    transcurrido = time.time() - info["inicio"]
    total = info["duracion_min"] * 60
    return max(0, int(total - transcurrido))


async def reprogramar_auto_apagado(codigo: str, duracion_min: float) -> None:
    """Usado al recuperar estado tras un reinicio."""
    info = _sostenidas.pop(codigo, None)
    if info:
        task = info.get("task")
        if task and not task.done():
            task.cancel()
    eq = EQUIPOS.get(codigo)
    if not eq:
        return
    duracion = max(0, int(duracion_min) + 1)
    task = asyncio.create_task(_auto_apagar(codigo, eq["gpio"], duracion))
    _sostenidas[codigo] = {
        "task": task,
        "inicio": time.time(),
        "duracion_min": duracion,
    }
    print(f"[maquinas_pin] Auto-apagado reprogramado: {codigo} en {duracion} min")


def limpiar() -> None:
    """Cancela todas las tareas de auto-apagado pendientes."""
    for info in list(_sostenidas.values()):
        task = info.get("task")
        if task and not task.done():
            task.cancel()
    _sostenidas.clear()
