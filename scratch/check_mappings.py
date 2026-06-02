import json
import re

channels_to_check = [
    {"channel": "CNET", "title": "I Wore Google's Latest Smart Glasses. Meta Better Be Worried."},
    {"channel": "The Outlaw Effect and 731 Woodworks", "title": "The Best $20 I Ever Spent on My Shop"},
    {"channel": "Jaimunji | Metal on Tap", "title": "ANTHRAX - It's For the Kids Reaction | 10 Years We Waited For THIS?"},
    {"channel": "SuperfastMatt", "title": "Watch Me Clean Up My Cockpit"},
    {"channel": "Consequence", "title": "Alissa White Gluz on Forming Blue Medusa, Leaving Arch Enemy, and Being Vegan"},
    {"channel": "lil WaterBill", "title": "White Death | The Phantom Tiger of Alaska"},
    {"channel": "The Outlaw Effect and 731 Woodworks", "title": "5 GENIUS Amazon Tools You Didn’t Know Existed"},
    {"channel": "Forbidden Ember and Forbidden Roots", "title": "Why Doesn't Disney World Have Mosquitoes? The $1 Secret They Hide From Every Visitor."},
    {"channel": "Siddeshwara Prasad", "title": "Mastering NotebookLM"},
    {"channel": "Miguel EDC 2", "title": "How CRKT Is Doing The Impossible With Folding Knives!"},
    {"channel": "MT", "title": "Metallica - The Thing That Should Not Be (live)"},
    {"channel": "Dani Connor Wild", "title": "I Begged the Guide to Stop…"},
    {"channel": "Secret Origins", "title": "The Younger Dryas Extinction: What Really Killed the Advanced Ancients"},
    {"channel": "EBE-1 Films", "title": "1953 KINGMAN UFO CRASH a short film"},
    {"channel": "MrBiscuitSpeaks", "title": "I UNDERSTAND IT NOW | Metallica-Disposable Heroes | RAPPER REACTS"},
    {"channel": "Lord Gonchar", "title": "Blaze of Glory (Jon Bon Jovi) • Stripped-Down Gritty Country Rock Cover"},
    {"channel": "YouTube Movies & TV", "title": "Death - Death By Metal"},
    {"channel": "StateOfMercury", "title": "What If Disposable Heroes Was On ...And Justice For All?"},
    {"channel": "Cherdleys", "title": "Sorry For Nailing Your Daughter"},
    {"channel": "In Flames", "title": "In Flames - Borgholm Brinner 2018 (Official Documentary)"},
    {"channel": "Wintersun Jari", "title": "Wintersun - Time (TIME I Live Rehearsals At Sonic Pump Studios) REMASTER"},
    {"channel": "Barnhunter", "title": "Metallica Electric Chair bootleg - soundboard recording 1984"},
    {"channel": "Reptiess", "title": "Caliban - I see the falling sky"}
]

# Read channel map
channel_map = {}
with open("youtube_category_channel_map.txt", "r", encoding="utf-8") as f:
    for line in f:
        if ":" in line:
            parts = line.strip().split(":")
            if len(parts) == 2:
                channel_map[parts[0].strip()] = parts[1].strip()

# Read category IDs
category_to_id = {}
with open("youtube_rules.promptinclude.md", "r", encoding="utf-8") as f:
    for line in f:
        if line.strip().startswith("|") and "`PL" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                cat_name = parts[2].strip()
                category_to_id[cat_name] = True

def get_target_cat(title, channel):
    title_lower = title.lower()
    
    def matches(keywords):
        for k in keywords:
            if " " in k:
                if k.lower() in title_lower: return True
            else:
                if re.search(rf"\b{re.escape(k)}\b", title_lower):
                    return True
        return False

    # Arizona
    if matches(["arizona", "phoenix", " az ", ", az"]): return "Arizona"
    # Music Videos
    if matches(["official music video", "official video", "(official"]): return "Music Videos"
    # AI
    if matches([" ai ", "gpt", "claude", "gemini", "notebooklm", "llm", "artificial intelligence"]): return "AI"
    # Star Wars
    if matches(["star wars", "vader", "kenobi", "darth", "jedi", "maul", "coruscant", "skywalker", "ahsoka", "mandalorian", "grogu", "yoda", "sith", "empire", "rebellion", "lightsaber"]): return "Star Wars"
    # 3D Printing
    if matches(["3d print", "slicing", "ender 3", "bambu", "voron", "3d printing"]): return "3D Printing Watch"
    # Woodworking
    if matches(["woodworking", "carpentry", "woodworker"]): return "Woodworking"
    # Smart Home
    if matches(["smart home", "home assistant", "zigbee", "z-wave", "matter"]): return "Smart Home"
    # Aviation
    if matches(["dogfight", "airplane", " jet ", "f-22", "f-35", "f-16", "aviation", "aircraft"]): return "Aviation"
    # Blackstone
    if matches(["blackstone", "griddle", "tortellini"]): return "Blackstone"
    # Food
    if matches(["food", "cook", "recipe", "delicious", "tasty", "culinary"]): return "Food"
    # Mobile
    if matches(["xteink", "ereader", "e-reader", "kindle", "boox", "remarkable", "smartphone", "iphone", "pixel 8", "s24 ultra", "android", "galaxy s"]): return "Mobile"
    # Tech
    if matches(["gadget", "unboxing", "tech review", "hardware"]): return "Tech"
    # Bigfoot
    if matches(["bigfoot", "sasquatch", "cryptid", "yeti"]): return "Bigfoot"
    # Auto
    if matches(["v8", "engine", "horsepower", "torque", "car review", "automotive"]): return "Auto"
    # Football
    if matches([" nfl ", "49ers", "touchdown", "quarterback", "super bowl"]): return "Football"
    # Overland
    if matches(["overland", "offroad", "4x4", "overlanding"]): return "Overland"
    # Drones
    if matches([" dji ", "fpv drone", "mavic", "quadcopter"]): return "Drones"
    
    # Channel map
    if channel in channel_map:
        return channel_map[channel]
        
    # Partial channel match
    for ch_key, cat in channel_map.items():
        if ch_key and ch_key in channel:
            return cat
            
    return None

for item in channels_to_check:
    ch = item["channel"]
    t = item["title"]
    cat = get_target_cat(t, ch)
    in_map = ch in channel_map
    map_val = channel_map.get(ch, "None")
    cat_str = str(cat)
    print(f"Channel: {ch:<40} | Title: {t[:40]:<40} | Matched Category: {cat_str:<20} | In map: {in_map} (val: {map_val})")
