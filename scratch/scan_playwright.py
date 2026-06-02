import json
import os
import asyncio
from playwright.async_api import async_playwright

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "user_data_playwright")

async def scan_playlist(context, url):
    page = await context.new_page()
    try:
        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(2)
        
        # Scroll to load all videos
        last_count = 0
        consecutive_same = 0
        while True:
            await page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
            await asyncio.sleep(3)
            
            # Count videos
            videos = await page.query_selector_all("ytd-playlist-video-renderer")
            count = len(videos)
            print(f"  Found {count} videos...")
            
            if count == last_count:
                consecutive_same += 1
                if consecutive_same >= 3:
                    break
            else:
                last_count = count
                consecutive_same = 0
            
            if count > 2000:
                break
                
        # Extract data
        results = []
        video_els = await page.query_selector_all("ytd-playlist-video-renderer")
        for v in video_els:
            try:
                title_el = await v.query_selector("#video-title")
                title = await title_el.inner_text()
                href = await title_el.get_attribute("href")
                url = "https://www.youtube.com" + href.split("&list=")[0] if href else ""
                
                channel = ""
                channel_el = await v.query_selector("ytd-channel-name a, #byline a, #text-container.ytd-channel-name")
                if channel_el:
                    channel = await channel_el.inner_text()
                
                results.append({"title": title.strip(), "url": url, "channel": channel.strip()})
            except:
                continue
        return results
    finally:
        await page.close()

async def main():
    if not os.path.exists("playlists_urls.json"):
        print("Run browser subagent to get URLs first.")
        return

    with open("playlists_urls.json", "r", encoding="utf-8") as f:
        playlists_to_scan = json.load(f)

    report = []
    if os.path.exists("playlists_report.json"):
        with open("playlists_report.json", "r", encoding="utf-8") as f:
            report = json.load(f)
            
    scanned_names = {p["name"] for p in report if p.get("video_count", 0) > 0}

    async with async_playwright() as p:
        # Note: Playwright might need a fresh login if not using the SAME profile as UC
        # But for now I'll just try to scan public info
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=True
        )
        
        for p_data in playlists_to_scan:
            if p_data["name"] in scanned_names:
                print(f"Skipping {p_data['name']}")
                continue
                
            print(f"Scanning {p_data['name']}...")
            try:
                videos = await scan_playlist(browser, p_data["url"])
                p_data["videos"] = videos
                p_data["video_count"] = len(videos)
                report.append(p_data)
                
                # Save incrementally
                with open("playlists_report.json", "w", encoding="utf-8") as f:
                    json.dump(report, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Error: {e}")
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
