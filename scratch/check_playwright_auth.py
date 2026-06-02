import asyncio
from playwright.async_api import async_playwright
import os

USER_DATA_DIR = os.path.join(os.getcwd(), "user_data_playwright")

async def check_login():
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False # Open it so the user can see
        )
        page = await context.new_page()
        await page.goto("https://www.youtube.com/")
        print("Please check if you are logged in. If not, please log in now.")
        print("I will wait 60 seconds...")
        await asyncio.sleep(60)
        await context.close()

if __name__ == "__main__":
    asyncio.run(check_login())
