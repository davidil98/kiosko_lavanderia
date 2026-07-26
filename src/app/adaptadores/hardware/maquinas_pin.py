"""Control de pines de máquinas (lavadoras / secadoras).

Modo `pulso`: HIGH 0.5s (compatibilidad con la electrónica actual).
Modo `sostenido`: HIGH continuo, con tarea asyncio que apaga a los
`duracion_min` minutos como seguro.

A partir de v2, el tracking de "qué máquina está ocupada" vive en
`core/estado_maquinas` (única fuente de verdad). Este módulo solo
opera el GPIO y notifica al estado_maquinas antes/después.

API pública (no cambia):
  - activar(codigo)
  - activar_con_duracion(codigo, duracion_min)
  - apagar(codigo)
  - sostenida_activa(codigo) -> Optional[dict]
  - tiempo_restante_sostenida(codigo) -> int
  - pausar(codigo) -> bool
  - reanudar(codigo, duracion_min_adicional) -> bool
  - limpiar()
"""

import asyncio
import time
from typing import Optional

from app.core.estado_maquinas import (
    ESTADO,
    asignar as em_asignar,
    obtener as em_obtener,
    liberar as em_liberar,
    pausar as em_pausar,
    reanudar as em_reanudar,
    set_task as em_set_task,
)
from app.core.maquinas import EQUIPOS

from .gpio import set_high, set_low


_DURACION_MAX_POR_TIPO: dict[str, int] = {
    "lavado": 25,
    "secado": 40,
    "mixto": 25,
    "doblado": 25,
}


def _duracion_max_sostenido(tipo: str) -> int:
    return _DURACION_MAX_POR_TIPO.get(tipo, 25)


async def _auto_apagar(codigo: str, pin: int, duracion_min: float) -> None:
    try:
        await asyncio.sleep(duracion_min * 60)
        set_low(pin)
        em = em_obtener(codigo)
        if em and em.ocupada:
            from app.eventos.bus import bus
            from app.eventos.tipos import maquina_liberada

            orden_id = em.orden_id or 0
            em_liberar(codigo)
            bus.publish(maquina_liberada(orden_id, codigo, motivo="auto_apagado"))
        print(f"[maquinas_pin] Auto-apagado {codigo} tras {duracion_min} min")
    except asyncio.CancelledError:
        pass


async def activar(codigo: str) -> None:
    """Pulso o sostenido según `EQUIPOS[codigo]['modo']`.

    Marca la máquina como ocupada en `estado_maquinas`. Para pulso
    (que solo dura 0.5s), la marca sigue ocupada para impedir
    reasignación; el operador debe marcar la orden como completada
    o usar `apagar` para liberarla explícitamente.
    """
    eq = EQUIPOS.get(codigo)
    if not eq:
        print(f"[maquinas_pin] Equipo '{codigo}' no encontrado")
        return
    em = em_obtener(codigo)
    if em and em.ocupada and em.modo == "sostenido":
        print(f"[maquinas_pin] {eq['nombre']} ya está activo (sostenido)")
        return

    pin = eq["gpio"]
    modo = eq.get("modo", "pulso")
    set_high(pin)

    if modo == "pulso":
        await asyncio.sleep(0.5)
        set_low(pin)
        if em is not None and not em.ocupada:
            em_asignar(
                codigo=codigo,
                orden_id=0,
                nombre_cliente="(pulso directo)",
                servicio="pulso",
                duracion_min=0,
            )
        print(f"[maquinas_pin] Pulso enviado a {eq['nombre']}")
        return

    duracion = _duracion_max_sostenido(eq["tipo"])
    if em is not None and not em.ocupada:
        em_asignar(
            codigo=codigo,
            orden_id=0,
            nombre_cliente="(sin orden asignada)",
            servicio="sostenido",
            duracion_min=duracion,
        )
    task = asyncio.create_task(_auto_apagar(codigo, pin, duracion))
    em_set_task(codigo, task)
    print(f"[maquinas_pin] {eq['nombre']} sostenido, auto-apagado en {duracion} min")


async def activar_con_duracion(codigo: str, duracion_min: int) -> None:
    """Como `activar()` pero con duración explícita (modo sostenido o
    personalizado)."""
    eq = EQUIPOS.get(codigo)
    if not eq:
        return
    em = em_obtener(codigo)

    pin = eq["gpio"]
    modo = eq.get("modo", "pulso")
    set_high(pin)

    if modo == "pulso":
        await asyncio.sleep(0.5)
        set_low(pin)
        if em is not None and not em.ocupada:
            em_asignar(
                codigo=codigo,
                orden_id=0,
                nombre_cliente="(pulso directo)",
                servicio="pulso",
                duracion_min=0,
            )
        return

    duracion = max(1, int(duracion_min))
    if em is not None and not em.ocupada:
        em_asignar(
            codigo=codigo,
            orden_id=0,
            nombre_cliente="(sin orden asignada)",
            servicio="sostenido",
            duracion_min=duracion,
        )
    task = asyncio.create_task(_auto_apagar(codigo, pin, duracion))
    em_set_task(codigo, task)
    print(f"[maquinas_pin] {eq['nombre']} sostenido {duracion} min (manual)")


async def apagar(codigo: str) -> None:
    """Apaga el GPIO y libera la máquina en `estado_maquinas`.

    Publica `TIPO_MAQUINA_LIBERADA` en el bus.
    """
    eq = EQUIPOS.get(codigo)
    if not eq:
        return
    set_low(eq["gpio"])
    orden_id = em_liberar(codigo)
    if orden_id is not None:
        from app.eventos.bus import bus
        from app.eventos.tipos import maquina_liberada

        bus.publish(maquina_liberada(orden_id, codigo, motivo="manual"))


async def pausar(codigo: str) -> bool:
    """Pausa el auto-apagado de una máquina en modo sostenido.

    Publica `TIPO_MAQUINA_PAUSADA` si tuvo éxito.
    """
    eq = EQUIPOS.get(codigo)
    if not eq:
        return False
    if not em_pausar(codigo):
        return False
    from app.eventos.bus import bus
    from app.eventos.tipos import maquina_pausada

    em = em_obtener(codigo)
    orden_id = em.orden_id if em else 0
    bus.publish(maquina_pausada(orden_id or 0, codigo))
    print(f"[maquinas_pin] {eq['nombre']} pausada")
    return True


async def reanudar(codigo: str, duracion_min_adicional: int) -> bool:
    """Reanuda una máquina pausada con duración adicional."""
    eq = EQUIPOS.get(codigo)
    if not eq:
        return False
    if not em_reanudar(codigo, duracion_min_adicional):
        return False
    from app.core.estado_maquinas import obtener as _em_obtener

    em = _em_obtener(codigo)
    if em is None or not em.sostenida_hasta:
        return False
    restante = em.sostenida_hasta - time.time()
    if restante <= 0:
        return False
    pin = eq["gpio"]
    task = asyncio.create_task(_auto_apagar(codigo, pin, restante / 60.0))
    em_set_task(codigo, task)
    from app.eventos.bus import bus
    from app.eventos.tipos import maquina_reanudada

    bus.publish(maquina_reanudada(em.orden_id or 0, codigo))
    print(f"[maquinas_pin] {eq['nombre']} reanudada (+{duracion_min_adicional} min)")
    return True


def sostenida_activa(codigo: str) -> Optional[dict]:
    em = em_obtener(codigo)
    if not em or not em.ocupada or em.modo != "sostenido":
        return None
    return {
        "inicio": None,
        "duracion_min": em.duracion_min,
        "pausada": em.pausada,
    }


def tiempo_restante_sostenida(codigo: str) -> int:
    em = em_obtener(codigo)
    if not em or not em.ocupada or em.modo != "sostenido":
        return 0
    return int(em.tiempo_restante_min)


async def reprogramar_auto_apagado(codigo: str, duracion_min: float) -> None:
    """Usado al recuperar estado tras un reinicio."""
    eq = EQUIPOS.get(codigo)
    if not eq:
        return
    duracion = max(0, int(duracion_min) + 1)
    task = asyncio.create_task(_auto_apagar(codigo, eq["gpio"], duracion))
    em_set_task(codigo, task)
    print(f"[maquinas_pin] Auto-apagado reprogramado: {codigo} en {duracion} min")


def limpiar() -> None:
    """Cancela todas las tareas de auto-apagado pendientes y libera
    las máquinas en estado_maquinas."""
    for em in list(ESTADO.values()):
        if em._task is not None and not em._task.done():
            em._task.cancel()
        em.ocupada = False
        em.orden_id = None
        em.nombre_cliente = ""
        em.servicio = ""
        em.duracion_min = 0
        em.sostenida_hasta = None
        em.pausada = False
        em._task = None
