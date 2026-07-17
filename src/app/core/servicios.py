"""Carga de catálogos (servicios y segmentaciones) en dataclasses de dominio.

`core` no importa `repo`: la carga se hace a través de loaders inyectados por
`bootstrap.py` (ver `configurar_cargadores`). Si no se inyectan, los loaders
devuelven vacío (útil como safeguard en tests donde el bootstrap no se llamó).

Los loaders reales están en `core/loader.py` y se registran llamando
`core.loader.instalar_como_defaults()` desde `bootstrap.py`.
"""

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class ServicioInfo:
    id: int
    codigo: str
    nombre: str
    modalidad: str
    icono: str
    tipo_calculo: str
    precio_fijo: int
    tarifa_por_kg: float
    duracion_min: int
    limite_kg: Optional[int]
    tipos_equipo: tuple
    orden: int
    activo: bool

    @classmethod
    def desde(cls, row) -> "ServicioInfo":
        tipos = tuple(
            t.strip() for t in (row.tipos_equipo or "").split(",") if t.strip()
        )
        return cls(
            id=row.id,
            codigo=row.codigo,
            nombre=row.nombre,
            modalidad=row.modalidad,
            icono=row.icono,
            tipo_calculo=row.tipo_calculo,
            precio_fijo=row.precio_fijo,
            tarifa_por_kg=row.tarifa_por_kg,
            duracion_min=row.duracion_min,
            limite_kg=row.limite_kg,
            tipos_equipo=tipos,
            orden=row.orden,
            activo=bool(row.activo),
        )

    @property
    def es_personalizado(self) -> bool:
        return self.modalidad == "personalizado"

    @property
    def limite_kg_efectivo(self) -> int:
        if self.limite_kg is not None:
            return self.limite_kg
        from app.core.maquinas import EQUIPOS

        capacidades = [
            e["capacidad_kg"]
            for e in EQUIPOS.values()
            if not self.tipos_equipo or e.get("tipo") in self.tipos_equipo
        ]
        return min(capacidades) if capacidades else 0

    @property
    def precio_base(self) -> int:
        from app.core.precio import calcular_precio

        if self.tipo_calculo == "por_kg":
            return int(round(self.tarifa_por_kg))
        return self.precio_fijo


@dataclass
class SegmentacionInfo:
    id: int
    servicio_id: int
    codigo: str
    nombre: str
    descripcion: str
    tipo_calculo: str
    precio_fijo: int
    tarifa_por_kg: float
    duracion_min: int
    orden: int
    activo: bool

    @classmethod
    def desde(cls, row) -> "SegmentacionInfo":
        return cls(
            id=row.id,
            servicio_id=row.servicio_id,
            codigo=row.codigo,
            nombre=row.nombre,
            descripcion=row.descripcion,
            tipo_calculo=row.tipo_calculo,
            precio_fijo=row.precio_fijo,
            tarifa_por_kg=row.tarifa_por_kg,
            duracion_min=row.duracion_min,
            orden=row.orden,
            activo=bool(row.activo),
        )

    @property
    def precio_base(self) -> int:
        from app.core.precio import calcular_precio

        if self.tipo_calculo == "por_kg":
            return int(round(self.tarifa_por_kg))
        return self.precio_fijo


CargadorServicios = Callable[[bool], list[ServicioInfo]]
CargadorServicio = Callable[[str], Optional[ServicioInfo]]
CargadorSegmentaciones = Callable[[Optional[int], bool], list[SegmentacionInfo]]
CargadorSegmentacion = Callable[[int], Optional[SegmentacionInfo]]

_cargar_todos: CargadorServicios = lambda solo=True: []
_cargar_uno: CargadorServicio = lambda codigo: None
_cargar_por_id: Callable[[int], Optional[ServicioInfo]] = lambda id_servicio: None
_cargar_segs: CargadorSegmentaciones = lambda servicio_id=None, solo=True: []
_cargar_seg_id: CargadorSegmentacion = lambda id_seg: None


def configurar_cargadores(
    *,
    todos: CargadorServicios,
    uno: CargadorServicio,
    por_id: Callable[[int], Optional[ServicioInfo]],
    segs: CargadorSegmentaciones,
    seg_por_id: CargadorSegmentacion,
) -> None:
    """Inyecta loaders. Llamar desde `bootstrap.py` (o `core.loader.instalar_como_defaults`)."""
    global _cargar_todos, _cargar_uno, _cargar_por_id, _cargar_segs, _cargar_seg_id
    _cargar_todos = todos
    _cargar_uno = uno
    _cargar_por_id = por_id
    _cargar_segs = segs
    _cargar_seg_id = seg_por_id


def cargar_servicios(solo_activos: bool = True) -> list[ServicioInfo]:
    return _cargar_todos(solo_activos)


def cargar_servicio_por_codigo(codigo: str) -> Optional[ServicioInfo]:
    return _cargar_uno(codigo)


def cargar_servicio_por_id(id_servicio: int) -> Optional[ServicioInfo]:
    return _cargar_por_id(id_servicio)


def cargar_segmentaciones(
    servicio_id: Optional[int] = None, solo_activos: bool = True
) -> list[SegmentacionInfo]:
    return _cargar_segs(servicio_id, solo_activos)


def cargar_segmentacion_por_id(id_seg: int) -> Optional[SegmentacionInfo]:
    return _cargar_seg_id(id_seg)


def servicios_autoservicio() -> list[ServicioInfo]:
    return [s for s in cargar_servicios() if s.modalidad == "autoservicio"]


def servicios_personalizado() -> list[ServicioInfo]:
    return [s for s in cargar_servicios() if s.modalidad == "personalizado"]
