import RPi.GPIO as GPIO
from pynput import keyboard

# --- CONFIGURACIÓN ---
PIN_OPTO = 17 
tecla_mantenida = False

def inicializar_gpio():
    # Usamos la numeración BCM estándar y configuramos como SALIDA
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN_OPTO, GPIO.OUT)
    
    # Nos aseguramos de que el pin inicie apagado (0V) por seguridad
    GPIO.output(PIN_OPTO, GPIO.LOW)

def al_presionar(tecla):
    global tecla_mantenida
    if tecla == keyboard.Key.space and not tecla_mantenida:
        tecla_mantenida = True
        print("🚀 [Pulso mandado] Inyectando 3.3V al optoacoplador...")
        
        # Encendemos el pin (3.3V)
        GPIO.output(PIN_OPTO, GPIO.HIGH)

def al_soltar(tecla):
    global tecla_mantenida
    if tecla == keyboard.Key.space:
        tecla_mantenida = False
        
        # Apagamos el pin (0V)
        GPIO.output(PIN_OPTO, GPIO.LOW)
        print("🛑 Pulso liberado. La lavadora debió registrar el inicio.\n")
        
    elif tecla == keyboard.Key.esc:
        print("\nSaliendo del test de la lavadora...")
        return False # Rompe el listener de pynput

if __name__ == "__main__":
    inicializar_gpio()
    
    print("=========================================")
    print(" CONTROL REMOTO (RPi.GPIO + TECLADO)")
    print(" Mantén presionado ESPACIO para hacer 'clic'.")
    print(" Presiona ESC para salir.")
    print("=========================================\n")
    
    try:
        # El Listener captura el teclado en segundo plano
        with keyboard.Listener(on_press=al_presionar, on_release=al_soltar) as listener:
            listener.join()
    finally:
        # Al presionar ESC o interrumpir el script, se limpian los pines
        GPIO.cleanup()
        print("Pines GPIO limpiados y seguros.")
