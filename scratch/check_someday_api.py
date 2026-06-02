import urllib.request
import urllib.parse
import json

playlist_url = "https://www.youtube.com/playlist?list=PL7y0zeb_CORI0zA5y78PAJBHAeMjEzLqk"
encoded_url = urllib.parse.quote_plus(playlist_url)
url = f"http://localhost:8000/api/playlists/videos?playlist_url={encoded_url}"

print("Calling API for Watch Someday...")
resp = urllib.request.urlopen(url, timeout=5)
data = json.loads(resp.read())
videos = data.get("videos", [])
print(f"Watch Someday playlist: {len(videos)} videos returned")
if videos:
    print(f"  First video: {videos[0].get('title', '?')}")
    print(f"  First video Published: {videos[0].get('published', 'MISSING')}")
    all_have = all("published" in v for v in videos)
    print(f"  All have published key: {all_have}")
    non_empty = sum(1 for v in videos if v.get("published") and v.get("published") != "Unknown")
    print(f"  Videos with real published dates (not Unknown): {non_empty}/{len(videos)}")
    some_dates = [v.get("published") for v in videos[:10]]
    print(f"  First 10 published values: {some_dates}")
