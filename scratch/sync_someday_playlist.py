import os
import sys
import time
import json

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import get_browser, list_videos_in_playlist

def sync_someday():
    print("Initializing browser for Watch Someday sync...")
    driver = get_browser()
    if not driver:
        print("Failed to initialize browser.")
        sys.exit(1)
        
    url = "https://www.youtube.com/playlist?list=PL7y0zeb_CORI0zA5y78PAJBHAeMjEzLqk"
    print(f"Navigating to {url}...")
    
    try:
        driver.get(url)
        time.sleep(5)
        
        print("Page Title:", driver.title)
        
        print("Running list_videos_in_playlist...")
        results = list_videos_in_playlist(url, driver=driver)
        print(f"Scraped {len(results)} videos!")
        
        if not results:
            print("No videos scraped. Exiting to prevent overwriting cache with empty data.")
            sys.exit(1)
            
        # Count unknown dates
        unknown_count = sum(1 for r in results if r.get("published") == "Unknown")
        print(f"Unknown dates: {unknown_count} out of {len(results)}")
        
        # Load existing playlists report
        report_path = "playlists_report.json"
        report = []
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                report = json.load(f)
                
        # Find if Watch Someday exists to keep its name
        playlist_name = "Watch Someday"
        for p in report:
            if p["url"] == url or url in p["url"]:
                playlist_name = p["name"]
                break
                
        # Filter out existing entries for Watch Someday
        report = [p for p in report if not (p["url"] == url or url in p["url"])]
        
        # Append updated Watch Someday entry
        report.append({
            "name": playlist_name,
            "url": url,
            "videos": results,
            "video_count": len(results)
        })
        
        # Save report
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
            
        print("Successfully updated playlists_report.json cache with scraped videos!")
        
    except Exception as e:
        print(f"Error during sync: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    sync_someday()
