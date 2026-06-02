import requests
import json
from dotenv import load_dotenv
import os

load_dotenv()
ACCESS_TOKEN = os.getenv("MP_TEST_TOKEN")

url = "https://api.mercadopago.com/terminals/v1/setup"

payload = json.dumps({
  "terminals": [
    {
      "id": "NEWLAND_N950__N950NCC904817363",
      "operating_mode": "PDV"
    }
  ]
})
headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    'Content-Type': 'application/json'
}

response = requests.request("PATCH", url, headers=headers, data=payload)

print(response.text)
