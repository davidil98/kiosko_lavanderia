import requests
import os
import uuid
from dotenv import load_dotenv

load_dotenv()
ACCESS_TOKEN = os.getenv("MP_TEST_TOKEN")

def enviar_orden_cobro():
    url = "https://api.mercadopago.com/v1/orders"
    
    # IMPORTANTE: Reemplaza esto con el ID real de tu terminal Point Smart
    ID_TERMINAL_REAL = "NEWLAND_N950__N950NCC904817363" 
    
    # Generamos una llave de idempotencia aleatoria y única para este cobro
    llave_idempotencia = str(uuid.uuid4())
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": llave_idempotencia
    }
    
    payload = {
        "type": "point",
        # Generamos una referencia externa única para rastrear este cobro en EcoLuna
        "external_reference": f"ECOLUNA_{llave_idempotencia[:8]}", 
        "expiration_time": "PT3M", # La orden expira en 3 minutos si no se paga
        "transactions": {
            "payments": [
                {
                    "amount": "35.00" # El costo del ciclo de lavado
                }
            ]
        },
        "config": {
            "point": {
                "terminal_id": ID_TERMINAL_REAL,
                "print_on_terminal": "no_ticket" # no_ticket ahorra papel, o usa seller_ticket
            },
            "payment_method": {
                "default_type": "credit_card"
            }
        },
        "description": "Ciclo de Lavado EcoLuna"
    }
    
    print(f"Enviando cobro de $35.00 a la terminal {ID_TERMINAL_REAL}...")
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code in [200, 201]:
        datos_orden = response.json()
        print("\n✅ ¡Orden enviada con éxito!")
        print("La terminal debería estar encendida pidiendo la tarjeta.")
        # ESTE ID ES CRUCIAL PARA REVISAR EL ESTADO DEL PAGO
        print(f"ID de la Orden (Guárdalo para verificar): {datos_orden.get('id')}") 
    else:
        print("\n❌ Error al crear la orden:")
        print(response.text)

if __name__ == "__main__":
    enviar_orden_cobro()