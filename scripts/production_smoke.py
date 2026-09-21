"""Small post-deploy smoke check for Render or local production URLs."""
import json
import sys
from urllib.request import Request, urlopen

base = (sys.argv[1] if len(sys.argv) > 1 else "https://tubemanager.onrender.com").rstrip("/")
for path in ("/health", "/live", "/ready"):
    with urlopen(Request(base + path, headers={"User-Agent": "motus-smoke/1"}), timeout=20) as response:
        body = response.read().decode("utf-8")
        if response.status != 200:
            raise SystemExit(f"{path}: HTTP {response.status}")
        try:
            json.loads(body)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}: invalid JSON: {exc}")
        print(f"{path}: ok")
