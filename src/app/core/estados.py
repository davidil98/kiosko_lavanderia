"""Enums del dominio: estados, modalidades, métodos de pago, etapas y tipos de cálculo.

Regla absoluta: cero comparaciones con strings en el resto del código.
`if orden.estado == EstadoOrden.PENDIENTE`, nunca `if orden.estado == "Pendiente"`.
"""

from enum import Enum


class EstadoOrden(str, Enum):
    PENDIENTE_PESO = "Pendiente-peso"
    PROCESANDO_PAGO = "Procesando-pago"
    PENDIENTE_PAGO = "Pendiente-pago"
    PENDIENTE = "Pendiente"
    EN_CURSO = "En-curso"
    FINALIZADO = "Finalizado"
    CANCELADO = "Cancelado"


class Modalidad(str, Enum):
    AUTOSERVICIO = "autoservicio"
    PERSONALIZADO = "personalizado"

    AUTOSERVICIO_MONEDAS = "autoservicio-monedas"
    AUTOSERVICIO_POINT = "autoservicio-point"
    AUTOSERVICIO_MOSTRADOR = "autoservicio-mostrador"

    PERSONALIZADO_MONEDAS = "personalizado-monedas"
    PERSONALIZADO_POINT = "personalizado-point"
    PERSONALIZADO_MOSTRADOR = "personalizado-mostrador"

    BYPASS = "bypass"

    @property
    def base(self) -> "Modalidad":
        """Devuelve la modalidad base (sin método de pago)."""
        if self.value.startswith("autoservicio"):
            return Modalidad.AUTOSERVICIO
        if self.value.startswith("personalizado"):
            return Modalidad.PERSONALIZADO
        return self

    @property
    def es_personalizado(self) -> bool:
        return self.base is Modalidad.PERSONALIZADO

    @classmethod
    def de(cls, base: "Modalidad", metodo: "MetodoPago") -> "Modalidad":
        """Compone una modalidad con método de pago sin usar f-strings."""
        if base is cls.BYPASS:
            return cls.BYPASS
        tabla = {
            (Modalidad.AUTOSERVICIO, MetodoPago.MONEDAS): cls.AUTOSERVICIO_MONEDAS,
            (Modalidad.AUTOSERVICIO, MetodoPago.POINT): cls.AUTOSERVICIO_POINT,
            (Modalidad.AUTOSERVICIO, MetodoPago.MOSTRADOR): cls.AUTOSERVICIO_MOSTRADOR,
            (Modalidad.PERSONALIZADO, MetodoPago.MONEDAS): cls.PERSONALIZADO_MONEDAS,
            (Modalidad.PERSONALIZADO, MetodoPago.POINT): cls.PERSONALIZADO_POINT,
            (
                Modalidad.PERSONALIZADO,
                MetodoPago.MOSTRADOR,
            ): cls.PERSONALIZADO_MOSTRADOR,
        }
        return tabla[(base, metodo)]


class MetodoPago(str, Enum):
    MONEDAS = "monedas"
    POINT = "point"
    MOSTRADOR = "mostrador"


class EtapaKanban(str, Enum):
    RECIBIDO = "Recibido"
    ALISTANDO = "Alistando"
    LISTO_ENTREGA = "Listo para Entrega"


class TipoCalculo(str, Enum):
    FIJO = "fijo"
    POR_KG = "por_kg"
    POR_DURACION = "por_duracion"
