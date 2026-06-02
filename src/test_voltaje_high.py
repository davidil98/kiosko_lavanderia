import RPi.GPIO as GPIO
import time

# Usaremos el GPIO 17 (Asegúrate de tener la resistencia de 220/330 ohms conectada)
PIN_OPTO = 17 

GPIO.setmode(GPIO.BCM)

# 1. EL CAMBIO VITAL: Lo configuramos como SALIDA (OUT), no como Entrada (IN)
GPIO.setup(PIN_OPTO, GPIO.OUT)

try:
    while True:
        print("Enviando orden a la lavadora...")
        
        # Mandamos 3.3V "fuertes" al optoacoplador (Enciende el LED interno)
        GPIO.output(PIN_OPTO, GPIO.HIGH) 
        
        # Mantenemos el "dedo" en el botón por medio segundo
        time.sleep(0.1) 
        
        # Cortamos el voltaje (Apaga el LED interno)
        GPIO.output(PIN_OPTO, GPIO.LOW) 
        
        print("¡Pulso completado!")

except KeyboardInterrupt:
    GPIO.cleanup()