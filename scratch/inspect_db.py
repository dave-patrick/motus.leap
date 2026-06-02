import json
import os

report_path = "playlists_report.json"
if os.path.exists(report_path):
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    print("Total playlists:", len(report))
    for p in report[:15]:
        print(f"Name: {p.get('name')} | URL: {p.get('url')}")
else:
    print("File not found:", report_path)
