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
        
        # Check initial video count
        videos = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
        print(f"Initially found {len(videos)} video renderers.")
        
        # Check continuation element
        conts = driver.find_elements(By.CSS_SELECTOR, "ytd-continuation-item-renderer")
        print(f"Initially found {len(conts)} continuation elements.")
        
        # Scroll the first continuation element into view
        if conts:
            print("Scrolling first continuation element into view...")
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", conts[0])
            time.sleep(5)
            
            videos = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
            print(f"After continuation scroll, found {len(videos)} video renderers.")
            
            # Check continuation elements again
            conts = driver.find_elements(By.CSS_SELECTOR, "ytd-continuation-item-renderer")
            print(f"Now found {len(conts)} continuation elements.")
        else:
            print("No continuation elements found in Selenium DOM!")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
