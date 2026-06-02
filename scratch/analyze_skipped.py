import json
from collections import Counter

def analyze():
    with open("watch_later_snapshot.json", "r", encoding="utf-8") as f:
        videos = json.load(f)
    
    channel_map = {}
    with open("youtube_category_channel_map.txt", "r", encoding="utf-8") as f:
        for line in f:
            if ":" in line:
                parts = line.strip().split(":")
                if len(parts) == 2:
                    channel_map[parts[0].strip()] = parts[1].strip()

    skipped = []
    for v in videos:
        channel = v.get("channel", "")
        if channel and channel not in channel_map:
            skipped.append(channel)
    
    counts = Counter(skipped)
    print("Top 20 Skipped Channels:")
    for ch, count in counts.most_common(20):
        print(f"{ch}: {count}")

if __name__ == "__main__":
    analyze()
