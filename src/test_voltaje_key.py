from gpiozero import OutputDevice, InputDevice
from pynput import keyboard

PIN_RELE = 18
PIN_LECTURA = 23

rele = OutputDevice(PIN_RELE)
# Configuramos el pin 23 para escuchar, con pull_down para que lea 0V por defecto
sensor_cierre = InputDevice(PIN_LECTURA, pull_up=False) 

print("Test de relé con Loopback iniciado...")

tecla_mantenida = False

def al_presionar(tecla):
    global tecla_mantenida
    if tecla == keyboard.Key.space and not tecla_mantenida:
        rele.on()
        # En cuanto encendemos el relé, le preguntamos al sensor si el voltaje logró pasar
        if sensor_cierre.is_active:
            print("⚡ [ÉXITO] Relé activado Y circuito cerrado verificado físicamente.")
        else:
            print(" [FALLA] El relé tiene señal, pero el circuito NO cerró.")
        tecla_mantenida = True
        
    elif tecla == keyboard.Key.esc:
        return False

def al_soltar(tecla):
    global tecla_mantenida
    if tecla == keyboard.Key.space:
        rele.off()
        print("[Señal Detenida] Relé apagado.")
        tecla_mantenida = False

with keyboard.Listener(on_press=al_presionar, on_release=al_soltar) as listener:
    listener.join()