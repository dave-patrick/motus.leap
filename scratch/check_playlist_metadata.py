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
        
        # Look for playlist header metadata (e.g., number of videos)
        try:
            stats = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-byline-renderer span, yt-formatted-string")
            print("Found stats texts:")
            for s in stats[:20]:
                t = s.text.strip()
                if t:
                    print(f"  - {t!r}")
        except Exception as e:
            print(f"Error getting stats: {e}")
            
        # Let's count how many ytd-playlist-video-renderer elements are present initially
        videos = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
        print(f"Initially found {len(videos)} video renderers.")
        
        # Scroll down 1 time
        driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
        time.sleep(5)
        videos = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
        print(f"After scroll 1, found {len(videos)} video renderers.")
        
        # Let's save a screenshot to see what it looks like at the bottom
        driver.save_screenshot("scratch/bottom_playlist.png")
        print("Saved screenshot to scratch/bottom_playlist.png")
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
