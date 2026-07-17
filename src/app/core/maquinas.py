"""Vista de dominio del catálogo de máquinas.

`EQUIPOS` es un dict con shape {codigo: {...}}. La fuente de verdad es la
tabla `maquinas`. `core` no importa `repo`: la carga se delega a un callable
inyectado por `bootstrap.py` (ver `set_cargador`). `recargar_equipos()` fuerza
recarga tras un CRUD del superadmin.
"""

from typing import Callable, TypedDict


class Equipo(TypedDict):
    codigo: str
    nombre: str
    tipo: str
    capacidad_kg: int
    gpio: int
    modo: str
    duracion_max_min: int


Cargador = Callable[[], dict[str, "Equipo"]]

_cargador: Cargador = lambda: {}
_CACHE: dict[str, Equipo] = {}


def set_cargador(cargador: Cargador) -> None:
    """Inyecta el loader. Llamar desde `bootstrap.py` al arrancar."""
    global _cargador, _CACHE
    _cargador = cargador
    _CACHE = {}


def cargar_equipos() -> dict[str, Equipo]:
    """Devuelve el dict, cargándolo si está vacío."""
    global _CACHE
    if not _CACHE:
        _CACHE = _cargador()
    return _CACHE


def recargar_equipos() -> dict[str, Equipo]:
    """Fuerza recarga. Llamar tras CRUD en el superadmin."""
    global _CACHE
    _CACHE = _cargador()
    return _CACHE


class _EquiposProxy:
    def __getitem__(self, key):
        return cargar_equipos()[key]

    def __iter__(self):
        return iter(cargar_equipos())

    def __len__(self):
        return len(cargar_equipos())

    def __contains__(self, key):
        return key in cargar_equipos()

    def keys(self):
        return cargar_equipos().keys()

    def values(self):
        return cargar_equipos().values()

    def items(self):
        return cargar_equipos().items()

    def get(self, key, default=None):
        return cargar_equipos().get(key, default)


EQUIPOS = _EquiposProxy()
