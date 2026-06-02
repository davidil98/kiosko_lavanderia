import RPi.GPIO as GPIO
import time

PIN_OPTO = 17

# 0.5 segundos simula perfectamente la pulsación de un dedo humano
TIEMPO_PULSO = 0.5 

def enviar_pulso_lavadora():
    # Configuramos la placa
    GPIO.setmode(GPIO.BCM)
    
    # Al declarar initial=GPIO.LOW, nos aseguramos de que el pin 
    # nazca apagado (0V) desde el milisegundo cero para evitar disparos en falso.
    GPIO.setup(PIN_OPTO, GPIO.OUT, initial=GPIO.LOW)

    try:
        print(f"🚀 Iniciando pulso (Enviando 3.3V al optoacoplador por {TIEMPO_PULSO}s)...")
        
        # 1. ENCENDEMOS (El optoacoplador cierra el circuito de la lavadora)
        GPIO.output(PIN_OPTO, GPIO.HIGH)
        
        # 2. ESPERAMOS (Mantenemos el voltaje el tiempo exacto)
        # time.sleep() congela el script aquí de forma precisa
        time.sleep(TIEMPO_PULSO)
        
        # 3. APAGAMOS (El optoacoplador abre el circuito)
        GPIO.output(PIN_OPTO, GPIO.LOW)
        
        print("🛑 Fin de pulso. La señal se envió correctamente.")
        
    finally:
        # Limpiamos los pines para devolver la Raspberry Pi a un estado seguro
        GPIO.cleanup()

if __name__ == "__main__":
    enviar_pulso_lavadora()

