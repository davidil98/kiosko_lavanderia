"""Loaders default que conectan `core/servicios.py` con `repo/`.

Vive aquí, no en `core/servicios.py`, para mantener la regla de que `core`
no importa infra directamente. `bootstrap.py` puede sustituir estos loaders
con otros (por ejemplo, para tests o un futuro cache en memoria).
"""

from typing import Optional

from app.core.servicios import ServicioInfo, SegmentacionInfo
from app.repo import segmentaciones as repo_seg
from app.repo import servicios as repo_servicios


def cargar_todos(solo_activos: bool = True) -> list[ServicioInfo]:
    return [ServicioInfo.desde(s) for s in repo_servicios._listar(solo_activos)]


def cargar_uno(codigo: str) -> Optional[ServicioInfo]:
    s = repo_servicios._obtener_por_codigo(codigo)
    return ServicioInfo.desde(s) if s else None


def cargar_por_id(id_servicio: int) -> Optional[ServicioInfo]:
    s = repo_servicios._obtener_por_id(id_servicio)
    return ServicioInfo.desde(s) if s else None


def cargar_segs(
    servicio_id: Optional[int] = None, solo_activos: bool = True
) -> list[SegmentacionInfo]:
    return [
        SegmentacionInfo.desde(s) for s in repo_seg._listar(servicio_id, solo_activos)
    ]


def cargar_seg_id(id_seg: int) -> Optional[SegmentacionInfo]:
    s = repo_seg._obtener_por_id(id_seg)
    return SegmentacionInfo.desde(s) if s else None


def instalar_como_defaults() -> None:
    """Registra estos loaders como los de `core/servicios`."""
    from app.core import servicios

    servicios.configurar_cargadores(
        todos=cargar_todos,
        uno=cargar_uno,
        por_id=cargar_por_id,
        segs=cargar_segs,
        seg_por_id=cargar_seg_id,
    )
