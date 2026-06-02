import json
import os

def analyze():
    snapshot_path = 'watch_later_snapshot.json'
    map_path = 'youtube_category_channel_map.txt'
    
    if not os.path.exists(snapshot_path):
        print(f"Error: {snapshot_path} not found")
        return
        
    with open(snapshot_path, 'r', encoding='utf-8') as f:
        videos = json.load(f)
        
    channel_map = {}
    if os.path.exists(map_path):
        with open(map_path, 'r', encoding='utf-8') as f:
            for line in f:
                if ':' in line:
                    ch, cat = line.strip().split(':', 1)
                    channel_map[ch.strip()] = cat.strip()
                    
    uncategorized = {}
    for video in videos:
        channel = video.get('channel', 'Unknown')
        if channel not in channel_map:
            uncategorized[channel] = uncategorized.get(channel, 0) + 1
            
    # Sort by count
    sorted_uncat = sorted(uncategorized.items(), key=lambda x: x[1], reverse=True)
    
    print("\n### Uncategorized Channels (Pending Approval) ###")
    for channel, count in sorted_uncat:
        print(f"- {channel} ({count} videos)")

if __name__ == "__main__":
    analyze()
