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

    print("Injected cookies count:", len(cookies))

    print("Navigating to Watch Later...")
    t0 = time.time()
    try:
        page.goto("https://www.youtube.com/playlist?list=WL", wait_until="domcontentloaded", timeout=60000)
        print(f"Goto finished in {time.time() - t0:.2f}s")
    except Exception as e:
        print(f"Goto failed: {e}")
        try:
            print("Retrying with commit...")
            page.goto("https://www.youtube.com/playlist?list=WL", wait_until="commit", timeout=30000)
            print("Retry goto finished.")
        except Exception as e2:
            print(f"Retry failed: {e2}")

    print("Waiting 10s for settle...")
    time.sleep(10)

    print("Title:", page.title())
    print("URL:", page.url)

    # Print active cookies on youtube.com domain
    active_cookies = context.cookies()
    print("Number of active cookies in browser context:", len(active_cookies))
    for c in active_cookies:
        if "youtube" in c["domain"]:
            print(f"  Cookie: {c['name']} (domain: {c['domain']}, path: {c['path']}, secure: {c['secure']}, expires: {c.get('expires')})")

    # Save screenshot
    screenshot_path = "/home/ubuntu/motus.leap/youtube_pw_debug_new.png"
    print(f"Saving screenshot to {screenshot_path}...")
    page.screenshot(path=screenshot_path)
    print("Done!")

finally:
    driver.quit()
