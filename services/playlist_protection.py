"""Playlist Protection & Affinity Safeguards.

Prevents videos that belong in their current playlist (e.g. Star Wars videos
in Star Wars, Aviation in Aviation, Woodworking in Woodworking, etc.) from
being falsely flagged as misplaced into other playlists due to channel mappings
or broad keyword rules.
"""

import re
from typing import Any, Dict, List, Optional, Set

STAGING_KEYWORDS = ("1~sort", "inbox", "unsorted", "watch later", "wl", "check later")


def is_staging_playlist(pid: Optional[str], title: Optional[str]) -> bool:
    """Check if a playlist is a staging/inbox playlist."""
    s_pid = str(pid or "").lower()
    s_title = str(title or "").lower()
    return any(kw in s_pid or kw in s_title for kw in STAGING_KEYWORDS)


# Comprehensive topic keyword dictionary for user's library
TOPIC_KEYWORDS: Dict[str, Set[str]] = {
    "star wars": {
        "star wars", "starwars", "jedi", "sith", "vader", "skywalker", "ahsoka",
        "mandalorian", "grogu", "andor", "kenobi", "clone wars", "boba fett",
        "lightsaber", "lucasfilm", "death star", "coruscant", "force storm",
        "darth", "tatooine", "bad batch", "star wars legends", "star wars visions",
        "into the void", "dawn of the jedi", "republic commando", "high republic",
        "george lucas", "star destroyer", "millennium falcon", "rebel alliance",
        "galactic empire", "death watch", "star wars theory", "star wars explained"
    },
    "ai": {
        "artificial intelligence", "machine learning", "deep learning", "llm",
        "llms", "gpt", "chatgpt", "openai", "claude", "gemini", "anthropic",
        "midjourney", "stable diffusion", "generative ai", "neural network",
        "agentic", "ai agent", "ai agents", "perplexity", "qwen", "llama"
    },
    "aviation": {
        "aviation", "airplane", "aeroplane", "planes", "aircraft", "fighter jet",
        "dogfight", "cockpit", "boeing", "airbus", "f-16", "f-15", "f-22", "f-35",
        "spitfire", "top gun", "flight simulator", "aviation history", "airliner",
        "flight deck", "runway", "air traffic", "atc", "cessna", "turbofan"
    },
    "truck": {
        "truck", "trucks", "tacoma", "toyota tacoma", "pickup", "f-150",
        "silverado", "ram 1500", "tundra", "rivian r1t", "cybertruck", "chevy truck",
        "ford f-150", "toyota truck", "pickup truck"
    },
    "auto": {
        "automotive", "car review", "engine review", "supercar", "porsche",
        "ferrari", "lamborghini", "bmw", "mercedes", "corvette", "mustang",
        "hypercar", "v8 engine", "exhaust sound", "drag race", "horsepower"
    },
    "bigfoot": {
        "bigfoot", "sasquatch", "cryptid", "yeti", "skunk ape", "grassman", "cryptids",
        "sightings", "patterson gimlin", "bigfoot sighting"
    },
    "food": {
        "recipe", "recipes", "cooking", "cook", "chef", "air fryer", "steak",
        "grill", "grilling", "baking", "bake", "cuisine", "kitchen tips", "delicious",
        "meal prep", "dinner", "breakfast", "lunch", "sourdough", "bread"
    },
    "blackstone": {
        "blackstone", "blackstone griddle", "griddle cooking", "griddle seasoning"
    },
    "woodworking": {
        "woodworking", "woodwork", "joinery", "carpentry", "woodturning",
        "router table", "table saw", "dovetail", "wood shop", "timber", "hardwood",
        "plywood", "hand plane", "chisel", "furniture build", "dining table", "table build",
        "desk build", "workbench", "cutting board", "wood grain", "wood project",
        "wooden", "cabinetmaking", "wood carving"
    },
    "blacksmith": {
        "blacksmith", "blacksmithing", "forging", "forge", "anvil", "damascus",
        "knife making", "sword making", "bladesmith", "heat treat"
    },
    "laser": {
        "laser cutter", "laser engraving", "laser engraver", "diode laser", "co2 laser",
        "fiber laser", "lightburn", "xtool", "glowforge", "omtech"
    },
    "3d printing": {
        "3d printing", "3d print", "3d printer", "slicer", "filament", "bambu",
        "prusa", "voron", "ender", "pla", "petg", "abs", "resin printing"
    },
    "smart home": {
        "smart home", "home assistant", "zigbee", "z-wave", "matter", "homekit",
        "home automation", "esphome", "smart plug", "smart switch"
    },
    "drones": {
        "drone", "drones", "fpv", "quadcopter", "dji", "dji avata", "dji mini",
        "fpv drone", "cinewhoop"
    },
    "mobile": {
        "smartphone", "smartphones", "galaxy s", "galaxy z", "iphone", "pixel 8",
        "pixel 9", "galaxy watch", "galaxy buds", "android review", "ios 18",
        "samsung galaxy", "foldable phone"
    },
    "concerts": {
        "live concert", "live performance", "full concert", "live at", "live in concert"
    },
    "music videos": {
        "music video", "official music video", "official video", "official mv", "official audio"
    },
    "cosplay": {
        "cosplay", "cosplayer", "cosplaying", "costume build", "armor build", "eva foam"
    },
    "arizona": {
        "arizona", "phoenix", "tucson", "sedona", "scottsdale", "flagstaff", "grand canyon"
    },
    "tana": {
        "tana", "tana paste", "command node", "tana workflows"
    },
    "camping": {
        "camping", "campground", "tent camping", "campfire", "camp kitchen", "bushcraft"
    },
    "overland": {
        "overland", "overlanding", "off-road", "off-roading", "4x4", "trail run"
    },
    "football": {
        "football", "nfl", "49ers", "touchdown", "quarterback", "super bowl", "chiefs"
    },
    "manifestation": {
        "manifestation", "manifesting", "law of attraction", "neville goddard"
    }
}


def _matches_keywords(text: str, keywords: Set[str]) -> bool:
    """Check if any keyword appears in text as a whole word or clean phrase."""
    t_lower = text.lower()
    for kw in keywords:
        kw_clean = kw.lower()
        if len(kw_clean) <= 2:
            if re.search(r'\b' + re.escape(kw_clean) + r'\b', t_lower):
                return True
        else:
            if kw_clean in t_lower:
                return True
    return False


def is_video_protected_in_current_playlist(
    video_title: str,
    current_pid: Optional[str],
    current_ptitle: Optional[str],
    target_pid: Optional[str],
    target_ptitle: Optional[str],
    config: Optional[Any] = None
) -> bool:
    """Check if a video should be protected from being moved out of its current playlist.
    
    Returns True if the video rightfully belongs in current_playlist and should
    NOT be suggested as misplaced or moved to target_playlist.
    """
    if not video_title or not current_ptitle:
        return False

    # Staging/inbox playlists (1~Sort, Inbox, etc.) are never protected
    if is_staging_playlist(current_pid, current_ptitle):
        return False

    cur_title_lower = current_ptitle.lower().strip()
    v_title_lower = video_title.lower()
    tgt_title_lower = str(target_ptitle or "").lower().strip()

    # 1. Direct Playlist Name Match
    # If the video title contains the current playlist's name (e.g. 'Star Wars', 'Aviation', 'Woodworking')
    if len(cur_title_lower) >= 3:
        if cur_title_lower in ("ai", "pi"):
            cur_matches_name = bool(re.search(r'\b' + re.escape(cur_title_lower) + r'\b', v_title_lower))
        else:
            cur_matches_name = cur_title_lower in v_title_lower
    else:
        cur_matches_name = bool(re.search(r'\b' + re.escape(cur_title_lower) + r'\b', v_title_lower))

    # Also match significant words from playlist title (e.g. 'wood' from 'woodworking')
    cur_title_words = [w for w in re.findall(r'[a-zA-Z0-9]+', cur_title_lower) if len(w) >= 4]
    cur_matches_word = any(re.search(r'\b' + re.escape(w) + r'\b', v_title_lower) for w in cur_title_words)

    # 2. Topic Keyword Match
    cur_keywords = set()
    for topic_key, kws in TOPIC_KEYWORDS.items():
        if topic_key in cur_title_lower or cur_title_lower in topic_key:
            cur_keywords.update(kws)

    # Enrich with keywords from config.ai_rules if available
    if config and hasattr(config, 'ai_rules') and config.ai_rules:
        for rule in config.ai_rules:
            r_target = str(rule.target_playlist or "").lower()
            r_name = str(rule.name or rule.playlist_name or "").lower()
            if (current_pid and str(current_pid).lower() == r_target) or (r_name and r_name in cur_title_lower):
                desc_words = [w for w in re.sub(r'[^\w\s]', ' ', (rule.description or "").lower()).split() if len(w) >= 3]
                cur_keywords.update(desc_words)

    cur_matches_keywords = _matches_keywords(video_title, cur_keywords) if cur_keywords else False

    if not cur_matches_name and not cur_matches_word and not cur_matches_keywords:
        return False

    # 3. Exception Checking
    # For Star Wars: 'UNLESS it is a music video or a cosplay video'
    if "star wars" in cur_title_lower:
        is_music_vid = _matches_keywords(video_title, TOPIC_KEYWORDS["music videos"])
        is_cosplay = _matches_keywords(video_title, TOPIC_KEYWORDS["cosplay"])
        
        # If it is a genuine music video and target is Music Videos, allow the move
        if is_music_vid and "music" in tgt_title_lower:
            return False
        # If it is a genuine cosplay video and target is Cosplay, allow the move
        if is_cosplay and "cosplay" in tgt_title_lower:
            return False

        # Otherwise, protect Star Wars video in Star Wars!
        return True

    # For other playlists:
    # If the video title matches its CURRENT playlist, and does NOT have explicit
    # keywords for the target playlist, it is protected in its current playlist.
    tgt_keywords = set()
    for topic_key, kws in TOPIC_KEYWORDS.items():
        if topic_key in tgt_title_lower or tgt_title_lower in topic_key:
            tgt_keywords.update(kws)

    tgt_matches = _matches_keywords(video_title, tgt_keywords) if tgt_keywords else False
    if (cur_matches_name or cur_matches_word or cur_matches_keywords) and not tgt_matches:
        return True

    # If it matches both current playlist and target playlist, prefer keeping in current playlist!
    return True


def is_playlist_opted_in(pid: Optional[str], title: Optional[str], opt_in_list: Optional[List[str]]) -> bool:
    """Check if a playlist is eligible for channel mapping moves.
    
    - Staging/inbox playlists are ALWAYS eligible.
    - If opt_in_list is configured (not empty), only staging playlists and playlists
      explicitly listed in opt_in_list are eligible.
    - If opt_in_list is empty/unconfigured, all playlists are checked, but videos
      matching their current playlist are safeguarded by is_video_protected_in_current_playlist.
    """
    if is_staging_playlist(pid, title):
        return True

    if not opt_in_list:
        return True

    opt_set = {str(p).lower().strip() for p in opt_in_list if p}
    s_pid = str(pid or "").lower().strip()
    s_title = str(title or "").lower().strip()

    return (s_pid in opt_set) or (s_title in opt_set)