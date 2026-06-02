import json
import os

def rebuild_map():
    if not os.path.exists('playlists_report.json'):
        print("Report not found.")
        return
        
    with open('playlists_report.json', 'r', encoding='utf-8') as f:
        playlists = json.load(f)
        
    mapping = {}
    
    # Priority for certain playlists if a channel is in multiple
    # (Optional: for now just take the first one or most frequent)
    
    for p in playlists:
        playlist_name = p['name']
        if playlist_name in ["Watch later", "Watch Someday", "To Sort"]:
            continue
            
        videos = p.get('videos', [])
        for v in videos:
            channel = v.get('channel')
            if channel:
                # Map channel to the current playlist name
                if channel not in mapping:
                    mapping[channel] = playlist_name
                    
    # Also add the ones we just added manually
    new_rules = [
        ('Stefan Svartling', 'Mobile'),
        ('Project Blue X', 'Mobile'),
        ('Steven Foster', 'Mobile'),
        ('zephplus', 'Mobile'),
        ('Clearly Curious', 'Mobile'),
        ('Agent Zero', 'AI'),
        ("Matt D'Avella", 'Productivity Stuff'),
        ('History in Motion', 'Learning'),
        ('The Secret', 'Learning'),
        ('Star Wars Infinite', 'Star Wars'),
        ('Masked Magic Secrets Revealed', 'Entertainment'),
        ('The Charismatic Voice', 'Music')
    ]
    
    for chan, cat in new_rules:
        mapping[chan] = cat

    # Write to file
    with open('youtube_category_channel_map.txt', 'w', encoding='utf-8') as f:
        for chan in sorted(mapping.keys()):
            f.write(f"{chan}:{mapping[chan]}\n")
            
    print(f"Rebuilt map with {len(mapping)} channels.")

if __name__ == "__main__":
    rebuild_map()
