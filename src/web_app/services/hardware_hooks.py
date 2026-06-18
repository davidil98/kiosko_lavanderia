import hardware
from services.notifications import state


def on_moneda_ingresada(valor):
    if state.servicio_seleccionado and not state.exito:
        state.ingresar_dinero(valor)


lector_monedas = hardware.LectorMonedas(callback=on_moneda_ingresada)
