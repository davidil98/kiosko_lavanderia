from dataclasses import dataclass
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


def get_limite_kg(servicio) -> int:
    """Resuelve el límite de peso: usa servicio.limite_kg si está definido,
    si no, calcula la capacidad mínima de las máquinas compatibles en EQUIPOS."""
    if servicio.limite_kg is not None:
        return servicio.limite_kg
    import hardware

    capacidades = [
        eq["capacidad_kg"]
        for eq in hardware.EQUIPOS.values()
        if not servicio.tipos_equipo or eq.get("tipo") in servicio.tipos_equipo
    ]
    return min(capacidades) if capacidades else 0


# ── Servicios de Autoservicio ──────────────────────────────────────────────────
SERVICIOS_AUTO = [
    ServicioInfo(
        nombre="Autolavado",
        precio=45,
        duracion_min=45,
        modalidad="autoservicio",
        icono="/media/icons/leaf.svg",
        tipos_equipo=("mixto", "lavado"),
    ),
    ServicioInfo(
        nombre="Secado",
        precio=50,
        duracion_min=45,
        modalidad="autoservicio",
        icono="/media/icons/wind.svg",
        tipos_equipo=("mixto", "secado"),
    ),
]

# ── Sub-opciones de Lavado Personalizado ──────────────────────────────────────
# Se cobra en mostrador al recibir la ropa ($150 por edredón o hasta 5 Kg de ropa/tela)
SERVICIOS_PERSONALIZADO = [
    ServicioInfo(
        nombre="Personalizado – Edredones",
        precio=150,
        duracion_min=90,
        modalidad="personalizado",
        icono="/media/icons/bed.svg",
        subtipo="edredones",
        limite_kg=5,
    ),
    ServicioInfo(
        nombre="Personalizado – Ropa",
        precio=150,
        duracion_min=60,
        modalidad="personalizado",
        icono="/media/icons/shirt.svg",
        subtipo="ropa",
        limite_kg=5,
    ),
]

# Lista completa para retrocompatibilidad
SERVICIOS = SERVICIOS_AUTO + SERVICIOS_PERSONALIZADO

# Pasos del wizard del cliente
PASOS = [
    "1. Selección de Servicio",
    "2. Ingresar Nombre",
    "3. Pesar Ropa",
    "4. Insertar Monedas",
    "5. Pago Exitoso",
]


class KioskoState:
    def __init__(self):
        self.servicio_seleccionado: Optional[ServicioInfo] = None
        self.nombre_cliente: str = ""
        self.dinero_ingresado: int = 0
        self.peso_ingresado: float = 0.0
        self.exito: bool = False
        self.en_procesamiento: bool = False
        self.alerta_excedente_mostrada: bool = False
        self.ultimo_id_transaccion: Optional[int] = None
        # 0=seleccion, 0.5=sub-seleccion lavado personalizado,
        # 1=nombre, 2=pesar, 3=pago, 4=exito
        self.paso_actual: int = 0
        self.mostrando_sub_lavar: bool = (
            False  # True cuando se muestran sub-opciones de Lavar
        )
        self.callback_on_change = None

    def set_callback(self, callback):
        self.callback_on_change = callback

    def _trigger_change(self):
        if self.callback_on_change:
            self.callback_on_change()

    def seleccionar_servicio(self, servicio_nombre: str):
        for s in SERVICIOS:
            if s.nombre == servicio_nombre:
                self.servicio_seleccionado = s
                self.dinero_ingresado = 0
                self.peso_ingresado = 0.0
                self.exito = False
                self.mostrando_sub_lavar = False
                self.paso_actual = 1
                self._trigger_change()
                return

    def mostrar_sub_lavar(self):
        """Muestra el sub-menú de Lavado (Autolavado vs Personalizado)."""
        self.mostrando_sub_lavar = True
        self._trigger_change()

    def confirmar_nombre(self, nombre: str):
        self.nombre_cliente = nombre.strip() or "Cliente"
        self.paso_actual = 2
        self._trigger_change()

    def ingresar_dinero(self, monto: int):
        if not self.servicio_seleccionado or self.exito:
            return
        # El servicio personalizado no requiere pago en kiosko
        if self.servicio_seleccionado.modalidad == "personalizado":
            return
        self.dinero_ingresado += monto
        self._trigger_change()

    def get_faltante(self) -> int:
        if not self.servicio_seleccionado:
            return 0
        return max(0, self.servicio_seleccionado.precio - self.dinero_ingresado)

    def get_cambio(self) -> int:
        if not self.servicio_seleccionado:
            return 0
        return max(0, self.dinero_ingresado - self.servicio_seleccionado.precio)

    def get_limite_kg(self) -> int:
        """Capacidad máxima de carga para el servicio seleccionado (0 = sin límite)."""
        if not self.servicio_seleccionado:
            return 0
        return get_limite_kg(self.servicio_seleccionado)

    def puede_pagar(self) -> bool:
        if not self.servicio_seleccionado:
            return False
        # El personalizado siempre puede "confirmar" (se paga en mostrador)
        if self.servicio_seleccionado.modalidad == "personalizado":
            return True
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
        self._trigger_change()
