from gpiozero import OutputDevice, Button
from pynput import keyboard
import time

# --- CONFIGURACIÓN DE PINES ---
# GPIO 18: Será la "boca" que manda el voltaje al relé
pin_salida = OutputDevice(18) 

# GPIO 17: Será el "oído" que detecta si el relé realmente cerró el circuito
# pull_up=True pone el pin en 3.3V esperando que el relé lo mande a GND
pin_entrada = Button(17, pull_up=True, bounce_time=0.05) 

# Variable de control
tecla_mantenida = False

def al_presionar(tecla):
    global tecla_mantenida
    if tecla == keyboard.Key.space and not tecla_mantenida:
        tecla_mantenida = True
        print("🚀 [Pulso mandado] Activando relé...")
        
        # 1. Mandamos el pulso
        pin_salida.on()
        
        # 2. Damos un margen de 100 milisegundos para que la mecánica del relé haga "clic"
        time.sleep(0.1) 
        
        # 3. Verificamos si la señal regresó por el pin 17
        if pin_entrada.is_pressed:
            print("  ✅ [Señal detectada] El relé cerró el circuito exitosamente.")
        else:
            print("  ❌ [Señal no detectada] El pulso se envió, pero no regresó. Revisa los cables.")

def al_soltar(tecla):
    global tecla_mantenida
    if tecla == keyboard.Key.space:
        tecla_mantenida = False
        pin_salida.off() # Apagamos el relé
        print("🛑 Pulso liberado.\n")
        
    elif tecla == keyboard.Key.esc:
        print("\nSaliendo del test...")
        return False # Esto rompe el listener y termina el script

print("=========================================")
print(" TEST DE BUCLE CERRADO (LOOPBACK)")
print(" Presiona ESPACIO para mandar pulso y verificar.")
print(" Presiona ESC para salir.")
print("=========================================\n")

# El Listener del teclado mantiene el script vivo por sí solo, 
# ya no necesitamos usar pause() ni bucles while.
with keyboard.Listener(on_press=al_presionar, on_release=al_soltar) as listener:
    listener.join()