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

    context.clear_cookies()
    context.add_cookies(pw_cookies)
    print("Cookies injected.")

    print("Navigating to Watch Video Page...")
    t0 = time.time()
    try:
        page.goto("https://www.youtube.com/watch?v=OIohIrmzzXw", wait_until="domcontentloaded", timeout=60000)
        print(f"Goto finished in {time.time() - t0:.2f}s")
    except Exception as e:
        print(f"Goto failed: {e}")
        try:
            print("Retrying with commit...")
            page.goto("https://www.youtube.com/watch?v=OIohIrmzzXw", wait_until="commit", timeout=30000)
            print("Retry goto finished.")
        except Exception as e2:
            print(f"Retry failed: {e2}")

    print("Waiting 10s...")
    time.sleep(10)

    print("Title:", page.title())
    print("Saving screenshot to /home/ubuntu/motus.leap/test_watch_page.png...")
    page.screenshot(path="/home/ubuntu/motus.leap/test_watch_page.png")
    print("Done!")

finally:
    driver.quit()
