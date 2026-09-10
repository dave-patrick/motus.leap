import os
import sys
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
from core.actions import add_video_to_playlist, get_browser

driver = get_browser()
try:
    print("Trying to add video...")
    res = add_video_to_playlist("https://www.youtube.com/watch?v=yMxbVf8vNnQ", "Auto", driver=driver)
    print(f"Result: {res}")
except Exception as e:
    print(f"Exception: {e}")
    try:
        driver.save_screenshot("test_add_debug.png")
        print("Saved screenshot to test_add_debug.png")
    except Exception as se:
        print(f"Failed to save screenshot: {se}")
finally:
    driver.quit()
