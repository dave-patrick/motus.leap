import os

def fix_encoding():
    with open('youtube_category_channel_map.txt', 'rb') as f:
        content = f.read()
    
    # Try decoding as UTF-16 (little endian or big endian)
    try:
        text = content.decode('utf-16')
        print("Decoded as UTF-16")
    except:
        try:
            text = content.decode('utf-16-be')
            print("Decoded as UTF-16-BE")
        except:
            text = content.decode('utf-8', 'ignore')
            print("Decoded as UTF-8 (ignore)")

    # Remove null bytes and other weird stuff
    text = text.replace('\x00', '')
    
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        line = line.strip()
        if ':' not in line:
            continue
            
        # If it's still spaced out like "T h e   C h a r i s m a t i c", fix it
        # But wait, if it's UTF-16 it shouldn't be spaced out if decoded correctly.
        
        if line not in cleaned:
            cleaned.append(line)
            
    with open('youtube_category_channel_map.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(cleaned) + '\n')

if __name__ == "__main__":
    fix_encoding()
