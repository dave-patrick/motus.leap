import os
import sys
import time
import json

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import get_browser, list_videos_in_playlist

def test_fetch():
    print("Initializing browser...")
    driver = get_browser()
    if not driver:
        print("Failed to initialize browser.")
        return
        
    url = "https://www.youtube.com/playlist?list=PL7y0zeb_CORI0zA5y78PAJBHAeMjEzLqk"
    print(f"Navigating to {url}...")
    
    try:
        driver.get(url)
        time.sleep(5)
        
        # Save an initial screenshot to see if it loads
        # screenshot_path = "scratch/debug_fetch_init.png"
        # driver.save_screenshot(screenshot_path)
        # print(f"Saved initial screenshot to {screenshot_path}")
        
        # Check page title and if elements are present
        print(f"Page Title: {driver.title}")
        
        from selenium.webdriver.common.by import By
        vids = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
        print(f"Initial ytd-playlist-video-renderer count: {len(vids)}")
        
        # Run list_videos_in_playlist using this driver
        print("Running list_videos_in_playlist...")
        results = list_videos_in_playlist(url, driver=driver)
        print(f"Scraped {len(results)} videos!")
        if results:
            print("Sample video 1:", results[0])
            # Save results count of non-Unknown dates
            unknown_count = sum(1 for r in results if r.get("published") == "Unknown")
            print(f"Unknown dates: {unknown_count} out of {len(results)}")
            
        driver.save_screenshot("scratch/debug_fetch_final.png")
        print("Saved final screenshot to scratch/debug_fetch_final.png")
    except Exception as e:
        print(f"Error during fetch: {e}")
        try:
            driver.save_screenshot("scratch/debug_fetch_error.png")
            print("Saved error screenshot to scratch/debug_fetch_error.png")
        except:
            pass
    finally:
        driver.quit()

if __name__ == "__main__":
    test_fetch()
