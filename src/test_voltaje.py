import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)

try:
    while True:
        estado = GPIO.input(17)
        print(f"Señal: {estado}")
        time.sleep(0.5)
except KeyboardInterrupt:
    GPIO.cleanup()
