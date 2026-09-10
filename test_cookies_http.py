import json
import requests
import sys
import re

cookies_path = '/home/ubuntu/.camofox/cookies/cookies.json'
try:
    with open(cookies_path) as f:
        cookies = json.load(f)
except Exception as e:
    print(f"Error reading cookies: {e}")
    sys.exit(1)

# Convert to requests cookie jar
jar = requests.cookies.RequestsCookieJar()
for c in cookies:
    domain = c['domain']
    jar.set(c['name'], c['value'], domain=domain, path=c.get('path', '/'))

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
    'Accept-Language': 'en-US,en;q=0.9',
}

print("Testing cookies against Watch Later...")
r = requests.get('https://www.youtube.com/playlist?list=WL', cookies=jar, headers=headers, timeout=15)
print("Final URL:", r.url)
print("Redirect History:", [res.url for res in r.history])
print("HTTP Status Code:", r.status_code)

title_match = re.search(r'<title>(.*?)</title>', r.text, re.IGNORECASE)
title = title_match.group(1) if title_match else 'None'
print("Page Title:", title.strip())

# Check for presence of some common texts
print("Contains 'Sign in'?", "Sign in" in r.text)
print("Contains 'The playlist does not exist'?", "The playlist does not exist" in r.text)

clean_text = ' '.join(r.text.split())
print("\nPage text snippet (first 500 chars):")
print(clean_text[:500])
