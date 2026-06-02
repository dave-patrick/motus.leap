import os
import sys
import time

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from core import get_browser, list_videos_in_playlist

def main():
    print("Testing live date extraction on Mobile playlist...")
    playlist_url = "https://www.youtube.com/playlist?list=PL7y0zeb_CORIpkrNA-VHc-QwaSjPAgCgj"
    videos = list_videos_in_playlist(playlist_url)
    print(f"Scraped {len(videos)} videos:")
    for v in videos[:10]:
        print(f"- Title: {v['title']}")
        print(f"  Channel: {v['channel']}")
        print(f"  Published: {v['published']}")
        print(f"  URL: {v['url']}")

if __name__ == "__main__":
    main()
