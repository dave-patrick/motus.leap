import os
import sys
import time

# Add root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from core import get_browser

def test_metadata():
    print("Starting browser...")
    driver = get_browser()
    try:
        # Load user's public playlist page
        url = "https://www.youtube.com/playlist?list=PL7y0zeb_CORLXj5a_QPWbHvJqgemcaXlr"
        print(f"Loading URL: {url}")
        driver.get(url)
        
        # Save screenshot before wait to see what is on screen
        time.sleep(5)
        driver.save_screenshot("scratch/screenshot_test_metadata_pre.png")
        print("Saved screenshot pre-wait.")
        
        # Wait for video elements
        try:
            print("Waiting for ytd-playlist-video-renderer...")
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "ytd-playlist-video-renderer"))
            )
            print("Found video renderers via WebDriverWait!")
        except TimeoutException:
            print("Timed out waiting for video renderers.")
            
        driver.save_screenshot("scratch/screenshot_test_metadata_post.png")
        print("Saved screenshot post-wait.")
        
        # Look for video renderers
        videos = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
        print(f"Found {len(videos)} video renderers.")
        
        for i, v in enumerate(videos[:3]):
            print(f"\n--- Video {i+1} ---")
            try:
                title = v.find_element(By.CSS_SELECTOR, "#video-title").text.strip()
                print(f"Title: {title}")
            except Exception as e:
                print(f"Error getting title: {e}")
                
            try:
                # Get the metadata container
                metadata_line = v.find_element(By.CSS_SELECTOR, "#metadata-line")
                print(f"Metadata line text: {metadata_line.text!r}")
                
                # Check child elements
                spans = metadata_line.find_elements(By.CSS_SELECTOR, "span")
                for j, span in enumerate(spans):
                    print(f"Span {j}: text={span.text!r}, class={span.get_attribute('class')!r}")
            except Exception as e:
                print(f"Error getting metadata: {e}")
                
    finally:
        driver.quit()

if __name__ == "__main__":
    test_metadata()
