"""Estado del wizard del kiosko cliente.

Reemplaza el `KioskoState` monolítico (22 atributos + 4 booleanos) por:
- `paso`: enum de 5 valores
- `sub`: enum de 4 sub-estados
- `esperando_admin`: tupla (motivo, metodo) | None

El wizard es **inmutable por convención**: cada cambio de paso/sub produce
un nuevo estado via `dataclasses.replace`. Las páginas leen y llaman a
los métodos que devuelven un nuevo wizard.

Decisión clave: el `wizard` se guarda en un dict `app.storage.user` por
sesión, no en un singleton global. Esto permite tener varios clientes
abiertos a la vez sin que se pisen entre sí.
"""

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Optional

from app.core.estados import MetodoPago
from app.core.precio import calcular_precio
from app.core.servicios import SegmentacionInfo, ServicioInfo


class Paso(str, Enum):
    SERVICIO = "servicio"
    NOMBRE = "nombre"
    PESO = "peso"
    PAGO = "pago"
    EXITO = "exito"


class Sub(str, Enum):
    NINGUNO = "ninguno"
    SUB_LAVAR = "sub_lavar"
    SEGMENTACIONES = "segmentaciones"
    METODOS_PAGO = "metodos_pago"


_NOMBRES_PASO = {
    Paso.SERVICIO: "1. Selección de Servicio",
    Paso.NOMBRE: "2. Ingresar Nombre",
    Paso.PESO: "3. Pesar Ropa",
    Paso.PAGO: "4. Pagar",
    Paso.EXITO: "5. Pago Exitoso",
}


def nombre_paso(p: Paso) -> str:
    return _NOMBRES_PASO[p]


@dataclass(frozen=True)
class WizardKiosko:
    paso: Paso = Paso.SERVICIO
    sub: Sub = Sub.NINGUNO
    servicio: Optional[ServicioInfo] = None
    segmentacion: Optional[SegmentacionInfo] = None
    nombre: str = ""
    peso: float = 0.0
    dinero: int = 0
    metodo: Optional[MetodoPago] = None
    ultimo_id_transaccion: Optional[int] = None
    esperando_admin: Optional[tuple[str, str]] = None  # (motivo, metodo_codigo)
    peso_rechazado_notificado: bool = False

    @classmethod
    def desde_dict(cls, d: dict) -> "WizardKiosko":
        if not isinstance(d, dict):
            return cls()
        data = dict(d)
        if "paso" in data and isinstance(data["paso"], str):
            try:
                data["paso"] = Paso(data["paso"])
            except ValueError:
                data["paso"] = Paso.SERVICIO
        if "sub" in data and isinstance(data["sub"], str):
            try:
                data["sub"] = Sub(data["sub"])
            except ValueError:
                data["sub"] = Sub.NINGUNO
        if "metodo" in data and isinstance(data["metodo"], str):
            try:
                data["metodo"] = MetodoPago(data["metodo"])
            except ValueError:
                data["metodo"] = None
        if "servicio" in data and isinstance(data["servicio"], dict):
            try:
                data["servicio"] = ServicioInfo(**data["servicio"])
            except Exception:
                data["servicio"] = None
        if "segmentacion" in data and isinstance(data["segmentacion"], dict):
            try:
                data["segmentacion"] = SegmentacionInfo(**data["segmentacion"])
            except Exception:
                data["segmentacion"] = None
        if "esperando_admin" in data and isinstance(data["esperando_admin"], list):
            data["esperando_admin"] = tuple(data["esperando_admin"])
        return cls(**data)

    # ── Transiciones ─────────────────────────────────────────────────────────

    def with_nombre(self, nombre: str) -> "WizardKiosko":
        return replace(self, nombre=nombre)

    def seleccionar_servicio(self, codigo: str) -> "WizardKiosko":
        """Elige servicio por código. Carga `ServicioInfo` y avanza a NOMBRE."""
        from app.core.servicios import cargar_servicio_por_codigo

        srv = cargar_servicio_por_codigo(codigo)
        if srv is None:
            return self
        return replace(
            self,
            servicio=srv,
            segmentacion=None,
            dinero=0,
            peso=0.0,
            metodo=None,
            sub=Sub.NINGUNO,
            paso=Paso.NOMBRE,
        )

    def seleccionar_segmentacion(self, id_seg: int) -> "WizardKiosko":
        """Elige segmentación. Avanza a METODOS_PAGO."""
        from app.core.servicios import cargar_segmentacion_por_id

        seg = cargar_segmentacion_por_id(id_seg)
        if seg is None:
            return self
        return replace(self, segmentacion=seg, sub=Sub.METODOS_PAGO)

    def mostrar_sub_lavar(self) -> "WizardKiosko":
        return replace(self, sub=Sub.SUB_LAVAR)

    def ocultar_sub_lavar(self) -> "WizardKiosko":
        return replace(self, sub=Sub.NINGUNO)

    def mostrar_segmentaciones(self) -> "WizardKiosko":
        return replace(self, sub=Sub.SEGMENTACIONES)

    def mostrar_metodos_pago(self) -> "WizardKiosko":
        return replace(self, sub=Sub.METODOS_PAGO)

    def confirmar_nombre(self) -> "WizardKiosko":
        nombre = (self.nombre or "").strip() or "Cliente"
        return replace(self, nombre=nombre, paso=Paso.PESO, sub=Sub.NINGUNO)

    def capturar_peso(self, kg: float) -> "WizardKiosko":
        return replace(self, peso=kg)

    def volver_a_pesar(self) -> "WizardKiosko":
        return replace(
            self, peso=0.0, esperando_admin=None, sub=Sub.NINGUNO, paso=Paso.PESO
        )

    def iniciar_pago(self) -> "WizardKiosko":
        """El cliente eligió un método de pago. Pasamos a PAGO."""
        return replace(self, paso=Paso.PAGO, sub=Sub.NINGUNO)

    def seleccionar_metodo(self, metodo: MetodoPago) -> "WizardKiosko":
        return replace(self, metodo=metodo)

    def ir_a_exito(self, id_transaccion: int) -> "WizardKiosko":
        return replace(
            self,
            paso=Paso.EXITO,
            sub=Sub.NINGUNO,
            esperando_admin=None,
            ultimo_id_transaccion=id_transaccion,
        )

    def empezar_espera(self, motivo: str, metodo_codigo: str = "") -> "WizardKiosko":
        return replace(self, esperando_admin=(motivo, metodo_codigo))

    def terminar_espera(self) -> "WizardKiosko":
        return replace(self, esperando_admin=None)

    def confirmar_peso_desde_admin(self) -> "WizardKiosko":
        """Admin aprobó el peso: terminar espera y avanzar al paso de pago."""
        return self.terminar_espera().iniciar_pago()

    def notificar_rechazo_peso(self) -> "WizardKiosko":
        return replace(self, peso_rechazado_notificado=True, peso=0.0)

    def reset(self) -> "WizardKiosko":
        return WizardKiosko()

    # ── Helpers de cálculo ──────────────────────────────────────────────────

    def item_cobro(self) -> Optional[ServicioInfo | SegmentacionInfo]:
        """El item a cobrar: segmentación si la hay, si no el servicio."""
        return self.segmentacion or self.servicio

    def precio_total(self) -> int:
        item = self.item_cobro()
        if item is None:
            return 0
        return calcular_precio(item, self.peso)

    def limite_kg(self) -> int:
        """Capacidad máxima derivada del servicio y de las máquinas."""
        if self.servicio is None:
            return 0
        if self.servicio.limite_kg is not None:
            return self.servicio.limite_kg
        return self.servicio.limite_kg_efectivo

    def puede_pagar_monedas(self) -> bool:
        if self.servicio is None:
            return False
        if self.dinero < self.precio_total():
            return False
        return True
