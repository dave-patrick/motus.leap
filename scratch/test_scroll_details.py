import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import get_browser

def main():
    driver = get_browser()
    try:
        url = "https://www.youtube.com/playlist?list=PL7y0zeb_CORI0zA5y78PAJBHAeMjEzLqk"
        print(f"Loading URL: {url}")
        driver.get(url)
        time.sleep(5)
        
        # Initial scroll height and metrics
        metrics = driver.execute_script("""
            return {
                scrollHeight: document.documentElement.scrollHeight,
                bodyScrollHeight: document.body.scrollHeight,
                windowHeight: window.innerHeight,
                scrollY: window.scrollY,
                videosCount: document.querySelectorAll('ytd-playlist-video-renderer').length
            };
        """)
        print("Initial metrics:", metrics)
        
        # Scroll to bottom
        driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
        time.sleep(5)
        
        # Metrics after scroll 1
        metrics2 = driver.execute_script("""
            return {
                scrollHeight: document.documentElement.scrollHeight,
                bodyScrollHeight: document.body.scrollHeight,
                windowHeight: window.innerHeight,
                scrollY: window.scrollY,
                videosCount: document.querySelectorAll('ytd-playlist-video-renderer').length
            };
        """)
        print("After Scroll 1 metrics:", metrics2)
        
        # Scroll again, but wait longer or nudge
        driver.execute_script("window.scrollBy(0, -100);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, document.documentElement.scrollHeight);")
        time.sleep(5)
        
        # Metrics after Scroll 2
        metrics3 = driver.execute_script("""
            return {
                scrollHeight: document.documentElement.scrollHeight,
                bodyScrollHeight: document.body.scrollHeight,
                windowHeight: window.innerHeight,
                scrollY: window.scrollY,
                videosCount: document.querySelectorAll('ytd-playlist-video-renderer').length
            };
        """)
        print("After Scroll 2 metrics:", metrics3)
        
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
