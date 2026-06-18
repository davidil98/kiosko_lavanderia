import requests
import os
from dotenv import load_dotenv

load_dotenv()
ACCESS_TOKEN = os.getenv("MP_TEST_TOKEN")

def crear_caja_ecoluna():
    url = "https://api.mercadopago.com/pos"
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    ID_SUCURSAL_REAL = 83094574  
    
    payload = {
        "name": "Kiosko Principal Lavandería",
        # "fixed_amount": True,  # Puedes descomentar esto si la máquina siempre cobra lo mismo
        #"category": 621102, # Solo dos categorías posibles: 468419 (Gas station) o 581201 (Gastonomy). Documentation: 621102. Si no se especifica queda como general.
        "store_id": ID_SUCURSAL_REAL,
        "external_store_id": "ECOLUNA_LAVANDERIA_001",
        "external_id": "CAJA01"     # Tu propio identificador para esta Raspberry Pi
    }
    
    print("Creando la caja en los servidores de Mercado Pago...")
    # Recuerda usar json=payload para que requests haga la conversión automáticamente
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code in [200, 201]:
        datos_caja = response.json()
        print("\n¡Caja (POS) creada exitosamente!")
        # El ID de la caja es vital para el siguiente paso
        print(f"ID de la Caja a guardar: {datos_caja.get('id')}")
        print('-'*6,'\n',response.text,'\n','-'*6)
    else:
        print("\nError al crear la caja:")
        print(response.text)

if __name__ == "__main__":
    crear_caja_ecoluna()