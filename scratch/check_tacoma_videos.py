import json
import os

report_path = "playlists_report.json"
if not os.path.exists(report_path):
    print("playlists_report.json not found!")
    sys.exit(0)

with open(report_path, "r", encoding="utf-8") as f:
    playlists = json.load(f)

tacoma_found = []
for p in playlists:
    p_name = p.get("name", "")
    videos = p.get("videos", [])
    for v in videos:
        title = v.get("title", "")
        if "tacoma" in title.lower():
            tacoma_found.append({
                "playlist": p_name,
                "title": title,
                "url": v.get("url"),
                "channel": v.get("channel")
            })

print(f"Found {len(tacoma_found)} Tacoma videos in playlists_report.json:")
for item in tacoma_found:
    print(f"Playlist: {item['playlist']} | Title: {item['title']} | URL: {item['url']}")
