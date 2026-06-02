import requests
import json

try:
    resp = requests.get("http://127.0.0.1:8000/api/playlists/videos", params={"playlist_url": "https://www.youtube.com/playlist?list=WL", "refresh": "true"})
    print("Status code:", resp.status_code)
    if resp.status_code == 200:
        data = resp.json()
        videos = data.get("videos", [])
        print(f"Returned {len(videos)} videos.")
        for v in videos[:3]:
            print(json.dumps(v, indent=2))
    else:
        print("Error detail:", resp.text)
except Exception as e:
    print("Error:", e)
