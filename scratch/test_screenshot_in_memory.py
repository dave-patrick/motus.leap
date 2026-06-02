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
        
        # Force initial paint in-memory
        driver.get_screenshot_as_png()
        
        videos = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
        print(f"Initial videos: {len(videos)}")
        
        for step in range(5):
            # Scroll to bottom
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(3)
            
            # Force paint to trigger IntersectionObserver
            driver.get_screenshot_as_png()
            time.sleep(2)
            
            videos = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
            print(f"Step {step+1} videos: {len(videos)}")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
