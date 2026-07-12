from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ServicioInfo:
    nombre: str
    precio: int
    duracion_min: int
    modalidad: str = "autoservicio"  # 'autoservicio' | 'personalizado'
    icono: str = "/media/icons/leaf.svg"
    subtipo: str = ""  # Para lavado personalizado: 'edredones' | 'ropa'
    limite_kg: Optional[int] = None  # Si None, se calcula desde EQUIPOS
    tipos_equipo: tuple = ()  # Tipos de máquina aceptados; vacío = cualquiera
    # Nuevos campos (data-driven) — con defaults para retrocompatibilidad
    codigo: str = field(default="")
    precio_fijo: int = field(default=0)
    tipo_calculo: str = field(default="fijo")
    tarifa_por_kg: float = field(default=0.0)
    id: int = field(default=0)
    activo: bool = field(default=True)

    @property
    def precio_calculado(self) -> int:
        """Precio base (para 'fijo' o fallback). Para 'por_kg' se usa
        calcular_precio() con el peso."""
        if self.tipo_calculo == "por_kg":
            return int(round(self.tarifa_por_kg * 1))
        return int(self.precio_fijo or self.precio)


def _row_a_servicio(row: dict) -> ServicioInfo:
    """Convierte una fila de la tabla servicios a ServicioInfo."""
    tipos = tuple(
        t.strip() for t in (row.get("tipos_equipo") or "").split(",") if t.strip()
    )
    limite = row.get("limite_kg")
    return ServicioInfo(
        id=row["id"],
        codigo=row["codigo"],
        nombre=row["nombre"],
        precio=row.get("precio_fijo") or 0,
        precio_fijo=row.get("precio_fijo") or 0,
        duracion_min=row.get("duracion_min") or 0,
        modalidad=row["modalidad"],
        icono=row.get("icono") or "/media/icons/leaf.svg",
        limite_kg=limite,
        tipos_equipo=tipos,
        tipo_calculo=row.get("tipo_calculo") or "fijo",
        tarifa_por_kg=float(row.get("tarifa_por_kg") or 0),
        activo=bool(row.get("activo", 1)),
    )


def cargar_servicios(solo_activos: bool = True) -> list:
    """Carga todos los servicios desde la DB. Llamar cada vez que se
    necesite la lista actualizada (no usar import-time cache)."""
    import database_web

    filas = database_web._listar_servicios(solo_activos=solo_activos)
    return [_row_a_servicio(f) for f in filas]


def get_servicio_por_codigo(codigo: str):
    """Devuelve el ServicioInfo por su código, o None si no existe."""
    import database_web

    fila = database_web._obtener_servicio_por_codigo(codigo)
    return _row_a_servicio(fila) if fila else None


@dataclass
class SegmentacionInfo:
    """Variante dentro de un servicio (ej. 'Lava + Seca + Dobla').

    Una segmentación es 100% data-driven. Tiene los mismos campos de cálculo
    que un ServicioInfo (tipo_calculo, precio_fijo, tarifa_por_kg) y se cobra
    con la misma función `calcular_precio()`.
    """

    id: int
    servicio_id: int
    codigo: str
    nombre: str
    descripcion: str = ""
    tipo_calculo: str = "fijo"
    precio_fijo: int = 0
    tarifa_por_kg: float = 0.0
    duracion_min: int = 0
    orden: int = 0
    activo: bool = True

    @property
    def precio_calculado(self) -> int:
        if self.tipo_calculo == "por_kg":
            return int(round(self.tarifa_por_kg * 1))
        return int(self.precio_fijo or 0)


def _row_a_segmentacion(row: dict) -> SegmentacionInfo:
    return SegmentacionInfo(
        id=row["id"],
        servicio_id=row["servicio_id"],
        codigo=row["codigo"],
        nombre=row["nombre"],
        descripcion=row.get("descripcion") or "",
        tipo_calculo=row.get("tipo_calculo") or "fijo",
        precio_fijo=row.get("precio_fijo") or 0,
        tarifa_por_kg=float(row.get("tarifa_por_kg") or 0),
        duracion_min=row.get("duracion_min") or 0,
        orden=row.get("orden") or 0,
        activo=bool(row.get("activo", 1)),
    )


def cargar_segmentaciones(servicio_id=None, solo_activos: bool = True) -> list:
    """Carga las segmentaciones. Si servicio_id es None, trae todas."""
    import database_web

    filas = database_web._listar_segmentaciones(servicio_id, solo_activos)
    return [_row_a_segmentacion(f) for f in filas]


def get_segmentacion_por_id(id_seg):
    """Devuelve un SegmentacionInfo por id, o None si no existe."""
    import database_web

    fila = database_web._obtener_segmentacion_por_id(id_seg)
    return _row_a_segmentacion(fila) if fila else None


def calcular_precio(servicio, peso_kg: float = 0.0) -> int:
    """Calcula el precio final según el tipo de cálculo.

    Acepta un ServicioInfo o un SegmentacionInfo (ambos tienen
    `tipo_calculo`, `precio_fijo`, `tarifa_por_kg`).
    """
    tipo = getattr(servicio, "tipo_calculo", "fijo") or "fijo"
    if tipo == "fijo":
        return int(getattr(servicio, "precio_fijo", 0) or 0)
    if tipo == "por_kg":
        tarifa = float(getattr(servicio, "tarifa_por_kg", 0) or 0)
        return int(round(tarifa * max(0.0, float(peso_kg or 0))))
    if tipo == "por_duracion":
        return int(getattr(servicio, "precio_fijo", 0) or 0)
    return int(
        getattr(servicio, "precio_fijo", 0) or getattr(servicio, "precio", 0) or 0
    )


def format_precio(item, peso_kg: float = 0.0) -> str:
    """Formatea el precio de un ServicioInfo o SegmentacionInfo para mostrar."""
    tipo = getattr(item, "tipo_calculo", "fijo") or "fijo"
    if tipo == "por_kg":
        tarifa = float(getattr(item, "tarifa_por_kg", 0) or 0)
        return f"${int(round(tarifa))}/kg"
    return f"${calcular_precio(item, peso_kg)}"


# ── Catálogo: wrapper deprecado. Usar cargar_servicios() en su lugar. ──────────
# Se mantiene por compatibilidad con código que aún importa SERVICIOS_AUTO /
# SERVICIOS_PERSONALIZADO, pero siempre devuelve la lista actual de la DB.
def SERVICIOS_AUTO() -> list:
    return [s for s in cargar_servicios() if s.modalidad == "autoservicio"]


def SERVICIOS_PERSONALIZADO() -> list:
    return [s for s in cargar_servicios() if s.modalidad == "personalizado"]


def SERVICIOS() -> list:
    return cargar_servicios()


# Alias para que `from models import SERVICIOS` siga funcionando en tests.
SERVICIOS_AUTO = SERVICIOS_AUTO  # callable
SERVICIOS_PERSONALIZADO = SERVICIOS_PERSONALIZADO
SERVICIOS = SERVICIOS

# Mantener las constantes de pasos (no dependen de DB)
PASOS = [
    "1. Selección de Servicio",
    "2. Ingresar Nombre",
    "3. Pesar Ropa",
    "4. Pagar",
    "5. Pago Exitoso",
]


class KioskoState:
    def __init__(self):
        self.servicio_seleccionado: Optional[ServicioInfo] = None
        self.segmentacion_seleccionada: Optional[SegmentacionInfo] = None
        self.nombre_cliente: str = ""
        self.dinero_ingresado: int = 0
        self.peso_ingresado: float = 0.0
        self.exito: bool = False
        self.en_procesamiento: bool = False
        self.alerta_excedente_mostrada: bool = False
        self.ultimo_id_transaccion: Optional[int] = None
        # 0=seleccion, 1=nombre, 2=pesar, 2.5=segmentacion, 3=pago, 4=exito
        # Sub-estados: mostrando_sub_lavar (paso 0), mostrando_segmentaciones (paso 2),
        # mostrando_metodos_pago (paso 2.5 o paso 2 sin segmentaciones).
        self.paso_actual: int = 0
        self.mostrando_sub_lavar: bool = False
        self.mostrando_segmentaciones: bool = False
        self.mostrando_metodos_pago: bool = False
        self.metodo_pago_codigo: Optional[str] = None
        self.metodo_pago_instancia: Optional[object] = None
        # Aprobación admin
        self.esperando_aprobacion_admin: bool = False
        self.motivo_espera: str = ""  # 'peso' | 'pago'
        self.peso_en_revision: float = 0.0
        self.peso_rechazado_notificado: bool = False
        self.callback_on_change = None
        self.notificar_admin = lambda: None  # Callback set from main.py

    def set_callback(self, callback):
        self.callback_on_change = callback

    def _trigger_change(self):
        if self.callback_on_change:
            self.callback_on_change()

    def seleccionar_servicio(self, servicio_codigo: str):
        """Selecciona un servicio por su código (data-driven)."""
        srv = get_servicio_por_codigo(servicio_codigo)
        if not srv:
            return
        self.servicio_seleccionado = srv
        self.segmentacion_seleccionada = None
        self.dinero_ingresado = 0
        self.peso_ingresado = 0.0
        self.exito = False
        self.mostrando_sub_lavar = False
        self.mostrando_segmentaciones = False
        self.mostrando_metodos_pago = False
        self.paso_actual = 1
        self._trigger_change()

    def seleccionar_segmentacion(self, id_segmentacion: int):
        """Selecciona una segmentación por su id."""
        seg = get_segmentacion_por_id(id_segmentacion)
        if not seg:
            return
        self.segmentacion_seleccionada = seg
        self.mostrando_segmentaciones = False
        self.mostrando_metodos_pago = True
        self._trigger_change()

    def get_item_cobro(self):
        """Devuelve la segmentación si está seleccionada, si no el servicio.
        Es el item que se usa para calcular el precio final."""
        return self.segmentacion_seleccionada or self.servicio_seleccionado

    def mostrar_segmentaciones(self):
        """Muestra el sub-menú de selección de segmentación (paso 2.5)."""
        self.mostrando_segmentaciones = True
        self.mostrando_metodos_pago = False
        self._trigger_change()

    def mostrar_sub_lavar(self):
        """Muestra el sub-menú de Lavado (Autolavado vs Personalizado)."""
        self.mostrando_sub_lavar = True
        self._trigger_change()

    def mostrar_metodos_pago(self):
        """Muestra el sub-menú de selección de método de pago (paso 2)."""
        self.mostrando_metodos_pago = True
        self._trigger_change()

    def marcar_esperando_admin(self, motivo: str):
        """Activa el overlay de espera de aprobación del administrador."""
        self.esperando_aprobacion_admin = True
        self.motivo_espera = motivo
        self._trigger_change()

    def limpiar_espera_admin(self):
        """Desactiva el overlay de espera."""
        self.esperando_aprobacion_admin = False
        self.motivo_espera = ""
        self._trigger_change()

    def confirmar_nombre(self, nombre: str):
        self.nombre_cliente = nombre.strip() or "Cliente"
        self.paso_actual = 2
        self._trigger_change()

    def ingresar_dinero(self, monto: int):
        if not self.servicio_seleccionado or self.exito:
            return
        # Los personalizados también pueden pagarse en el kiosko (cualquier método)
        self.dinero_ingresado += monto
        self._trigger_change()

    def get_faltante(self) -> int:
        if not self.servicio_seleccionado:
            return 0
        if self.servicio_seleccionado.tipo_calculo == "por_kg":
            # El faltante se calcula contra el precio actual estimado con el peso
            precio = calcular_precio(self.servicio_seleccionado, self.peso_ingresado)
        else:
            precio = self.servicio_seleccionado.precio
        return max(0, precio - self.dinero_ingresado)

    def get_cambio(self) -> int:
        if not self.servicio_seleccionado:
            return 0
        if self.servicio_seleccionado.tipo_calculo == "por_kg":
            precio = calcular_precio(self.servicio_seleccionado, self.peso_ingresado)
        else:
            precio = self.servicio_seleccionado.precio
        return max(0, self.dinero_ingresado - precio)

    def get_limite_kg(self) -> int:
        """Capacidad máxima de carga para el servicio seleccionado (0 = sin límite)."""
        if not self.servicio_seleccionado:
            return 0
        if self.servicio_seleccionado.limite_kg is not None:
            return self.servicio_seleccionado.limite_kg
        import hardware

        capacidades = [
            eq["capacidad_kg"]
            for eq in hardware.EQUIPOS.values()
            if not self.servicio_seleccionado.tipos_equipo
            or eq.get("tipo") in self.servicio_seleccionado.tipos_equipo
        ]
        return min(capacidades) if capacidades else 0

    def puede_pagar(self) -> bool:
        if not self.servicio_seleccionado:
            return False
        # El personalizado siempre puede "confirmar" (se paga en mostrador)
        if self.servicio_seleccionado.modalidad == "personalizado":
            return True
        if self.servicio_seleccionado.tipo_calculo == "por_kg":
            precio = calcular_precio(self.servicio_seleccionado, self.peso_ingresado)
            return self.dinero_ingresado >= precio
        return self.dinero_ingresado >= self.servicio_seleccionado.precio

    def procesar_exito(self, id_transaccion: int):
        self.exito = True
        self.ultimo_id_transaccion = id_transaccion
        self.paso_actual = 4
        self._trigger_change()

    def reset(self):
        self.servicio_seleccionado = None
        self.nombre_cliente = ""
        self.dinero_ingresado = 0
        self.peso_ingresado = 0.0
        self.exito = False
        self.en_procesamiento = False
        self.alerta_excedente_mostrada = False
        self.ultimo_id_transaccion = None
        self.paso_actual = 0
        self.mostrando_sub_lavar = False
        self.mostrando_metodos_pago = False
        self.metodo_pago_codigo = None
        self.metodo_pago_instancia = None
        self.esperando_aprobacion_admin = False
        self.motivo_espera = ""
        self.peso_en_revision = 0.0
        self.peso_rechazado_notificado = False
        self._trigger_change()
