import json

r = json.load(open('playlists_report.json', encoding='utf-8'))
for p in r:
    vids = p.get('videos', [])
    mock = [v for v in vids if 'mockvid' in v.get('url', '') or v.get('title', '').startswith('Mock Video')]
    if mock:
        print(f"{p['name']}: {len(mock)} mock videos / {len(vids)} total")
