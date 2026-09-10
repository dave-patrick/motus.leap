import sys
sys.path.insert(0, '/home/ubuntu/motus.leap')
from core.actions import get_browser
import time

print("Initializing Camofox browser...")
driver = get_browser()
try:
    print("Navigating to Watch Later playlist...")
    driver.get("https://www.youtube.com/playlist?list=WL")
    print("Waiting 20 seconds for page to settle...")
    time.sleep(20)
    
    driver.save_screenshot("debug_wl.png")
    print("Screenshot saved to debug_wl.png")
    
    print("Current Title:", driver.execute_script("return document.title;"))
    print("Current URL:", driver.execute_script("return window.location.href;"))
    
    # Check if signed in
    is_signed_in = driver.execute_script("""
        return !!(document.querySelector('ytd-avatar-button') || document.querySelector('#avatar-btn') || document.querySelector('img#img'));
    """)
    print("Is signed in:", is_signed_in)
    
    # Check for video renderers
    video_count = driver.execute_script("""
        return document.querySelectorAll('ytd-playlist-video-renderer').length;
    """)
    print("Playlist videos count found:", video_count)
    
    # Check if we see the "Sign in" or "Playlist does not exist" message
    alert_text = driver.execute_script("""
        let alertEl = document.querySelector('ytd-alert-with-button-renderer, yt-alert-renderer');
        return alertEl ? alertEl.innerText : 'None';
    """)
    print("Alert message on page:", alert_text)
    
finally:
    driver.quit()
