"""Mapeo de filas SQLite a dataclasses.

Único lugar del proyecto que hace `dict(row)`. Los repos pasan la conexión y
reciben dicts ya mapeados, no `sqlite3.Row`.
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class Servicio:
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
    tipos_equipo: str
    orden: int
    activo: bool


@dataclass(frozen=True)
class Segmentacion:
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


@dataclass(frozen=True)
class Maquina:
    id: int
    codigo: str
    nombre: str
    tipo: str
    capacidad_kg: int
    gpio: int
    modo: str
    duracion_max_min: int
    activa: bool
    orden: int


@dataclass(frozen=True)
class Transaccion:
    id_transaccion: int
    fecha_hora: Optional[str]
    tipo_servicio: Optional[str]
    monto_pagado: int
    dinero_ingresado: int
    cambio_devuelto: int
    id_equipo: Optional[str]
    duracion_estimada_min: Optional[int]
    estado: str
    nombre_cliente: str
    inicio_servicio: Optional[str]
    peso_kg: float
    notas: str
    etapa_kanban: Optional[str]
    modalidad: str
    numero_transaccion_terminal: str
    validado_por: str
    mp_order_id: str


@dataclass(frozen=True)
class CorteCaja:
    id: int
    fecha: str
    usuario_apertura: str
    saldo_inicial: int
    usuario_cierre: Optional[str]
    saldo_real: Optional[int]
    saldo_esperado: Optional[int]
    diferencia: Optional[int]
    estado: str
    notas: str
    hora_apertura: str
    hora_cierre: Optional[str]


@dataclass(frozen=True)
class MovimientoCaja:
    id: int
    corte_id: int
    fecha_hora: str
    tipo: str
    monto: int
    concepto: str
    usuario: str
    notas: str
    auto: int


def _to_int(v: Any, default: int = 0) -> int:
    if v is None or v == "":
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _to_float(v: Any, default: float = 0.0) -> float:
    if v is None or v == "":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _to_bool(v: Any) -> bool:
    return bool(v) and v != 0


def _to_str(v: Any, default: str = "") -> str:
    return default if v is None else str(v)


def servicio(row) -> Servicio:
    return Servicio(
        id=_to_int(row["id"]),
        codigo=_to_str(row["codigo"]),
        nombre=_to_str(row["nombre"]),
        modalidad=_to_str(row["modalidad"]),
        icono=_to_str(row["icono"], "/media/icons/leaf.svg"),
        tipo_calculo=_to_str(row["tipo_calculo"], "fijo"),
        precio_fijo=_to_int(row["precio_fijo"]),
        tarifa_por_kg=_to_float(row["tarifa_por_kg"]),
        duracion_min=_to_int(row["duracion_min"]),
        limite_kg=_to_int(row["limite_kg"])
        if row["limite_kg"] not in (None, "")
        else None,
        tipos_equipo=_to_str(row["tipos_equipo"]),
        orden=_to_int(row["orden"]),
        activo=_to_bool(row["activo"]),
    )


def segmentacion(row) -> Segmentacion:
    return Segmentacion(
        id=_to_int(row["id"]),
        servicio_id=_to_int(row["servicio_id"]),
        codigo=_to_str(row["codigo"]),
        nombre=_to_str(row["nombre"]),
        descripcion=_to_str(row["descripcion"]),
        tipo_calculo=_to_str(row["tipo_calculo"], "fijo"),
        precio_fijo=_to_int(row["precio_fijo"]),
        tarifa_por_kg=_to_float(row["tarifa_por_kg"]),
        duracion_min=_to_int(row["duracion_min"]),
        orden=_to_int(row["orden"]),
        activo=_to_bool(row["activo"]),
    )


def maquina(row) -> Maquina:
    return Maquina(
        id=_to_int(row["id"]),
        codigo=_to_str(row["codigo"]),
        nombre=_to_str(row["nombre"]),
        tipo=_to_str(row["tipo"]),
        capacidad_kg=_to_int(row["capacidad_kg"]),
        gpio=_to_int(row["gpio"]),
        modo=_to_str(row["modo"], "pulso"),
        duracion_max_min=_to_int(row["duracion_max_min"], 25),
        activa=_to_bool(row["activa"]),
        orden=_to_int(row["orden"]),
    )


def transaccion(row) -> Transaccion:
    return Transaccion(
        id_transaccion=_to_int(row["id_transaccion"]),
        fecha_hora=row["fecha_hora"],
        tipo_servicio=row["tipo_servicio"],
        monto_pagado=_to_int(row["monto_pagado"]),
        dinero_ingresado=_to_int(row["dinero_ingresado"]),
        cambio_devuelto=_to_int(row["cambio_devuelto"]),
        id_equipo=row["id_equipo"],
        duracion_estimada_min=_to_int(row["duracion_estimada_min"])
        if row["duracion_estimada_min"] not in (None, "")
        else None,
        estado=_to_str(row["estado"], "Pendiente"),
        nombre_cliente=_to_str(row["nombre_cliente"], "Cliente"),
        inicio_servicio=row["inicio_servicio"],
        peso_kg=_to_float(row["peso_kg"]),
        notas=_to_str(row["notas"]),
        etapa_kanban=row["etapa_kanban"],
        modalidad=_to_str(row["modalidad"], "autoservicio"),
        numero_transaccion_terminal=_to_str(row["numero_transaccion_terminal"]),
        validado_por=_to_str(row["validado_por"]),
        mp_order_id=_to_str(row["mp_order_id"]),
    )


def transaccion_dict(row) -> dict:
    """Devuelve un dict para los callers que no quieren el dataclass todavía
    (muchas pantallas de admin esperan un dict con keys string)."""
    return {
        "id_transaccion": _to_int(row["id_transaccion"]),
        "fecha_hora": row["fecha_hora"],
        "tipo_servicio": row["tipo_servicio"],
        "monto_pagado": _to_int(row["monto_pagado"]),
        "dinero_ingresado": _to_int(row["dinero_ingresado"]),
        "cambio_devuelto": _to_int(row["cambio_devuelto"]),
        "id_equipo": row["id_equipo"],
        "duracion_estimada_min": _to_int(row["duracion_estimada_min"])
        if row["duracion_estimada_min"] not in (None, "")
        else None,
        "estado": _to_str(row["estado"], "Pendiente"),
        "nombre_cliente": _to_str(row["nombre_cliente"], "Cliente"),
        "inicio_servicio": row["inicio_servicio"],
        "peso_kg": _to_float(row["peso_kg"]),
        "notas": _to_str(row["notas"]),
        "etapa_kanban": row["etapa_kanban"],
        "modalidad": _to_str(row["modalidad"], "autoservicio"),
        "numero_transaccion_terminal": _to_str(row["numero_transaccion_terminal"]),
        "validado_por": _to_str(row["validado_por"]),
        "mp_order_id": _to_str(row["mp_order_id"]),
    }


def corte_caja(row) -> CorteCaja:
    return CorteCaja(
        id=_to_int(row["id"]),
        fecha=_to_str(row["fecha"]),
        usuario_apertura=_to_str(row["usuario_apertura"]),
        saldo_inicial=_to_int(row["saldo_inicial"]),
        usuario_cierre=row["usuario_cierre"],
        saldo_real=_to_int(row["saldo_real"])
        if row["saldo_real"] not in (None, "")
        else None,
        saldo_esperado=_to_int(row["saldo_esperado"])
        if row["saldo_esperado"] not in (None, "")
        else None,
        diferencia=_to_int(row["diferencia"])
        if row["diferencia"] not in (None, "")
        else None,
        estado=_to_str(row["estado"], "abierto"),
        notas=_to_str(row["notas"]),
        hora_apertura=_to_str(row["hora_apertura"]),
        hora_cierre=row["hora_cierre"],
    )


def movimiento_caja(row) -> MovimientoCaja:
    return MovimientoCaja(
        id=_to_int(row["id"]),
        corte_id=_to_int(row["corte_id"]),
        fecha_hora=_to_str(row["fecha_hora"]),
        tipo=_to_str(row["tipo"]),
        monto=_to_int(row["monto"]),
        concepto=_to_str(row["concepto"]),
        usuario=_to_str(row["usuario"]),
        notas=_to_str(row["notas"]),
        auto=_to_int(row["auto"]),
    )
