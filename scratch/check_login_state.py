import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import core
import time

driver = core.get_browser()
try:
    print("Navigating to YouTube...")
    driver.get("https://www.youtube.com")
    time.sleep(8)
    
    # Check if signed in by looking for sign-in buttons
    is_signed_in = driver.execute_script("""
        let signInBtn = document.querySelector('a[aria-label="Sign in"]') || 
                      document.querySelector('ytd-button-renderer.style-suggestive') ||
                      Array.from(document.querySelectorAll('span')).some(s => s.innerText && s.innerText.includes("Sign in"));
        return !signInBtn;
    """)
    print("Signed in to YouTube according to page check:", is_signed_in)
    
    driver.save_screenshot("scratch/youtube_login_check.png")
    print("Saved screenshot to scratch/youtube_login_check.png")
finally:
    driver.quit()
