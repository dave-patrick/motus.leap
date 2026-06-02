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
        
        # Take initial screenshot and find elements
        os.makedirs("scratch", exist_ok=True)
        driver.save_screenshot("scratch/scroll_debug_0.png")
        
        videos = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
        print(f"Initial videos: {len(videos)}")
        
        conts = driver.find_elements(By.CSS_SELECTOR, "ytd-continuation-item-renderer")
        print(f"Initial continuations: {len(conts)}")
        for idx, c in enumerate(conts):
            print(f"Cont {idx+1}: displayed={c.is_displayed()}")
            
        for step in range(5):
            scroll_height = driver.execute_script("return document.documentElement.scrollHeight;")
            print(f"\nStep {step+1}: scrollHeight = {scroll_height}")
            
            # Scroll to bottom
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(5)
            
            # Take screenshot to see if it rendered
            driver.save_screenshot(f"scratch/scroll_debug_{step+1}.png")
            
            videos = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
            conts = driver.find_elements(By.CSS_SELECTOR, "ytd-continuation-item-renderer")
            print(f"Step {step+1} videos: {len(videos)}, continuations: {len(conts)}")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
