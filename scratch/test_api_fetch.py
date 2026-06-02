import urllib.request
import json
import urllib.parse

playlist_url = "https://www.youtube.com/playlist?list=PL7y0zeb_CORIJD6jmMKp0HDh8Zv2XWnVE"
encoded_url = urllib.parse.quote_plus(playlist_url)
api_url = f"http://127.0.0.1:8000/api/playlists/videos?playlist_url={encoded_url}"

print(f"Sending GET request to: {api_url}")
try:
    with urllib.request.urlopen(api_url, timeout=300) as response:
        status = response.getcode()
        html = response.read().decode('utf-8')
        data = json.loads(html)
        print(f"Status code: {status}")
        videos = data.get("videos", [])
        print(f"Returned {len(videos)} videos:")
        for idx, v in enumerate(videos):
            print(f"  {idx+1}. Title: {v.get('title')} | Published: {v.get('published')}")
except Exception as e:
    print(f"Error requesting API: {e}")
