from gpiozero import Button
from signal import pause

# Configura el GPIO 17. 
# Por defecto, Button activa el PULL_UP interno y detecta la caída a GND (0V).
# bounce_time=0.05 actúa como filtro anti-rebote para ignorar fluctuaciones eléctricas falsas.
pin_prueba = Button(17, bounce_time=0.05)

def señal_detectada():
    print("⚡ ¡Pulso recibido! (El pin 17 tocó GND)")

def señal_liberada():
    print("🛑 Señal liberada (El pin 17 volvió a 3.3V)")

# Enlazamos los eventos del hardware a las funciones
pin_prueba.when_pressed = señal_detectada
pin_prueba.when_released = señal_liberada

print("=========================================")
print(" SIMULADOR DE PULSOS ACTIVO (gpiozero)")
print(" Haz un puente físico entre el GPIO 17 y GND para simular el pulso.")
print(" Presiona Ctrl+C para salir.")
print("=========================================\n")

try:
    # pause() mantiene el script vivo escuchando el hardware 
    # sin consumir recursos del procesador (cero bucles while)
    pause() 
except KeyboardInterrupt:
    print("\nCerrando test de forma segura...")