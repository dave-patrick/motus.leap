import urllib.request
import json

try:
    with urllib.request.urlopen("http://localhost:9377/health") as response:
        print("Status:", response.status)
        print("Body:", response.read().decode())
except Exception as e:
    print("Error:", e)
