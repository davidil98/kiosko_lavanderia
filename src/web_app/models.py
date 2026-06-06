from dataclasses import dataclass
from typing import Optional

@dataclass
class ServicioInfo:
    nombre: str
    precio: int
    duracion_min: int

# Constantes de servicios
SERVICIOS = [
    ServicioInfo(nombre="Lavar", precio=35, duracion_min=45),
    ServicioInfo(nombre="Secar", precio=45, duracion_min=45),
    ServicioInfo(nombre="Lavar y secar", precio=75, duracion_min=90)
]

class KioskoState:
    def __init__(self):
        self.servicio_seleccionado: Optional[ServicioInfo] = None
        self.dinero_ingresado: int = 0
        self.exito: bool = False
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
                self._trigger_change()
                return

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

    def procesar_exito(self):
        self.exito = True
        self._trigger_change()

    def reset(self):
        self.servicio_seleccionado = None
        self.dinero_ingresado = 0
        self.exito = False
        self._trigger_change()
