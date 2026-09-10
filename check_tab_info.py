import sys
sys.path.insert(0, '/home/ubuntu/motus.leap')
from core.actions import get_browser
import time

print("Initializing Camofox browser wrapper...")
driver = get_browser()
try:
    print("Navigating to WL...")
    driver.get("https://www.youtube.com/playlist?list=WL")
    print("Waiting 15 seconds for page load...")
    time.sleep(15)
    
    # Save screenshot
    driver.save_screenshot("test_wl_info.png")
    print("Screenshot saved to test_wl_info.png")
    
    # Get current url, title, and body text
    print("Current Title:", driver.execute_script("return document.title;"))
    print("Current URL:", driver.execute_script("return window.location.href;"))
    
    # Check if signed in
    is_signed_in = driver.execute_script("""
        return !!(document.querySelector('ytd-avatar-button') || document.querySelector('#avatar-btn') || document.querySelector('img#img'));
    """)
    print("Is signed in (avatar check):", is_signed_in)
    
    # Print a snippet of page source
    html = driver.page_source
    print("HTML length:", len(html))
    print("Snippet of HTML:")
    print(html[:1000])
    
finally:
    driver.quit()
