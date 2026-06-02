import json
import os
import re

# Keyword routing logic (copied from cli.py)
def get_target_category(title, channel, channel_map):
    title_lower = title.lower()
    
    # Rule 1: Arizona keywords
    if "arizona" in title_lower or "phoenix" in title_lower or " az " in title_lower or ", az" in title_lower:
        return "Arizona"
    # Rule 2: Music videos
    elif "official music video" in title_lower or "official video" in title_lower or "(official" in title_lower:
        return "Music Videos"
    # Rule 3: AI keywords
    elif any(k in title_lower for k in [" ai ", "gpt", "claude", "gemini", "notebooklm", "llm"]):
        return "AI"
    # Rule 4: Star Wars keywords
    elif "star wars" in title_lower or "vader" in title_lower or "kenobi" in title_lower or " darth " in title_lower or " jedi " in title_lower or " maul " in title_lower:
        return "Star Wars"
    # Rule 6: 3D Printing keywords
    elif any(k in title_lower for k in ["3d print", "slicing", "ender 3", "bambu", "voron"]):
        return "3D Printing Watch"
    # Rule 7: Woodworking keywords
    elif any(k in title_lower for k in ["woodworking", "woodworking", "carpentry"]):
        return "Woodworking"
    # Rule 8: Smart Home keywords
    elif "smart home" in title_lower or "home assistant" in title_lower:
        return "Smart Home Stuff"
    # Rule 9: Aviation keywords
    elif any(k in title_lower for k in ["dogfight", " plane", " jet ", " f-22", " f-35", " f-16", "aviation", "aircraft"]):
        return "Aviation"
    # Rule 10: Blackstone keywords
    elif "blackstone" in title_lower or "griddle" in title_lower:
        return "Blackstone"
    # Rule 11: Food keywords
    elif any(k in title_lower for k in ["food", "cook", "recipe", "delicious", "tasty"]):
        return "Food"
    # Rule 12: Xteink/Mobile keywords
    elif "xteink" in title_lower or "ereader" in title_lower or "e-reader" in title_lower:
        return "Mobile"
    # Rule 13: Gadget/Tech keywords
    elif "gadget" in title_lower:
        return "Tech"
    # Rule 9: Channel mapping
    elif channel in channel_map:
        return channel_map[channel]
    
    return None

def deduplicate():
    if not os.path.exists('playlists_report.json'):
        print("Report not found. Run scan first.")
        return
        
    with open('playlists_report.json', 'r', encoding='utf-8') as f:
        playlists = json.load(f)
        
    channel_map = {}
    if os.path.exists('youtube_category_channel_map.txt'):
        with open('youtube_category_channel_map.txt', 'r', encoding='utf-8') as f:
            for line in f:
                if ':' in line:
                    chan, cat = line.strip().split(':', 1)
                    channel_map[chan] = cat

    # Map video ID to (title, channel, [playlist_names])
    video_map = {}
    for p in playlists:
        p_name = p['name']
        for v in p.get('videos', []):
            v_id = v['url'].split('v=')[-1].split('&')[0]
            if v_id not in video_map:
                video_map[v_id] = {
                    'title': v['title'],
                    'channel': v['channel'],
                    'url': v['url'],
                    'playlists': []
                }
            video_map[v_id]['playlists'].append(p_name)

    # Find duplicates
    duplicates = {vid: data for vid, data in video_map.items() if len(data['playlists']) > 1}
    
    if not duplicates:
        print("No duplicates found.")
        return

    print(f"Found {len(duplicates)} duplicate videos.")
    
    for vid, data in duplicates.items():
        title = data['title']
        channel = data['channel']
        current_playlists = data['playlists']
        
        target = get_target_category(title, channel, channel_map)
        
        print(f"\nProcessing '{title}' ({vid})")
        print(f"  Currently in: {', '.join(current_playlists)}")
        
        if target:
            print(f"  Target playlist according to rules: {target}")
            # If it's already in the target, remove from others
            if target in current_playlists:
                for p in current_playlists:
                    if p != target:
                        print(f"  Action: Remove from '{p}'")
                        # Here I would call the actual removal tool
            else:
                print(f"  Action: Move to '{target}' and remove from all current.")
        else:
            print("  No clear target rule found. Keeping in: " + current_playlists[0])
            # Maybe use the first one and remove from others?
            for p in current_playlists[1:]:
                print(f"  Action: Remove from '{p}' (duplicate cleanup)")

if __name__ == "__main__":
    deduplicate()
