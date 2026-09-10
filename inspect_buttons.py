import requests
import json
import sys

base_url = "http://localhost:9377"
headers = {
    "Authorization": "Bearer my_secret_cookie_key",
    "Content-Type": "application/json"
}

# 1. Find the active tab ID
r = requests.get(f"{base_url}/tabs?userId=yt_playlist_agent_default", headers=headers)
tabs = r.json().get("tabs", [])
if not tabs:
    print("No active tabs found!")
    sys.exit(0)

tab_id = tabs[0]["tabId"]
print(f"Active tab ID: {tab_id}")

# 2. Get current URL and Title
expr_info = """
({
    title: document.title,
    url: window.location.href,
    htmlLength: document.documentElement.outerHTML.length
})
"""

payload_info = {
    "userId": "yt_playlist_agent_default",
    "expression": expr_info
}

er = requests.post(f"{base_url}/tabs/{tab_id}/evaluate", headers=headers, json=payload_info)
if er.status_code == 200:
    res = er.json().get("result", {})
    print(f"URL: {res.get('url')}")
    print(f"Title: {res.get('title')}")
    print(f"HTML Length: {res.get('htmlLength')}")
else:
    print(f"Info Evaluate failed: {er.status_code} {er.text}")

# 3. Evaluate script to find button elements
expr = """
(function() {
    let buttons = Array.from(document.querySelectorAll("button, [role='button'], yt-button-renderer"));
    return buttons.map(b => ({
        tagName: b.tagName,
        text: (b.innerText || b.textContent || "").trim().substring(0, 50),
        ariaLabel: b.getAttribute("aria-label")
    }));
})()
"""

payload = {
    "userId": "yt_playlist_agent_default",
    "expression": expr
}

er = requests.post(f"{base_url}/tabs/{tab_id}/evaluate", headers=headers, json=payload)
if er.status_code == 200:
    results = er.json().get("result", [])
    print(f"\nFound {len(results)} button elements:")
    for i, res in enumerate(results, 1):
        print(f"{i}. Tag: {res['tagName']}, Text: {repr(res['text'])}, AriaLabel: {repr(res['ariaLabel'])}")
else:
    print(f"Evaluate failed: {er.status_code} {er.text}")
