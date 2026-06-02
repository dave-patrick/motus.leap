import asyncio
import os
from playwright.async_api import async_playwright

async def test_sorting():
    async with async_playwright() as p:
        print("Launching browser...")
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("Navigating to http://127.0.0.1:8000/...")
        await page.goto("http://127.0.0.1:8000/")
        await page.wait_for_timeout(1000)
        
        print("Switching to Playlists tab...")
        await page.evaluate("switchTab('playlists')")
        
        print("Waiting for playlist cards...")
        await page.wait_for_selector(".playlist-card", timeout=10000)
        
        # Let's find the card that has the name "Football"
        cards = await page.query_selector_all(".playlist-card")
        football_card = None
        for card in cards:
            name_el = await card.query_selector(".playlist-name")
            if name_el:
                name = await name_el.inner_text()
                if "Football" in name:
                    football_card = card
                    break
        
        if not football_card:
            print("Football card not found, using the first card...")
            football_card = cards[0]
            
        playlist_name = await (await football_card.query_selector(".playlist-name")).inner_text()
        print(f"Clicking playlist card: {playlist_name}")
        await football_card.click()
        
        print("Waiting for video table to load...")
        await page.wait_for_selector(".video-row", timeout=10000)
        await page.wait_for_timeout(1000)
        
        # Helper to get current rows data
        async def get_table_data():
            rows = await page.query_selector_all(".video-row")
            data = []
            for r in rows:
                cells = await r.query_selector_all("td")
                # Cells are: Checkbox, Index (#), Title, Channel, Published, Action
                idx = await cells[1].inner_text()
                title = await (await cells[2].query_selector("a")).inner_text()
                channel = await cells[3].inner_text()
                published = await cells[4].inner_text()
                data.append({
                    "index": int(idx.strip()) if idx.strip().isdigit() else idx,
                    "title": title.strip(),
                    "channel": channel.strip(),
                    "published": published.strip()
                })
            return data

        # Get initial order
        initial_data = await get_table_data()
        print(f"Loaded {len(initial_data)} videos. First video: '{initial_data[0]['title']}', Published: '{initial_data[0]['published']}'")
        
        # 1. Test Title sorting (Ascending)
        print("Clicking 'Video Title' header to sort ascending...")
        await page.click("#th-title")
        await page.wait_for_timeout(500)
        asc_title_data = await get_table_data()
        
        # Verify sorted ascending
        titles_asc = [v['title'].lower() for v in asc_title_data]
        is_sorted_asc = titles_asc == sorted(titles_asc)
        print(f"  Title Ascending Sorted: {is_sorted_asc}")
        print(f"  First title: '{titles_asc[0]}', Last title: '{titles_asc[-1]}'")
        
        # 2. Test Title sorting (Descending)
        print("Clicking 'Video Title' header again to sort descending...")
        await page.click("#th-title")
        await page.wait_for_timeout(500)
        desc_title_data = await get_table_data()
        
        # Verify sorted descending
        titles_desc = [v['title'].lower() for v in desc_title_data]
        is_sorted_desc = titles_desc == sorted(titles_desc, reverse=True)
        print(f"  Title Descending Sorted: {is_sorted_desc}")
        print(f"  First title: '{titles_desc[0]}', Last title: '{titles_desc[-1]}'")
        
        # 3. Test Channel sorting (Ascending)
        print("Clicking 'Channel' header to sort ascending...")
        await page.click("#th-channel")
        await page.wait_for_timeout(500)
        asc_channel_data = await get_table_data()
        
        channels_asc = [v['channel'].lower() for v in asc_channel_data]
        is_channel_sorted_asc = channels_asc == sorted(channels_asc)
        print(f"  Channel Ascending Sorted: {is_channel_sorted_asc}")
        print(f"  First channel: '{channels_asc[0]}', Last channel: '{channels_asc[-1]}'")
        
        # 4. Test Published sorting (Ascending - newest/first rank)
        print("Clicking 'Published' header to sort...")
        await page.click("#th-published")
        await page.wait_for_timeout(500)
        published_data = await get_table_data()
        print(f"  First 3 published dates (sorted): {[v['published'] for v in published_data[:3]]}")
        print(f"  Last 3 published dates (sorted): {[v['published'] for v in published_data[-3:]]}")
        
        # 5. Test restoring Index order
        print("Clicking index column '#' header...")
        await page.click("#th-index")
        await page.wait_for_timeout(500)
        restored_data = await get_table_data()
        is_index_restored = [v['title'] for v in restored_data] == [v['title'] for v in initial_data]
        print(f"  Index Order Restored: {is_index_restored}")
        
        # Take a screenshot of the detail view for verification visual
        screenshot_path = os.path.join(os.getcwd(), "scratch", "test_sorting_output.png")
        print(f"Saving sorted detail view screenshot to {screenshot_path}...")
        await page.screenshot(path=screenshot_path, full_page=True)
        
        await browser.close()
        print("Test completed.")
        
        assert is_sorted_asc, "Title Ascending sort failed"
        assert is_sorted_desc, "Title Descending sort failed"
        assert is_channel_sorted_asc, "Channel Ascending sort failed"
        assert is_index_restored, "Index restoration failed"

if __name__ == "__main__":
    asyncio.run(test_sorting())
