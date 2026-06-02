from gpiozero import OutputDevice
from pynput import keyboard
import time

# --- CONFIGURACIÓN DEL PIN ---
# Al usar OutputDevice, gpiozero automáticamente hace el "GPIO.setup(OUT)"
# y lo mantiene en 0V (apagado) hasta que le des la orden de encender.
pin_optoacoplador = OutputDevice(17) 

# Variable de control para evitar repeticiones si dejas la tecla pegada
tecla_mantenida = False

def al_presionar(tecla):
    global tecla_mantenida
    if tecla == keyboard.Key.space and not tecla_mantenida:
        tecla_mantenida = True
        print("🚀 [Pulso mandado] Inyectando 3.3V al optoacoplador...")
        
        # Esto manda el amperaje necesario para encender el LED interno
        pin_optoacoplador.on() 

def al_soltar(tecla):
    global tecla_mantenida
    if tecla == keyboard.Key.space:
        tecla_mantenida = False
        
        # Corta el voltaje a 0V, apagando el LED interno
        pin_optoacoplador.off() 
        print("🛑 Pulso liberado. La lavadora debió registrar el inicio.\n")
        
    elif tecla == keyboard.Key.esc:
        print("\nSaliendo del test de la lavadora...")
        return False # Rompe el listener y termina el script

print("=========================================")
print(" CONTROL REMOTO DE LAVADORA (OPTOACOPLADOR)")
print(" Mantén presionado ESPACIO para hacer 'clic' en la máquina.")
print(" Presiona ESC para salir.")
print("=========================================\n")

# El Listener del teclado mantiene el script vivo sin consumir CPU
with keyboard.Listener(on_press=al_presionar, on_release=al_soltar) as listener:
    listener.join()