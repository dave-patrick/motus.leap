import undetected_chromedriver as uc
import time
import os

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "user_data")

def test():
    options = uc.ChromeOptions()
    # options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument("--window-size=800,600")
    print("Starting browser...")
    try:
        driver = uc.Chrome(options=options, use_subprocess=True)
        print("Browser started successfully!")
        driver.get("https://www.google.com")
        print(f"Title: {driver.title}")
        driver.quit()
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test()
