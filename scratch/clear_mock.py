import json

report_path = 'playlists_report.json'
r = json.load(open(report_path, encoding='utf-8'))

cleared = []
for p in r:
    vids = p.get('videos', [])
    real = [v for v in vids if 'mockvid' not in v.get('url', '') and not v.get('title', '').startswith('Mock Video')]
    if len(real) < len(vids):
        removed = len(vids) - len(real)
        print(f"Clearing {removed} mock videos from '{p['name']}'")
        p['videos'] = real
        p['video_count'] = len(real)
        cleared.append(p['name'])

with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(r, f, indent=2, ensure_ascii=False)

print(f"\nDone. Cleared mock data from: {cleared}")
print("These playlists will do a live fetch next time they are opened in the dashboard.")
