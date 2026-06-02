import RPi.GPIO as GPIO
from time import time, sleep

PIN_OPTO = 17
GPIO.setmode(GPIO.BCM)

time_on = 0.1
time_off = 0.1

try:
    if time() >= 0 and time() < time_on:
        print('Inicio de pulso')
        GPIO.setup(PIN_OPTO, GPIO.OUT)
    elif time() >= time_on and time() < time_on + time_off:
        print('Fin de pulso')
    GPIO.setup(PIN_OPTO, GPIO.IN)
finally:
    GPIO.cleanup()

