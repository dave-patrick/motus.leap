import requests
import json

def test_flow():
    # 1. Get playlists
    resp = requests.get("http://127.0.0.1:8000/api/playlists")
    print("GET /api/playlists status:", resp.status_code)
    playlists = resp.json()
    print(f"Total playlists returned: {len(playlists)}")
    if not playlists:
        print("No playlists found in cache.")
        return
        
    # Pick first playlist
    first_p = playlists[0]
    p_name = first_p["name"]
    p_url = first_p["url"]
    print(f"Testing with playlist: '{p_name}' ({p_url})")
    
    # 2. Get videos (cached)
    resp = requests.get("http://127.0.0.1:8000/api/playlists/videos", params={"playlist_url": p_url, "refresh": "false"})
    print("GET /api/playlists/videos (cached) status:", resp.status_code)
    result = resp.json()
    videos = result.get("videos", [])
    print(f"Total videos in cache: {len(videos)}")
    if videos:
        print("First 3 videos:")
        for v in videos[:3]:
            print(f"  - {v.get('title')} by {v.get('channel')} ({v.get('url')})")
            
if __name__ == "__main__":
    test_flow()
