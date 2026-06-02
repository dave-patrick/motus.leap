import json
import os
import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

USER_DATA_DIR = os.path.join(os.getcwd(), "user_data")

def get_wl_videos():
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument("--mute-audio")
    options.add_argument("--window-position=-10000,0")
    
    driver = uc.Chrome(options=options, use_subprocess=True, version_main=148)
    try:
        driver.get("https://www.youtube.com/playlist?list=WL")
        time.sleep(5)
        
        # Scroll to ensure all 41 are loaded (should be fine but safe)
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
        videos = []
        video_els = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
        for el in video_els:
            try:
                title_el = el.find_element(By.ID, "video-title")
                title = title_el.text
                link = title_el.get_attribute("href")
                # Extract vid
                import re
                match = re.search(r"v=([^&]+)", link)
                vid = match.group(1) if match else None
                if vid:
                    videos.append({"title": title, "vid": vid})
            except:
                continue
                
        with open("wl_scan_results.json", "w", encoding="utf-8") as f:
            json.dump(videos, f, indent=2)
            
        print(f"Scanned {len(videos)} videos from Watch Later.")
    finally:
        driver.quit()

if __name__ == "__main__":
    get_wl_videos()
