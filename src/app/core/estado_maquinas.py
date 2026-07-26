"""Estado global de máquinas (única fuente de verdad sobre qué máquina está
ocupada y por cuánto tiempo).

`ESTADO` es un dict `{codigo: EstadoMaquina}`. La capa de hardware
(`adaptadores.hardware.maquinas_pin`) consulta este módulo para evitar
asignaciones duplicadas y para saber si debe reprogramar el auto-apagado.

Convención:
- Una máquina "libre" tiene `ocupada=False` y `orden_id=None`.
- Una máquina "en uso" tiene `ocupada=True` y `orden_id=<int>`.
- Una máquina "pausada" tiene `ocupada=True, pausada=True` y la task
  de auto-apagado cancelada.
- `sostenida_hasta` es timestamp epoch (segundos) o None si la máquina
  está libre, en pulso, o en modo sostenido aún no programado.

Este módulo es `core/`, por lo que NO importa de `adaptadores/` ni
`ui/`. La capa de hardware le notifica cuando arranca/apaga; la UI
pregunta antes de asignar.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EstadoMaquina:
    """Snapshot in-memory del estado de una máquina."""

    codigo: str
    nombre: str
    tipo: str  # "lavado" | "secado" | "mixto" | "doblado"
    modo: str  # "pulso" | "sostenido"
    ocupada: bool = False
    orden_id: Optional[int] = None
    nombre_cliente: str = ""
    servicio: str = ""
    duracion_min: int = 0
    sostenida_hasta: Optional[float] = None
    inicio_servicio: Optional[float] = None
    pausada: bool = False
    _task: Optional[asyncio.Task] = field(default=None, repr=False)

    @property
    def tiempo_restante_min(self) -> float:
        if self.sostenida_hasta is None:
            return 0.0
        return max(0.0, (self.sostenida_hasta - time.time()) / 60.0)

    @property
    def tiempo_encendida_min(self) -> int:
        """Minutos enteros desde que se asignó la máquina (0 si libre)."""
        if self.inicio_servicio is None:
            return 0
        return max(0, int((time.time() - self.inicio_servicio) / 60))


ESTADO: dict[str, EstadoMaquina] = {}


def registrar_maquina(codigo: str, nombre: str, tipo: str, modo: str) -> None:
    """Crea/actualiza la entrada de una máquina en el catálogo (libre).

    Llamar una vez por cada máquina del catálogo al iniciar.
    """
    if codigo in ESTADO:
        existente = ESTADO[codigo]
        existente.nombre = nombre
        existente.tipo = tipo
        existente.modo = modo
        return
    ESTADO[codigo] = EstadoMaquina(codigo=codigo, nombre=nombre, tipo=tipo, modo=modo)


def cargar_desde_bd(maquinas: list, ordenes_en_curso: list) -> None:
    """Reconstruye ESTADO desde la BD tras un reinicio.

    Args:
        maquinas: lista de `Maquina` (dataclass) del repo.
        ordenes_en_curso: lista de dicts de transacciones con
            estado='En-curso' y id_equipo no vacío.
    """
    ESTADO.clear()
    for m in maquinas:
        registrar_maquina(m.codigo, m.nombre, m.tipo, m.modo)

    for o in ordenes_en_curso:
        eq_nombre = o.get("id_equipo", "")
        if not eq_nombre:
            continue
        eq = next((m for m in maquinas if m.nombre == eq_nombre), None)
        if eq is None:
            continue
        duracion = o.get("duracion_estimada_min") or 0
        inicio = o.get("inicio_servicio")
        sostenida_hasta: Optional[float] = None
        inicio_epoch: Optional[float] = None
        if inicio:
            try:
                from datetime import datetime as _dt

                t0 = _dt.strptime(inicio, "%Y-%m-%d %H:%M:%S").timestamp()
                inicio_epoch = t0
                if eq.modo == "sostenido" and duracion:
                    sostenida_hasta = t0 + duracion * 60
            except (ValueError, TypeError):
                inicio_epoch = None
                sostenida_hasta = None

        estado = ESTADO[eq.codigo]
        estado.ocupada = True
        estado.orden_id = o["id_transaccion"]
        estado.nombre_cliente = o.get("nombre_cliente", "")
        estado.servicio = o.get("tipo_servicio", "")
        estado.duracion_min = duracion
        estado.sostenida_hasta = sostenida_hasta
        estado.inicio_servicio = inicio_epoch
        estado.pausada = False


def esta_disponible(codigo: str) -> bool:
    estado = ESTADO.get(codigo)
    if estado is None:
        return False
    return not estado.ocupada


def obtener(codigo: str) -> Optional[EstadoMaquina]:
    return ESTADO.get(codigo)


def listar_todas() -> list[EstadoMaquina]:
    return list(ESTADO.values())


def listar_disponibles() -> list[EstadoMaquina]:
    return [e for e in ESTADO.values() if not e.ocupada]


def listar_ocupadas() -> list[EstadoMaquina]:
    return [e for e in ESTADO.values() if e.ocupada]


def asignar(
    codigo: str,
    orden_id: int,
    nombre_cliente: str,
    servicio: str,
    duracion_min: int,
) -> None:
    """Marca la máquina como ocupada. NO toca el GPIO.

    Si ya estaba ocupada por la misma orden, actualiza los datos.
    Si estaba ocupada por otra orden, lanza `RuntimeError` (la UI debe
    haber validado antes con `esta_disponible`).
    """
    estado = ESTADO.get(codigo)
    if estado is None:
        raise KeyError(f"Maquina '{codigo}' no registrada en estado_maquinas")
    if estado.ocupada and estado.orden_id != orden_id:
        raise RuntimeError(
            f"Maquina '{codigo}' ya ocupada por orden #{estado.orden_id}"
        )
    estado.ocupada = True
    estado.orden_id = orden_id
    estado.nombre_cliente = nombre_cliente
    estado.servicio = servicio
    estado.duracion_min = duracion_min
    estado.pausada = False
    estado.inicio_servicio = time.time()
    if estado.modo == "sostenido" and duracion_min > 0:
        estado.sostenida_hasta = time.time() + duracion_min * 60
    else:
        estado.sostenida_hasta = None


def liberar(codigo: str) -> Optional[int]:
    """Libera la máquina y devuelve el `orden_id` que la ocupaba, o None.

    Cancela también la task asyncio de auto-apagado si existe.
    NO publica en el bus ni toca el GPIO. La capa de hardware debe:
      1. Apagar el GPIO.
      2. Llamar este método.
      3. Publicar TIPO_MAQUINA_LIBERADA en el bus.
    """
    estado = ESTADO.get(codigo)
    if estado is None:
        return None
    orden_id = estado.orden_id
    if estado._task is not None and not estado._task.done():
        estado._task.cancel()
    estado.ocupada = False
    estado.orden_id = None
    estado.nombre_cliente = ""
    estado.servicio = ""
    estado.duracion_min = 0
    estado.sostenida_hasta = None
    estado.inicio_servicio = None
    estado.pausada = False
    estado._task = None
    return orden_id


def pausar(codigo: str) -> bool:
    """Pausa el auto-apagado de una máquina en modo sostenido.

    Devuelve True si se pausó, False si no aplica (no es sostenida o
    ya estaba pausada). Cancela la task asyncio de auto-apagado.
    """
    estado = ESTADO.get(codigo)
    if estado is None or not estado.ocupada or estado.modo != "sostenido":
        return False
    if estado.pausada:
        return False
    if estado._task is not None and not estado._task.done():
        estado._task.cancel()
    estado._task = None
    estado.pausada = True
    return True


def reanudar(codigo: str, duracion_min_adicional: int) -> bool:
    """Reanuda una máquina pausada con una duración adicional en minutos.

    Devuelve True si se reanudó, False si no estaba pausada o no es
    sostenida. Crea una nueva task asyncio de auto-apagado.
    """
    estado = ESTADO.get(codigo)
    if estado is None or not estado.ocupada or estado.modo != "sostenido":
        return False
    if not estado.pausada:
        return False
    estado.pausada = False
    estado.duracion_min = estado.duracion_min + duracion_min_adicional
    if estado.duracion_min > 0:
        estado.sostenida_hasta = time.time() + estado.duracion_min * 60
    return True


def set_task(codigo: str, task: Optional[asyncio.Task]) -> None:
    """La capa de hardware registra la task asyncio de auto-apagado.

    Usado por `maquinas_pin.activar_con_duracion` después de crear la
    task. No debería llamarse desde otros lugares.
    """
    estado = ESTADO.get(codigo)
    if estado is None:
        return
    if estado._task is not None and not estado._task.done():
        estado._task.cancel()
    estado._task = task


def reprogramar_auto_apagados(
    on_auto_apagar, duracion_por_tipo: Optional[dict] = None
) -> None:
    """Tras un reinicio, recrea las tasks asyncio de auto-apagado.

    Args:
        on_auto_apagar: callable async que recibe (codigo, pin,
            duracion_min) y se encarga de apagar el GPIO al cumplirse.
        duracion_por_tipo: dict opcional con duraciones por defecto
            (si la orden no tiene `duracion_estimada_min`).
    """
    for estado in ESTADO.values():
        if not estado.ocupada or estado.modo != "sostenido":
            continue
        if estado.sostenida_hasta is None:
            continue
        restante = estado.sostenida_hasta - time.time()
        if restante <= 0:
            continue
        dur_min = restante / 60.0
        from app.core.maquinas import EQUIPOS

        eq = EQUIPOS.get(estado.codigo)
        if not eq:
            continue
        pin = eq["gpio"]
        task = asyncio.create_task(on_auto_apagar(estado.codigo, pin, dur_min))
        estado._task = task
