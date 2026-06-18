import requests
from dotenv import load_dotenv
import os

load_dotenv()
ACCESS_TOKEN = os.getenv("MP_TEST_TOKEN")

url = "https://api.mercadopago.com/terminals/v1/list"

payload={}
headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

response = requests.request("GET", url, headers=headers, data=payload)

print(response.text)
