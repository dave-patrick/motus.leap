import os

file_path = 'youtube_category_channel_map.txt'

new_channels = {
    "Michael Button": "Learning",
    "TekWize": "Tech",
    "Tech Lies": "Tech",
}

channel_map = {}
with open(file_path, 'r', encoding='utf-8') as f:
    for line in f:
        if ':' in line:
            parts = line.strip().split(':')
            if len(parts) == 2:
                channel_map[parts[0].strip()] = parts[1].strip()

added = []
for ch, cat in new_channels.items():
    if ch not in channel_map:
        channel_map[ch] = cat
        added.append(f"  {ch} -> {cat}")
    else:
        print(f"  Already exists: {ch} -> {channel_map[ch]}")

sorted_map = dict(sorted(channel_map.items(), key=lambda item: item[0].lower()))

with open(file_path, 'w', encoding='utf-8') as f:
    for ch, cat in sorted_map.items():
        f.write(f"{ch}:{cat}\n")

print(f"Added {len(added)} new mappings ({len(sorted_map)} total):")
for a in added:
    print(a)
