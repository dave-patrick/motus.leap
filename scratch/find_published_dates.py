import json
import os

report_path = "playlists_report.json"
if os.path.exists(report_path):
    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    found_with_published = []
    found_without_published = []
    for p in data:
        for v in p.get("videos", []):
            if v.get("published"):
                found_with_published.append((p["name"], v["title"], v["published"]))
            else:
                found_without_published.append((p["name"], v["title"]))
    print(f"Total videos with published date: {len(found_with_published)}")
    print(f"Total videos without published date: {len(found_without_published)}")
    if found_with_published:
        print("Samples with published date:")
        for sample in found_with_published[:10]:
            print(f" - Playlist: {sample[0]} | Title: {sample[1]} | Published: {sample[2]}")
    else:
        print("NO videos have a published date!")
else:
    print("playlists_report.json not found")
