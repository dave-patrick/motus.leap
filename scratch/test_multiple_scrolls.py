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
        
        # Initial count
        videos = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
        print(f"Initially found {len(videos)} videos.")
        
        # Scroll loop
        for step in range(6):
            driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
            time.sleep(5)
            
            videos = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
            print(f"Step {step+1}: Scroll to bottom. Videos found: {len(videos)}")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
