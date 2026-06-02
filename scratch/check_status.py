from core import get_browser
from selenium.webdriver.common.by import By
import time

def check():
    driver = get_browser()
    try:
        driver.get('https://www.youtube.com/playlist?list=WL')
        time.sleep(10)
        # Try to find the stats string like "1,742 videos"
        try:
            stats = driver.find_element(By.CSS_SELECTOR, "yt-formatted-string#stats").text
            print(f"STATS: {stats}")
        except:
            print("Stats element not found")
            
        # List first few video titles
        videos = driver.find_elements(By.ID, "video-title")
        print(f"First {len(videos)} videos:")
        for v in videos[:10]:
            print(f"  - {v.text}")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    check()
