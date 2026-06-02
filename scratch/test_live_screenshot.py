import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium.webdriver.common.by import By
from core import get_browser

def main():
    driver = get_browser()
    try:
        url = "https://www.youtube.com/playlist?list=PL7y0zeb_CORI0zA5y78PAJBHAeMjEzLqk"
        print(f"Loading URL: {url}")
        driver.get(url)
        time.sleep(5)
        
        # Capture initial screenshot
        os.makedirs("scratch", exist_ok=True)
        driver.save_screenshot("scratch/live_playlist.png")
        print("Initial screenshot saved to scratch/live_playlist.png")
        
        # Check initial videos
        videos = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
        print(f"Initial videos count: {len(videos)}")
        
        # Look for dialogs / consent walls / overlay elements
        overlays = driver.find_elements(By.CSS_SELECTOR, "tp-yt-paper-dialog, yt-cookie-consent-dialog, #consent-bump, .consent-bump, #dialog")
        print(f"Found {len(overlays)} potential overlay/dialog elements.")
        for idx, o in enumerate(overlays):
            print(f"Overlay {idx+1}: tag={o.tag_name}, id={o.get_attribute('id')}, class={o.get_attribute('class')}, displayed={o.is_displayed()}")
            if o.is_displayed():
                print(f"Content: {o.text[:200]}")
        
        # Let's check for any ytd-continuation-item-renderer elements
        conts = driver.find_elements(By.CSS_SELECTOR, "ytd-continuation-item-renderer")
        print(f"Continuation elements count: {len(conts)}")
        for idx, c in enumerate(conts):
            print(f"Continuation {idx+1}: displayed={c.is_displayed()}, innerHTML={c.get_attribute('innerHTML')[:200]}")
            
        # Let's scroll to the bottom slowly (stepwise)
        driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
        time.sleep(5)
        
        driver.save_screenshot("scratch/live_playlist_scrolled.png")
        print("Scrolled screenshot saved to scratch/live_playlist_scrolled.png")
        
        videos_after = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
        print(f"Videos after scrolling: {len(videos_after)}")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
