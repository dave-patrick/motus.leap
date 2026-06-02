import json
with open('playlists_report.json', 'r', encoding='utf-8') as f:
    report = json.load(f)

targets = [
    'What If I Fell Into A Black Hole?',
    'Geothermal Energy is Changing',
    'The US Has Just Unveiled the Next Abrams Tank'
]

for t in targets:
    print(f'Playlists containing "{t}":')
    for p in report:
        for v in p.get('videos', []):
            if t in v.get('title', ''):
                print(f'  - {p.get("name")}')
                break
