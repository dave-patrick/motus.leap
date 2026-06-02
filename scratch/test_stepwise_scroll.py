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
        sys.stdout.flush()
        driver.get(url)
        time.sleep(5)
        
        # Initial check
        videos = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
        print(f"Initially found {len(videos)} video renderers.")
        sys.stdout.flush()
        
        # Step-by-step scrolling
        scroll_step = 800
        current_scroll = 0
        
        for step in range(25): # Scroll up to 25 times
            scroll_height = driver.execute_script("return document.documentElement.scrollHeight;")
            current_scroll = min(current_scroll + scroll_step, scroll_height)
            
            # Scroll down by scroll_step
            driver.execute_script(f"window.scrollTo(0, {current_scroll});")
            time.sleep(0.3) # Wait for page to render
            
            videos = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
            print(f"Step {step+1}: Scroll to {current_scroll}/{scroll_height}. Videos found: {len(videos)}")
            sys.stdout.flush()
            
            # If we've reached the very bottom, let's wait a bit longer for continuation to load
            if current_scroll >= scroll_height:
                print("Reached bottom, waiting 3s for continuation...")
                sys.stdout.flush()
                time.sleep(3)
                
                # Check videos count again
                videos = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
                print(f"After waiting at bottom: {len(videos)} videos")
                sys.stdout.flush()
                
                if len(videos) > 100:
                    print("Success! Videos count broke 100 limit.")
                    sys.stdout.flush()
                    break
                    
                # Try nudge scroll up and down
                driver.execute_script("window.scrollBy(0, -150);")
                time.sleep(0.3)
                driver.execute_script("window.scrollBy(0, 150);")
                time.sleep(1.5)
                
                videos = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
                print(f"After nudge at bottom: {len(videos)} videos")
                sys.stdout.flush()
                if len(videos) > 100:
                    break
        
        videos = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
        print(f"Final video count: {len(videos)}")
        sys.stdout.flush()
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
