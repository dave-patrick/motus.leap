import urllib.request
import urllib.parse
import json

playlist_url = "https://www.youtube.com/playlist?list=PL7y0zeb_CORKoxZUO3457C3b6WrIefFk8" # Football
encoded_url = urllib.parse.quote_plus(playlist_url)
url = f"http://localhost:8000/api/playlists/videos?playlist_url={encoded_url}&refresh=true"

print("Calling API for Football live refresh (this should spawn a subprocess scan)...")
resp = urllib.request.urlopen(url, timeout=120)
data = json.loads(resp.read())
videos = data.get("videos", [])
print(f"Football playlist: {len(videos)} videos returned")
if videos:
    print(f"  First video: {videos[0].get('title', '?')}")
    print(f"  Published: {videos[0].get('published', 'MISSING')}")
