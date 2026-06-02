import re

def recover_from_junk():
    with open('youtube_category_channel_map.txt', 'rb') as f:
        content = f.read()
    
    # Try all possible decodings
    decodings = ['utf-16', 'utf-16-le', 'utf-16-be', 'utf-8', 'latin-1']
    all_found = set()
    
    for enc in decodings:
        try:
            text = content.decode(enc, 'ignore')
            # Look for Channel:Category patterns
            matches = re.findall(r'([A-Za-z0-9 \.\&\-\']+):([A-Za-z0-9 ]+)', text)
            for m in matches:
                chan, cat = m
                chan = chan.strip()
                cat = cat.strip()
                if chan and cat:
                    all_found.add(f"{chan}:{cat}")
        except:
            continue
            
    if all_found:
        with open('youtube_category_channel_map.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(sorted(list(all_found))) + '\n')
        print(f"Recovered {len(all_found)} mappings.")
    else:
        print("No mappings found in junk.")

if __name__ == "__main__":
    recover_from_junk()
