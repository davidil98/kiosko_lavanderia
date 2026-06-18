import requests
import os
from dotenv import load_dotenv

load_dotenv()
ACCESS_TOKEN = os.getenv("MP_TEST_TOKEN") # Reemplazar por access token de producción en su momento
USER_ID = os.getenv("MP_TEST_USER") # Reemplazar por user_id de producción en su momento

def obtener_user_id():
    """Hace una petición rápida para saber el ID de la cuenta propietaria del token."""
    url = "https://api.mercadopago.com/users/me"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    
    respuesta = requests.get(url, headers=headers)
    if respuesta.status_code == 200:
        return respuesta.json().get("id")
    else:
        print("\nError al obtener el USER_ID:", respuesta.text)
        return None

def crear_sucursal_ecoluna():
    """Crea la sucursal física en la base de datos de Mercado Pago."""
    user_id = obtener_user_id()
    if not user_id:
        return # Si falló el paso anterior, detenemos el script
        
    url = f"https://api.mercadopago.com/users/{user_id}/stores"
    
    # Aquí solucionamos el error de Postman inyectando el Authorization
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # El diccionario ya estructurado en Python (requests convierte esto a JSON automáticamente)
    payload = {
        "name": "EcoLuna Lavandería",
        "business_hours": {
            "monday": [{"open": "08:00", "close": "20:00"}],
            "tuesday": [{"open": "08:00", "close": "20:00"}],
            "wednesday": [{"open": "08:00", "close": "20:00"}],
            "thursday": [{"open": "08:00", "close": "20:00"}],
            "friday": [{"open": "08:00", "close": "20:00"}],
            "saturday": [{"open": "09:00", "close": "18:00"}],
            "sunday": [{"open": "09:00", "close": "15:00"}]
        },
        "external_id": "ECOLUNA_LAVANDERIA_001",
        #Cabo Catoche 229, Lomas del Poniente 2do Sector, 66369 Cdad. Santa Catarina, N.L.
        "location": {
            "street_number": "229", 
            "street_name": "Cabo Catoche", 
            "city_name": "Santa Catarina",
            "state_name": "Nuevo León",
            "latitude": 25.7049, 
            "longitude": -100.4538,
            "reference": "Local de Lavandería"
        }
    }
    
    print("Enviando petición a Mercado Pago...")
    # Usamos json=payload en lugar de data=payload para evitar usar la librería 'json' externa
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code in [200, 201]:
        datos_sucursal = response.json()
        print("\n¡Sucursal creada exitosamente!")
        print(f"ID de Sucursal (Guárdalo): {datos_sucursal.get('id')}")
        print(f"Nombre: {datos_sucursal.get('name')}")
    else:
        print("\nError al crear la sucursal:")
        print(response.text)

if __name__ == "__main__":
    crear_sucursal_ecoluna()