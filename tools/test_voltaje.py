import RPi.GPIO as GPIO
import time

# CONECTAR DE PIN 11 (GPIO 17) A CUALQUIERO PIN GND
GPIO.setmode(GPIO.BCM)
GPIO.setup(21, GPIO.IN, pull_up_down=GPIO.PUD_UP)

try:
    while True:
        estado = GPIO.input(21)
        print(f"Señal: {estado}")
        time.sleep(0.5)
except KeyboardInterrupt:
    GPIO.cleanup()
