import json
with open('playlists_report.json', 'r', encoding='utf-8') as f:
    playlists = json.load(f)
for p in playlists:
    list_id = p['url'].split('list=')[1].split('&')[0]
    print(f"| {p['name']} | {list_id} |")
