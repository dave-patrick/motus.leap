import json
import time

with open('/home/ubuntu/.camofox/cookies/cookies.json') as f:
    cookies = json.load(f)

now = time.time()
print(f"Total cookies: {len(cookies)}")
for c in cookies:
    exp = c.get('expires', 0)
    if exp > 0:
        diff = f"{exp - now:.1f}s"
    else:
        diff = "no expiry"
    print(f"Name: {c['name']}, Domain: {c['domain']}, Expires: {exp} ({diff})")
