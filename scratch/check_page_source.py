import os
import sys
import time
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import get_browser

def main():
    driver = get_browser()
    try:
        url = "https://www.youtube.com/playlist?list=PL7y0zeb_CORI0zA5y78PAJBHAeMjEzLqk"
        print(f"Loading URL: {url}")
        driver.get(url)
        time.sleep(5)
        
        # Save page source to inspect
        html = driver.page_source
        with open("scratch/playlist_page.html", "w", encoding="utf-8") as f:
            f.write(html)
            
        print("HTML saved to scratch/playlist_page.html")
        
        # Search for stats or counts in HTML
        # e.g. "285 videos" or "285" in stats
        matches = re.findall(r'(\d+)\s+videos', html, re.I)
        print("Regex 'videos' matches:", matches)
        
        # Search for any text containing "Someday"
        title_matches = re.findall(r'<title>(.*?)</title>', html)
        print("Title tag content:", title_matches)
        
        # Check if user is logged in
        # YouTube usually has "Sign in" or avatar/account info
        if "Sign in" in html:
            print("Status: NOT logged in (found 'Sign in')")
        else:
            print("Status: Maybe logged in (did not find 'Sign in')")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
