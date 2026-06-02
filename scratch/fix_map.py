import os

def fix_map():
    with open('youtube_category_channel_map.txt', 'rb') as f:
        content = f.read()
    
    # Try to decode while ignoring null bytes and bad characters
    text = content.decode('utf-16', 'ignore') if b'\x00' in content else content.decode('utf-8', 'ignore')
    text = text.replace('\x00', '')
    
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        if ':' not in line:
            continue
        line = line.strip()
        # Fix the literal backslash in Matt D\'Avella
        line = line.replace("\\'", "'")
        # Fix spaces in "T h e   C h a r i s m a t i c   V o i c e"
        if "T h e" in line and "C h a r i s" in line:
            parts = line.split(':')
            name = parts[0].replace(' ', '')
            # Add back spaces for the real channel name if needed, but usually it's just "The Charismatic Voice"
            if name == "TheCharismaticVoice":
                line = "The Charismatic Voice:" + parts[1]
        
        if line not in cleaned:
            cleaned.append(line)
            
    with open('youtube_category_channel_map.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(cleaned) + '\n')

if __name__ == "__main__":
    fix_map()
