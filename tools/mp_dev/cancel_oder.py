import requests
from dotenv import load_dotenv
import os

load_dotenv()
ACCESS_TOKEN = os.getenv("MP_TEST_TOKEN")

url = "https://api.mercadopago.com/v1/orders/:orderId/cancel"

payload={}
headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
    'X-Idempotency-Key': 'Idempotency_Value'
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.text)
