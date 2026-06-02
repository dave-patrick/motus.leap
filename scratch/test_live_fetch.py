import os
import sys
import time
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import list_videos_in_playlist

def main():
    playlist_url = "https://www.youtube.com/playlist?list=PL7y0zeb_CORI0zA5y78PAJBHAeMjEzLqk"
    print(f"Fetching videos from Watch Someday playlist: {playlist_url}")
    
    start_time = time.time()
    videos = list_videos_in_playlist(playlist_url)
    duration = time.time() - start_time
    
    print(f"Fetch completed in {duration:.2f} seconds. Found {len(videos)} videos.")
    
    if videos:
        print("\nFirst 10 videos:")
        for i, v in enumerate(videos[:10]):
            print(f" {i+1}. Title: {v['title']}")
            print(f"    Channel: {v['channel']}")
            print(f"    Published: {v['published']}")
            print(f"    URL: {v['url']}")
            
        unknown_count = sum(1 for v in videos if v.get('published') == 'Unknown')
        print(f"\nSummary: {unknown_count} / {len(videos)} videos have Unknown publication date.")
    else:
        print("No videos returned.")

if __name__ == "__main__":
    main()
