import os
import sys
import json
import time

sys.path.insert(0, '/home/ubuntu/motus.leap')
from core.actions import get_playwright_browser

COOKIES_PATH = "/home/ubuntu/.camofox/cookies/cookies.json"

if not os.path.exists(COOKIES_PATH):
    print("No cookies.json found!")
    sys.exit(1)

with open(COOKIES_PATH) as f:
    cookies = json.load(f)

print("Starting Playwright...")
os.environ["DISPLAY"] = ":1"
driver = get_playwright_browser()
if not driver:
    print("Failed to initialize Playwright!")
    sys.exit(1)

try:
    context = driver.context
    page = driver.page

    # Print cookies in context before injection
    print("Cookies in context before:", len(context.cookies()))
    for c in context.cookies():
        val_snippet = c['value'][:10] + "..." if len(c['value']) > 10 else c['value']
        print(f"  Before - Cookie: {c['name']} for {c['domain']} (value: {val_snippet})")

    # Playwright add_cookies expects specific fields. Let's sanitize them.
    pw_cookies = []
    for c in cookies:
        clean = {
            "name": c["name"],
            "value": c["value"],
            "domain": c["domain"],
            "path": c.get("path", "/"),
        }
        if "secure" in c: clean["secure"] = c["secure"]
        if "httpOnly" in c: clean["httpOnly"] = c["httpOnly"]
        clean["sameSite"] = "Lax"
        if "expires" in c and c["expires"] > 0:
            clean["expires"] = int(c["expires"])
        
        pw_cookies.append(clean)

    print(f"Injecting {len(pw_cookies)} cookies...")
    try:
        context.add_cookies(pw_cookies)
    except Exception as ie:
        print(f"Injection error: {ie}")

    print("Cookies in context after:", len(context.cookies()))
    for c in context.cookies():
        val_snippet = c['value'][:10] + "..." if len(c['value']) > 10 else c['value']
        print(f"  After - Cookie: {c['name']} for {c['domain']} (value: {val_snippet})")

    def log_request(request):
        if "playlist?list=WL" in request.url:
            print("\n--- Request Sent to YouTube ---")
            print("Request URL:", request.url)
            # Filter cookies to print
            headers = request.headers
            print("Request Cookie Header:", headers.get("cookie") or headers.get("Cookie") or "NONE")
            print("Request User-Agent:", headers.get("user-agent") or headers.get("User-Agent") or "NONE")
            try:
                print("Context cookies matching url:", context.cookies(request.url))
            except Exception as ce:
                print("Error getting context cookies for url:", ce)
            print("-------------------------------\n")
    page.on("request", log_request)

    print("Navigating to Watch Later...")
    page.goto("https://www.youtube.com/playlist?list=WL", wait_until="domcontentloaded", timeout=60000)
    print("Waiting 10s...")
    time.sleep(10)

    print("Title:", page.title())
    text = page.locator("body").inner_text()[:400]
    print("Page text snippet:\n", text)

    page.screenshot(path="/home/ubuntu/motus.leap/youtube_pw_debug.png")
    print("Screenshot saved to /home/ubuntu/motus.leap/youtube_pw_debug.png")

finally:
    driver.quit()
