import json
from collections import Counter
import os

with open('playlists_report.json', 'r', encoding='utf-8') as f:
    report = json.load(f)

os.makedirs('scratch', exist_ok=True)

for p in report:
    name = p.get('name')
    if name in ['Music Videos', 'Music', 'Star Wars']:
        videos = p.get('videos', [])
        print(f'\n--- {name} ({len(videos)} videos) ---')
        urls = [v['url'] for v in videos]
        dupes = [url for url, count in Counter(urls).items() if count > 1]
        print(f'Duplicates: {len(dupes)}')
        if dupes:
            for d in dupes:
                vids = [v for v in videos if v['url'] == d]
                print(f'  - {d} ({vids[0]["title"]})')
        
        # Save titles to files for deeper analysis
        filename = f'scratch/{name.replace(" ", "_")}_titles.txt'
        with open(filename, 'w', encoding='utf-8') as f_out:
            for v in videos:
                f_out.write(f'{v.get("channel", "")}: {v.get("title", "")}\n')
        print(f'Saved video list to {filename}')
