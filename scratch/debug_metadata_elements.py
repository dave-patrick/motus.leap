import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from core import get_browser

def main():
    print("Starting browser...")
    driver = get_browser()
    try:
        url = "https://www.youtube.com/playlist?list=PL7y0zeb_CORLXj5a_QPWbHvJqgemcaXlr"
        print(f"Loading URL: {url}")
        driver.get(url)
        time.sleep(5)
        
        videos = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
        print(f"Found {len(videos)} video renderers.")
        
        for i, v in enumerate(videos[:3]):
            print(f"\n--- Video {i+1} ---")
            title = v.find_element(By.CSS_SELECTOR, "#video-title").text.strip()
            print(f"Title: {title}")
            
            # Print outerHTML of ytd-video-meta-block
            try:
                meta_block = v.find_element(By.CSS_SELECTOR, "ytd-video-meta-block")
                print("ytd-video-meta-block outerHTML:")
                print(meta_block.get_attribute("outerHTML")[:1000])
                print(f"ytd-video-meta-block text: {meta_block.text!r}")
            except Exception as e:
                print(f"Error finding ytd-video-meta-block: {e}")
                
            # Print all span text inside ytd-video-meta-block
            try:
                spans = v.find_elements(By.CSS_SELECTOR, "ytd-video-meta-block span")
                for j, s in enumerate(spans):
                    print(f"  Span {j}: text={s.text!r}, id={s.get_attribute('id')!r}, class={s.get_attribute('class')!r}")
            except Exception as e:
                print(f"Error finding spans: {e}")
                
            # Try to query video-info
            try:
                info = v.find_element(By.CSS_SELECTOR, "#video-info")
                print(f"video-info text: {info.text!r}")
            except Exception as e:
                print(f"Error finding video-info: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
