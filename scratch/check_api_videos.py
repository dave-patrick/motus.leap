import urllib.request
import json

# Test Football playlist (real cached, no live fetch should occur)
url = "http://localhost:8000/api/playlists/videos?playlist_url=https%3A%2F%2Fwww.youtube.com%2Fplaylist%3Flist%3DPL7y0zeb_CORKoxZUO3457C3b6WrIefFk8"
resp = urllib.request.urlopen(url, timeout=5)
data = json.loads(resp.read())
videos = data.get("videos", [])
print(f"Football playlist: {len(videos)} videos returned")
if videos:
    print(f"  First video: {videos[0].get('title', '?')}")
    print(f"  Published: {videos[0].get('published', 'MISSING')}")
    all_have = all("published" in v for v in videos)
    print(f"  All have published key: {all_have}")
    non_empty = sum(1 for v in videos if v.get("published") and v.get("published") != "Unknown")
    print(f"  Videos with real published dates (not Unknown): {non_empty}/{len(videos)}")
    some_unknowns = [v.get("published") for v in videos[:5]]
    print(f"  First 5 published values: {some_unknowns}")
