import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("Navigating to dashboard...")
        await page.goto("http://127.0.0.1:8000/")
        await page.wait_for_timeout(2000)
        
        # Switch to Playlists tab
        print("Switching to Playlists tab...")
        await page.evaluate("switchTab('playlists')")
        
        # Click on the first playlist card
        # Wait for the playlists grid cards to load
        print("Waiting for playlist cards...")
        await page.wait_for_selector(".playlist-card", timeout=10000)
        
        # Click first playlist card
        print("Clicking first playlist card...")
        await page.click(".playlist-card:first-child")
        
        # Wait for video table to load
        print("Waiting for video table to load...")
        await page.wait_for_selector(".video-row")
        await page.wait_for_timeout(1000)
        
        # Capture screenshot
        screenshot_path = os.path.join(os.getcwd(), "scratch", "dashboard_playlist_detail.png")
        print(f"Saving screenshot to {screenshot_path}...")
        await page.screenshot(path=screenshot_path, full_page=True)
        
        await browser.close()
        print("Verification complete.")

if __name__ == "__main__":
    asyncio.run(main())
