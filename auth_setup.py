import os
import subprocess

USER_DATA_DIR = os.path.join(os.path.dirname(__file__), "user_data")

def get_chrome_path():
    paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def setup_auth():
    chrome_path = get_chrome_path()
    
    if not chrome_path:
        print("Could not find Google Chrome. Please install Chrome or log in using another method.")
        return

    print("Starting browser for authentication setup...")
    print(f"Data will be saved to: {USER_DATA_DIR}")
    print("\n" + "="*50)
    print("INSTRUCTIONS:")
    print("1. A standard Chrome browser window will open.")
    print("2. Log into your Google/YouTube account.")
    print("3. Once you are fully logged in and see your account icon, CLOSE the browser window.")
    print("="*50 + "\n")
    
    # Launch Chrome directly without Playwright to bypass Google's automation detection
    cmd = [
        chrome_path,
        f"--user-data-dir={USER_DATA_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://www.youtube.com"
    ]
    
    print("Waiting for you to log in and close the browser...")
    subprocess.run(cmd)
    
    print("Browser closed. Session data saved!")

if __name__ == "__main__":
    setup_auth()
