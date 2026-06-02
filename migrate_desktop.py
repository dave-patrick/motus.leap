import json
import os
import time
from core import get_browser, add_video_to_playlist, remove_video_from_playlist, list_videos_in_playlist

def main():
    status_path = os.path.join(os.path.dirname(__file__), "migration_status.json")
    log_path = os.path.join(os.path.dirname(__file__), "migration.log")
    
    def log_msg(msg):
        print(msg)
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(f"{msg}\n")
            
    log_msg("Starting Desktop to Watch Someday migration...")
    
    # 1. Load or initialize migration status
    if os.path.exists(status_path):
        with open(status_path, "r", encoding="utf-8") as f:
            status_data = json.load(f)
        log_msg("Loaded existing migration status.")
    else:
        driver = get_browser()
        try:
            log_msg("Fetching live videos in 'Desktop' playlist from YouTube...")
            videos = list_videos_in_playlist("https://www.youtube.com/playlist?list=PL7y0zeb_CORJraEVfJV-zpqq3iZTXFiv7", driver=driver)
            log_msg(f"Found {len(videos)} videos in Desktop playlist.")
            status_data = []
            for v in videos:
                status_data.append({
                    "title": v.get("title"),
                    "url": v.get("url"),
                    "status": "pending"
                })
            with open(status_path, "w", encoding="utf-8") as f:
                json.dump(status_data, f, indent=2, ensure_ascii=False)
        except Exception as ex:
            log_msg(f"Failed to fetch live videos: {ex}")
            driver.quit()
            return
        finally:
            driver.quit()
        
    pending_videos = [v for v in status_data if v["status"] in ("pending", "failed")]
    log_msg(f"{len(pending_videos)} videos left to migrate (including previously failed).")
    
    if not pending_videos:
        log_msg("All videos already migrated.")
        return
        
    driver = get_browser()
    try:
        for idx, v in enumerate(pending_videos):
            title = v["title"]
            url = v["url"]
            if url.startswith("/"):
                url = "https://www.youtube.com" + url
            log_msg(f"[{idx+1}/{len(pending_videos)}] Moving: '{title}'...")
            
            success = False
            try:
                # Use the proven sequential add/remove functions
                if add_video_to_playlist(url, "Watch Someday", driver=driver):
                    # Sleep 1 second between operations
                    time.sleep(1.0)
                    if remove_video_from_playlist(url, "Desktop", driver=driver):
                        success = True
            except Exception as e:
                log_msg(f"  Error: {e}")
                
            if success:
                v["status"] = "success"
                log_msg("  Success!")
            else:
                v["status"] = "failed"
                log_msg("  Failed!")
                
            # Update status file
            with open(status_path, "w", encoding="utf-8") as f:
                json.dump(status_data, f, indent=2, ensure_ascii=False)
                
            time.sleep(1.5)
    finally:
        driver.quit()
        log_msg("Migration script execution finished.")

if __name__ == "__main__":
    main()
