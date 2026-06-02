import json
import os
import re

# Keyword routing logic (copied/updated from cli.py)
def get_target_category(title, channel, channel_map):
    title_lower = title.lower()
    
    # Priority Keywords
    if any(k in title_lower for k in ["ereader", "e-reader", "xteink"]):
        return "Mobile"
    if "gadget" in title_lower:
        return "Tech"
    
    # Standard Rules
    if "arizona" in title_lower or "phoenix" in title_lower:
        return "Arizona"
    elif any(k in title_lower for k in [" ai ", "gpt", "claude", "gemini"]):
        return "AI"
    elif any(k in title_lower for k in ["star wars", "vader", "kenobi"]):
        return "Star Wars"
    elif "blackstone" in title_lower or "griddle" in title_lower:
        return "Blackstone"
    elif any(k in title_lower for k in ["food", "cook", "recipe"]):
        return "Food"
    
    # Channel mapping
    if channel in channel_map:
        return channel_map[channel]
    
    return None

def maintenance():
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

    # Map video ID to its data and list of playlists
    video_library = {}
    for p in playlists:
        p_name = p['name']
        for v in p.get('videos', []):
            v_id = v['url'].split('v=')[-1].split('&')[0]
            if v_id not in video_library:
                video_library[v_id] = {
                    'title': v['title'],
                    'channel': v['channel'],
                    'url': v['url'],
                    'playlists': []
                }
            video_library[v_id]['playlists'].append(p_name)

    actions = []
    
    for vid, data in video_library.items():
        title = data['title']
        channel = data['channel']
        current_ps = data['playlists']
        
        target = get_target_category(title, channel, channel_map)
        
        # 1. Check for miscategorization (in wrong playlist)
        if target and target not in current_ps:
            actions.append({
                'type': 'MISPLACED',
                'title': title,
                'vid': vid,
                'from': current_ps,
                'to': target
            })
            
        # 2. Check for duplicates (even if correct, only keep ONE)
        if len(current_ps) > 1:
            # If target exists, keep target, remove others
            if target and target in current_ps:
                wrong_ps = [p for p in current_ps if p != target]
                actions.append({
                    'type': 'DUPLICATE',
                    'title': title,
                    'vid': vid,
                    'keep': target,
                    'remove': wrong_ps
                })
            else:
                # No clear target, just keep the first one
                actions.append({
                    'type': 'DUPLICATE_NO_TARGET',
                    'title': title,
                    'vid': vid,
                    'keep': current_ps[0],
                    'remove': current_ps[1:]
                })

    # Summary
    if not actions:
        print("Library is clean. No duplicates or misplaced videos found.")
        return

    print(f"Found {len(actions)} maintenance actions needed.")
    
    # Detailed log
    for a in actions:
        if a['type'] == 'MISPLACED':
            print(f"[MOVE] '{a['title']}' -> '{a['to']}' (from {a['from']})")
        elif a['type'] == 'DUPLICATE':
            print(f"[CLEAN] '{a['title']}' (Duplicate) -> Keeping in '{a['keep']}', Removing from {a['remove']}")
        elif a['type'] == 'DUPLICATE_NO_TARGET':
            print(f"[CLEAN] '{a['title']}' (Duplicate) -> No rule, keeping '{a['keep']}', removing from {a['remove']}")

    # Save actions to a file for processing
    with open('maintenance_actions.json', 'w', encoding='utf-8') as f:
        json.dump(actions, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    maintenance()
