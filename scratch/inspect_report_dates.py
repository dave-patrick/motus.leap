import json
import os

report_path = "playlists_report.json"
if os.path.exists(report_path):
    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"Total playlists: {len(data)}")
    for i, p in enumerate(data):
        name = p.get("name", "Unknown Name")
        url = p.get("url", "")
        videos = p.get("videos", [])
        date_counts = {}
        for v in videos:
            pub = v.get("published", "MISSING")
            date_counts[pub] = date_counts.get(pub, 0) + 1
        print(f"{i+1}. Playlist: {name} ({len(videos)} videos) | URL: {url}")
        print(f"   Date distribution: {date_counts}")
else:
    print("playlists_report.json not found")
