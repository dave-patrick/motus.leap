import os
from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "user_data_playwright")

def test():
    print("Starting Playwright...")
    try:
        with sync_playwright() as p:
            print("Launching browser context...")
            context = p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=True,  # run headless for simple check
                args=[
                    "--window-size=1920,1080",
                    "--mute-audio"
                ]
            )
            page = context.new_page()
            print("Navigating to example.com...")
            page.goto("https://example.com")
            print(f"Title: {page.title()}")
            context.close()
            print("Success!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
