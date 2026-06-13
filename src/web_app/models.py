from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ServicioInfo:
    nombre: str
    precio: int
    duracion_min: int

# Solo Lavar y Secar por ahora
SERVICIOS = [
    ServicioInfo(nombre="Lavar", precio=35, duracion_min=45),
    ServicioInfo(nombre="Secar", precio=45, duracion_min=45),
]

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
        self.nombre_cliente: str = ''
        self.dinero_ingresado: int = 0
        self.exito: bool = False
        self.en_procesamiento: bool = False
        self.alerta_excedente_mostrada: bool = False
        self.ultimo_id_transaccion: Optional[int] = None
        # 0=seleccion, 1=nombre, 2=pago, 3=exito
        self.paso_actual: int = 0
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
                self.exito = False
                self.paso_actual = 1
                self._trigger_change()
                return

    def confirmar_nombre(self, nombre: str):
        self.nombre_cliente = nombre.strip() or 'Cliente'
        self.paso_actual = 2
        self._trigger_change()

    def ingresar_dinero(self, monto: int):
        if not self.servicio_seleccionado or self.exito:
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

    def puede_pagar(self) -> bool:
        if not self.servicio_seleccionado:
            return False
        return self.dinero_ingresado >= self.servicio_seleccionado.precio

    def procesar_exito(self, id_transaccion: int):
        self.exito = True
        self.ultimo_id_transaccion = id_transaccion
        self.paso_actual = 4
        self._trigger_change()

    def reset(self):
        self.servicio_seleccionado = None
        self.nombre_cliente = ''
        self.dinero_ingresado = 0
        self.exito = False
        self.en_procesamiento = False
        self.alerta_excedente_mostrada = False
        self.ultimo_id_transaccion = None
        self.paso_actual = 0
        self._trigger_change()
