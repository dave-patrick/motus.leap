import json
import os
import asyncio
from playwright.async_api import async_playwright

# Use the primary user data dir where the login session is stored
USER_DATA_DIR = os.path.abspath(os.path.join(os.getcwd(), "user_data"))

async def handle_video(page, action):
    vid = action['vid']
    target_playlist = action.get('to')
    remove_playlists = action.get('from', [])
    if action.get('type') in ['DUPLICATE', 'DUPLICATE_NO_TARGET']:
        remove_playlists = action.get('remove', [])
        target_playlist = None

    url = f"https://www.youtube.com/watch?v={vid}"
    print(f"  URL: {url}")
    
    try:
        # Increase timeout and use wait_until="load" for stability
        await page.goto(url, wait_until="load", timeout=60000)
    except Exception as e:
        print(f"    Warning: Page load timed out or errored: {e}. Continuing anyway.")
    
    # Mute and pause video
    await page.evaluate("""
        Array.from(document.querySelectorAll('video, audio')).forEach(m => { 
            m.muted = true; 
            m.pause(); 
            m.volume = 0;
        });
    """)
    await asyncio.sleep(2)

    # Find Save button
    save_btn_selectors = [
        "button[aria-label='Save to playlist']",
        "ytd-button-renderer:has-text('Save')",
        "button:has-text('Save')",
        "ytd-watch-metadata #actions button:has(path[d*='M18 4v13.22'])"
    ]
    
    save_btn = None
    for sel in save_btn_selectors:
        try:
            save_btn = await page.wait_for_selector(sel, timeout=5000)
            if save_btn: break
        except: continue
        
    if not save_btn:
        print("    'Save' button not visible. Trying 'More actions' menu...")
        more_btn = await page.query_selector("button[aria-label='More actions']")
        if more_btn:
            await more_btn.click()
            await asyncio.sleep(1)
            save_btn = await page.query_selector("ytd-menu-service-item-renderer:has-text('Save')")

    if not save_btn:
        print("    ERROR: Could not find Save button.")
        await page.screenshot(path=f"debug_save_fail_{vid}.png")
        return

    # Scroll into view and click
    await save_btn.scroll_into_view_if_needed()
    await save_btn.click()
    await asyncio.sleep(3) # Wait longer for dialog

    # Wait for dialog
    dialog_selector = "yt-sheet-view-model, ytd-add-to-playlist-create-renderer, #playlists"
    try:
        await page.wait_for_selector(dialog_selector, timeout=10000)
    except:
        print("    ERROR: 'Save to...' dialog did not appear.")
        await page.screenshot(path=f"debug_dialog_fail_{vid}.png")
        return

    # Determine actions
    to_check = [target_playlist] if target_playlist else []
    to_uncheck = [p for p in remove_playlists if p != target_playlist]

    # Scrollable container
    scroll_selector = "yt-sheet-view-model #content, ytd-add-to-playlist-create-renderer #playlists, #content-icon-view-model"
    scroll_el = await page.query_selector(scroll_selector)
    
    for _ in range(30): # More scrolls for 69 playlists
        items = await page.query_selector_all('yt-list-item-view-model, ytd-playlist-add-to-option-renderer, toggleable-list-item-view-model')
        
        for item in items:
            title_el = await item.query_selector('.ytListItemViewModelTitle, #label, .ytListItemViewModelTitleWrapper, span.ytListItemViewModelTitle')
            if not title_el: continue
            
            title = (await title_el.inner_text()).strip()
            if not title: continue
            
            is_checked = False
            btn = await item.query_selector("button")
            if btn:
                val = await btn.get_attribute("aria-checked")
                is_checked = (val == "true")
            else:
                val = await item.get_attribute("aria-checked") or await item.get_attribute("aria-selected")
                is_checked = (val == "true")

            if title in to_check:
                if not is_checked:
                    print(f"    -> Checking '{title}'")
                    await item.click()
                    await asyncio.sleep(1)
                else:
                    print(f"    -> '{title}' already checked.")
                to_check.remove(title)
                
            elif title in to_uncheck:
                if is_checked:
                    print(f"    -> Unchecking '{title}'")
                    await item.click()
                    await asyncio.sleep(1)
                else:
                    print(f"    -> '{title}' already unchecked.")
                to_uncheck.remove(title)

        if not to_check and not to_uncheck:
            break
            
        if scroll_el:
            await scroll_el.hover()
            await page.mouse.wheel(0, 600)
        else:
            await page.keyboard.press("PageDown")
        await asyncio.sleep(1)

    if to_check:
        print(f"    WARNING: Could not find: {to_check}")
    if to_uncheck:
        print(f"    WARNING: Could not find to uncheck: {to_uncheck}")

    await page.keyboard.press("Escape")
    await asyncio.sleep(1)

async def main():
    import sys
    filename = sys.argv[1] if len(sys.argv) > 1 else 'wl_priority_actions.json'
    
    if not os.path.exists(filename):
        print(f"File {filename} not found.")
        return

    with open(filename, 'r', encoding='utf-8') as f:
        actions = json.load(f)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=True,
            viewport={'width': 1280, 'height': 1024}, # Larger height
            args=["--mute-audio"]
        )
        page = await context.new_page()

        count = 0
        for a in actions:
            count += 1
            print(f"[{count}/{len(actions)}] {a['title']}")
            try:
                await handle_video(page, a)
            except Exception as e:
                print(f"  Error: {e}")
                
        await context.close()

if __name__ == "__main__":
    asyncio.run(main())
