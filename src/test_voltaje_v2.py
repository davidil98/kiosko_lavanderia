from gpiozero import Button
from time import time, sleep

# Al usar "Button", gpiozero configura automáticamente el pin 17 
# con PULL_UP interno y lo conecta a eventos de hardware.
# bounce_time=0.05 ignora pulsos falsos menores a 50ms.
PIN_MONEDERO = 17
monedero = Button(PIN_MONEDERO, bounce_time=0.05)

class LectorMonedas:
    def __init__(self):
        self.pulsos = 0
        self.ultimo_tiempo = 0
        self.diccionario_monedas = {2: 1, 4: 2, 6: 5, 8: 10} # {Pulsos: Pesos}
        
        # Enlazamos el evento fisico a nuestra funcion
        monedero.when_pressed = self.registrar_pulso

    def registrar_pulso(self):
        self.pulsos += 1
        self.ultimo_tiempo = time()
        print(f"Pulso detectado. Total temporal: {self.pulsos}")

    def procesar_ventana_tiempo(self):
        # Esta función revisa si ya pasó el tiempo de espera (ej. 0.4 segundos)
        # desde el último pulso registrado.
        if self.pulsos > 0 and (time() - self.ultimo_tiempo) > 0.4:
            if self.pulsos in self.diccionario_monedas:
                valor = self.diccionario_monedas[self.pulsos]
                print(f"✅ Moneda validada: ${valor} pesos")
            else:
                print(f"❌ Error de lectura (Pulsos: {self.pulsos})")
            
            # Reiniciamos para la siguiente moneda
            self.pulsos = 0

# Prueba del sistema
lector = LectorMonedas()
print("Kiosko listo. Inserta monedas...")

try:
    while True:
        # Aquí el bucle principal solo se encarga de revisar el timer
        lector.procesar_ventana_tiempo()
        sleep(0.1) # Un sleep pequeño aquí no afecta, porque los pulsos se guardan en 2do plano
        
except KeyboardInterrupt:
    print("\nCerrando sistema...")
