import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core import get_browser

def test():
    print("Attempting to start browser...")
    try:
        driver = get_browser()
        if driver:
            print("Browser started successfully!")
            print(f"Title: {driver.title}")
            driver.quit()
        else:
            print("Failed to start browser (None returned)")
    except Exception as e:
        print(f"Exception caught: {e}")

if __name__ == "__main__":
    test()
