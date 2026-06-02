import requests
import json

try:
    resp = requests.get("http://127.0.0.1:8000/api/status")
    print("Status code:", resp.status_code)
    print("Response JSON:")
    print(json.dumps(resp.json(), indent=2))
except Exception as e:
    print("Error:", e)
