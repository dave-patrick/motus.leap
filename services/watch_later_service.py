"""Watch Later Processing & Auto-Sorting Service.

Provides parsing, rule classification, preview generation, and execution
for auto-sorting YouTube Watch Later videos into category playlists.
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data")
SNAPSHOT_FILES = [
    os.path.join(DATA_DIR, "watch_later_snapshot.json"),
    os.path.join(DATA_DIR, "watch_later_fresh.json"),
    os.path.join(BASE_DIR, "watch_later_snapshot.json"),
    os.path.join(BASE_DIR, "watch_later_fresh.json"),
]


def extract_video_id(url_or_id: str) -> Optional[str]:
    """Extract standard 11-character YouTube video ID."""
    if not url_or_id:
        return None
    s = str(url_or_id).strip()
    m = re.search(r"(?:v=|youtu\.be/|/watch\?v=)([A-Za-z0-9_-]{11})", s)
    if m:
        return m.group(1)
    if re.match(r"^[A-Za-z0-9_-]{11}$", s):
        return s
    return None


def get_all_snapshot_candidate_paths() -> List[str]:
    """Return all possible snapshot paths in priority order across DATA_DIR, users dirs, and BASE_DIR."""
    candidates = list(SNAPSHOT_FILES)
    # Check users subdirectories in DATA_DIR (e.g. /app/data/users/{user_id}/...)
    users_dir = os.path.join(DATA_DIR, "users")
    if os.path.exists(users_dir):
        try:
            for entry in os.scandir(users_dir):
                if entry.is_dir():
                    candidates.append(os.path.join(entry.path, "watch_later_snapshot.json"))
                    candidates.append(os.path.join(entry.path, "watch_later_fresh.json"))
                    candidates.append(os.path.join(entry.path, "playlist_videos_WL.json"))
        except Exception as e:
            log.warning(f"Error scanning users_dir for Watch Later: {e}")
    # Also check BASE_DIR/data if present
    base_data = os.path.join(BASE_DIR, "data")
    if os.path.exists(base_data):
        candidates.append(os.path.join(base_data, "watch_later_snapshot.json"))
        candidates.append(os.path.join(base_data, "watch_later_fresh.json"))
    return candidates


def load_watch_later_videos(allow_browser: bool = False, driver=None) -> List[Dict[str, Any]]:
    """Load Watch Later videos from local snapshot files, persistent disk cache, or live browser if requested."""
    # 1. Live browser extraction if requested and available
    if allow_browser:
        try:
            from core.actions import get_browser, list_videos_in_playlist
            os.environ.setdefault("DISABLE_CAMOFOX", "1")
            browser = driver or get_browser()
            try:
                live_vids = list_videos_in_playlist("https://www.youtube.com/playlist?list=WL", driver=browser)
                if live_vids:
                    # Save to both DATA_DIR and BASE_DIR
                    for out_dir in [DATA_DIR, BASE_DIR]:
                        try:
                            os.makedirs(out_dir, exist_ok=True)
                            snap_path = os.path.join(out_dir, "watch_later_snapshot.json")
                            with open(snap_path, "w", encoding="utf-8") as f:
                                json.dump(live_vids, f, indent=2, ensure_ascii=False)
                        except Exception:
                            pass
                    return _normalize_videos(live_vids)
            finally:
                if not driver and browser:
                    try:
                        browser.quit()
                    except Exception:
                        pass
        except Exception as be:
            log.warning(f"Live Watch Later browser scan failed, falling back to snapshot: {be}")

    # 2. Local snapshot files across DATA_DIR, users dirs, and BASE_DIR
    for snap_path in get_all_snapshot_candidate_paths():
        if os.path.exists(snap_path):
            try:
                with open(snap_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, list) and raw:
                    return _normalize_videos(raw)
                elif isinstance(raw, dict) and raw.get("videos") and isinstance(raw["videos"], list):
                    return _normalize_videos(raw["videos"])
            except Exception as fe:
                log.warning(f"Failed to read snapshot {snap_path}: {fe}")

    # 3. Check all_data.json caches for any videos tagged with playlist_id == 'WL'
    for candidate_dir in [DATA_DIR, BASE_DIR]:
        all_data_path = os.path.join(candidate_dir, "all_data.json")
        if os.path.exists(all_data_path):
            try:
                with open(all_data_path, "r", encoding="utf-8") as f:
                    all_d = json.load(f)
                if isinstance(all_d, dict) and "videos" in all_d:
                    wl_vids = [
                        v for v in all_d["videos"]
                        if isinstance(v, dict) and (
                            str(v.get("playlist_id", "")).upper() == "WL" or
                            "watch later" in str(v.get("playlist_name", "")).lower()
                        )
                    ]
                    if wl_vids:
                        return _normalize_videos(wl_vids)
            except Exception as e:
                log.warning(f"Failed reading all_data.json for WL videos from {all_data_path}: {e}")

    # Check users/*/all_data.json
    users_dir = os.path.join(DATA_DIR, "users")
    if os.path.exists(users_dir):
        try:
            for entry in os.scandir(users_dir):
                if entry.is_dir():
                    user_all = os.path.join(entry.path, "all_data.json")
                    if os.path.exists(user_all):
                        try:
                            with open(user_all, "r", encoding="utf-8") as f:
                                all_d = json.load(f)
                            if isinstance(all_d, dict) and "videos" in all_d:
                                wl_vids = [
                                    v for v in all_d["videos"]
                                    if isinstance(v, dict) and (
                                        str(v.get("playlist_id", "")).upper() == "WL" or
                                        "watch later" in str(v.get("playlist_name", "")).lower()
                                    )
                                ]
                                if wl_vids:
                                    return _normalize_videos(wl_vids)
                        except Exception:
                            pass
        except Exception:
            pass

    return []


def _normalize_videos(raw_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Ensure every video item has standard keys (id, title, channel, url, duration)."""
    normalized = []
    seen_ids = set()
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        url = item.get("url", "")
        vid = item.get("id") or item.get("vid") or extract_video_id(url)
        if not vid or vid in seen_ids:
            continue
        seen_ids.add(vid)

        clean_url = url if url.startswith("http") else f"https://www.youtube.com/watch?v={vid}"
        duration = item.get("duration") or item.get("length", "")
        if isinstance(duration, str):
            duration = duration.strip().split("\n")[0]

        normalized.append({
            "id": vid,
            "video_id": vid,
            "title": (item.get("title") or f"Video {vid}").strip(),
            "channel": (item.get("channel") or "").strip(),
            "url": clean_url,
            "published": item.get("published", ""),
            "duration": duration,
        })
    return normalized


def _find_data_file(filename: str) -> Optional[str]:
    """Find a configuration or data file in DATA_DIR or BASE_DIR."""
    for d in [DATA_DIR, BASE_DIR]:
        p = os.path.join(d, filename)
        if os.path.exists(p):
            return p
    return None


def load_rules_and_mappings() -> Tuple[Dict[str, str], Dict[str, str]]:
    """Parse channel mappings and category-to-playlist ID mappings."""
    channel_map = {}
    category_to_id = {}

    # 1. yt_category_channel_map.txt
    ch_map_path = _find_data_file("yt_category_channel_map.txt")
    if ch_map_path:
        try:
            with open(ch_map_path, "r", encoding="utf-8") as f:
                for line in f:
                    if ":" in line:
                        parts = line.strip().split(":", 1)
                        if len(parts) == 2:
                            ch = parts[0].strip()
                            cat = parts[1].strip()
                            if ch and cat:
                                channel_map[ch] = cat
        except Exception as e:
            log.warning(f"Error loading channel map from {ch_map_path}: {e}")

    # 2. yt_rules.promptinclude.md (category -> playlist ID)
    rules_path = _find_data_file("yt_rules.promptinclude.md")
    if rules_path:
        try:
            with open(rules_path, "r", encoding="utf-8") as f:
                for line in f:
                    line_s = line.strip()
                    if line_s.startswith("|") and "PL" in line_s:
                        parts = [p.strip() for p in line_s.split("|")]
                        if len(parts) >= 4:
                            cat_name = parts[2].strip()
                            m = re.search(r'(PL[A-Za-z0-9_-]+)', parts[3].strip())
                            if m:
                                category_to_id[cat_name] = m.group(1)
        except Exception as e:
            log.warning(f"Error loading promptinclude rules from {rules_path}: {e}")

    # 3. playlists_urls.json (additional active playlists)
    urls_path = _find_data_file("playlists_urls.json")
    if urls_path:
        try:
            with open(urls_path, "r", encoding="utf-8") as f:
                urls = json.load(f)
                for item in urls:
                    name = item.get("name")
                    url = item.get("url", "")
                    if name and "list=" in url:
                        pid = url.split("list=")[1].split("&")[0]
                        category_to_id[name] = pid
        except Exception as e:
            log.warning(f"Error loading playlists_urls.json from {urls_path}: {e}")

    # 4. categorized_playlists.json (check for 1~Sort / To Sort / Inbox)
    cat_pl_path = _find_data_file("categorized_playlists.json")
    if cat_pl_path:
        try:
            with open(cat_pl_path, "r", encoding="utf-8") as f:
                cat_pls = json.load(f)
                if isinstance(cat_pls, list):
                    for item in cat_pls:
                        name = item.get("name")
                        url = item.get("url", "")
                        pid = None
                        if "list=" in url:
                            pid = url.split("list=")[1].split("&")[0]
                        elif item.get("id"):
                            pid = item.get("id")
                        if name and pid:
                            clean_name = name.lower()
                            if any(k in clean_name for k in ["to sort", "1~sort", "1sort"]) or pid == "PL7y0zeb_CORJD72rD7pNoAoWtDW5k8oSy":
                                category_to_id["1~Sort"] = pid
                            else:
                                category_to_id[name] = pid
        except Exception as e:
            log.warning(f"Error loading categorized_playlists.json from {cat_pl_path}: {e}")

    return channel_map, category_to_id


def classify_video(
    title: str,
    channel: str,
    channel_map: Dict[str, str],
    category_to_id: Dict[str, str]
) -> Dict[str, Any]:
    """Classify a single video into a target category and playlist ID using hierarchical rules."""
    title_lower = title.lower()
    channel_lower = channel.lower()
    channel_map_lower = {k.lower(): (k, v) for k, v in channel_map.items()}

    # 1. Exact channel mapping (Highest Priority)
    if channel_lower in channel_map_lower:
        orig_k, cat = channel_map_lower[channel_lower]
        pid = category_to_id.get(cat)
        return {
            "target_category": cat,
            "target_playlist_id": pid,
            "match_type": "exact_channel",
            "matched_by": f"Channel rule: {orig_k}",
        }

    # Keyword matcher helper
    def matches(keywords: List[str]) -> bool:
        for k in keywords:
            if " " in k or not k.isalnum():
                if k.lower() in title_lower:
                    return True
            else:
                if re.search(rf"\b{re.escape(k.lower())}\b", title_lower):
                    return True
        return False

    # 2. Keyword rules
    is_tv_or_monitor = matches([" tv ", "television", "qled", "neo qled", "oled", "monitor", "soundbar"])
    is_star_wars = matches(["star wars", "jedi", "sith", "vader", "lightsaber", "galaxy's edge", "galaxy’s edge", "skeleton crew", "yoda", "grogu"])
    is_space = matches(["space", "nasa", "telescope", "hubble", "jwst", "astronomy", "milky way", "universe", "andromeda", "cosmic", "cosmology", "astrophysics", "orbit", "planet", "solar system", "constellation"])
    is_samsung_galaxy = (
        (matches(["samsung"]) or matches(["galaxy"])) and not is_tv_or_monitor and not is_star_wars and not is_space
    )

    cat = None
    rule_name = None

    if (matches(["xteink", "ereader", "e-reader", "kindle", "boox", "remarkable", "smartphone", "iphone", "pixel 8", "s24 ultra", "android"]) or is_samsung_galaxy) and not is_star_wars and not is_space:
        cat = "Mobile"
        rule_name = "Mobile keywords"
    elif matches(["tana"]):
        cat = "Tana"
        rule_name = "Tana keywords"
    elif matches(["arizona", "phoenix", " az ", ", az"]):
        cat = "Arizona"
        rule_name = "Arizona keywords"
    elif matches(["cosplay"]):
        cat = "Cosplay"
        rule_name = "Cosplay keywords"
    elif matches(["official music video", "official video", "music video", "lyric video", "official audio", "official lyric", "official visualizer", "musicvideo", "lyrics video", "(official)"]):
        cat = "Music Videos"
        rule_name = "Music Video keywords"
    elif matches(["star wars", "vader", "kenobi", "darth", "jedi", "darth maul", "coruscant", "skywalker", "ahsoka", "mandalorian", "grogu", "yoda", "sith", "galactic empire", "rebel alliance", "lightsaber"]):
        cat = "Star Wars"
        rule_name = "Star Wars keywords"
    elif matches([" ai ", "gpt", "claude", "gemini", "notebooklm", "llm", "artificial intelligence", "deepseek", "qwen", "mistral"]):
        cat = "AI"
        rule_name = "AI keywords"
    elif matches(["3d print", "slicing", "ender 3", "bambu", "voron", "3d printing"]):
        cat = "3D Printing Watch"
        rule_name = "3D Printing keywords"
    elif matches(["woodworking", "carpentry", "woodworker"]):
        cat = "Woodworking"
        rule_name = "Woodworking keywords"
    elif matches(["smart home", "home assistant", "zigbee", "z-wave", "matter"]):
        cat = "Smart Home"
        rule_name = "Smart Home keywords"
    elif matches(["dogfight", "airplane", " jet ", "f-22", "f-35", "f-16", "aviation", "aircraft"]):
        cat = "Aviation"
        rule_name = "Aviation keywords"
    elif matches(["blackstone", "griddle", "tortellini"]):
        cat = "Blackstone"
        rule_name = "Blackstone keywords"
    elif matches(["food", "cook", "recipe", "delicious", "tasty", "culinary"]):
        cat = "Food"
        rule_name = "Food keywords"
    elif matches(["gadget", "unboxing", "tech review", "hardware"]):
        cat = "Tech"
        rule_name = "Tech keywords"
    elif matches(["bigfoot", "sasquatch", "cryptid", "yeti"]):
        cat = "Bigfoot"
        rule_name = "Bigfoot keywords"
    elif matches(["v8", "engine", "horsepower", "torque", "car review", "automotive"]):
        cat = "Auto"
        rule_name = "Auto keywords"
    elif matches([" nfl ", "49ers", "touchdown", "quarterback", "super bowl"]):
        cat = "Football"
        rule_name = "Football keywords"
    elif matches(["overland", "offroad", "4x4", "overlanding"]):
        cat = "Overland"
        rule_name = "Overland keywords"
    elif matches([" dji ", "fpv drone", "mavic", "quadcopter"]):
        cat = "Drones"
        rule_name = "Drones keywords"

    if cat:
        pid = category_to_id.get(cat)
        return {
            "target_category": cat,
            "target_playlist_id": pid,
            "match_type": "keyword",
            "matched_by": rule_name,
        }

    # 3. Partial channel mapping (Lowest Priority)
    for ch_key, ch_cat in channel_map.items():
        if ch_key and ch_key.lower() in channel_lower:
            pid = category_to_id.get(ch_cat)
            return {
                "target_category": ch_cat,
                "target_playlist_id": pid,
                "match_type": "partial_channel",
                "matched_by": f"Partial channel: {ch_key}",
            }

    return {
        "target_category": None,
        "target_playlist_id": None,
        "match_type": "none",
        "matched_by": f"No rule matched for '{channel}'",
    }


def preview_watch_later_sorting(
    allow_browser: bool = False,
    driver=None,
    extra_playlists: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Generate a classification preview for all videos currently in Watch Later."""
    videos = load_watch_later_videos(allow_browser=allow_browser, driver=driver)
    channel_map, category_to_id = load_rules_and_mappings()
    if extra_playlists and isinstance(extra_playlists, dict):
        for name, pid in extra_playlists.items():
            if name and pid:
                clean_name = name.lower()
                if any(k in clean_name for k in ["to sort", "1~sort", "1sort"]) or pid == "PL7y0zeb_CORJD72rD7pNoAoWtDW5k8oSy":
                    category_to_id["1~Sort"] = pid
                else:
                    category_to_id[name] = pid

    # Always ensure 1~Sort is present as an available staging destination
    if "1~Sort" not in category_to_id:
        category_to_id["1~Sort"] = "PL7y0zeb_CORJD72rD7pNoAoWtDW5k8oSy"

    classified_items = []
    unclassified_items = []
    unmatched_channels = set()
    category_counts: Dict[str, int] = {}

    for v in videos:
        title = v["title"]
        channel = v["channel"]
        result = classify_video(title, channel, channel_map, category_to_id)

        item = {
            **v,
            "target_category": result["target_category"],
            "target_playlist_id": result["target_playlist_id"],
            "match_type": result["match_type"],
            "matched_by": result["matched_by"],
            "is_matched": bool(result["target_category"] and result["target_playlist_id"]),
        }

        if item["is_matched"]:
            classified_items.append(item)
            cat = result["target_category"]
            category_counts[cat] = category_counts.get(cat, 0) + 1
        else:
            unclassified_items.append(item)
            if channel:
                unmatched_channels.add(channel)

    # Clean up duplicate names pointing to the 1~Sort playlist id
    cleaned_categories = {}
    for cat, pid in category_to_id.items():
        if pid == "PL7y0zeb_CORJD72rD7pNoAoWtDW5k8oSy" or any(k in cat.lower() for k in ["to sort", "1~sort", "1sort"]):
            cleaned_categories["1~Sort"] = pid
        else:
            cleaned_categories[cat] = pid

    available_categories = sorted([
        {"category": cat, "playlist_id": pid}
        for cat, pid in cleaned_categories.items()
    ], key=lambda x: x["category"].lower())

    return {
        "status": "ok",
        "total_count": len(videos),
        "classified_count": len(classified_items),
        "unclassified_count": len(unclassified_items),
        "items": classified_items + unclassified_items,
        "classified_items": classified_items,
        "unclassified_items": unclassified_items,
        "category_summary": [
            {"category": cat, "count": count, "playlist_id": category_to_id.get(cat)}
            for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
        ],
        "unmatched_channels": sorted(unmatched_channels),
        "available_categories": available_categories,
    }


async def execute_auto_sort(
    items: List[Dict[str, Any]],
    yt_client: Any = None,
    remove_from_source: bool = False,
    driver: Any = None,
) -> Dict[str, Any]:
    """Execute auto-sort for specified items."""
    if not items:
        return {"status": "ok", "moved": 0, "failed": 0, "message": "No items to sort."}

    moved_count = 0
    failed_count = 0
    errors = []
    successfully_moved_ids = set()

    for item in items:
        vid = item.get("video_id") or item.get("id")
        target_pid = item.get("target_playlist_id")
        target_cat = item.get("target_category", "Unknown")
        title = item.get("title", vid)
        channel = item.get("channel", "")

        if not vid or not target_pid:
            failed_count += 1
            errors.append(f"Missing video ID or target playlist for '{title}'")
            continue

        try:
            added_via_api = False
            if yt_client and hasattr(yt_client, "add_video_to_playlist"):
                try:
                    yt_client.add_video_to_playlist(target_pid, vid)
                    added_via_api = True
                except Exception as api_err:
                    log.warning(f"API add_video_to_playlist failed for {vid} -> {target_pid}: {api_err}")

            if not added_via_api and driver:
                from core.actions import move_video
                move_video(f"https://www.youtube.com/watch?v={vid}", "Watch Later", target_cat, driver=driver)
            elif remove_from_source and driver:
                try:
                    from core.actions import move_video
                    move_video(f"https://www.youtube.com/watch?v={vid}", "Watch Later", target_cat, driver=driver)
                except Exception as b_err:
                    log.warning(f"Browser remove from WL failed for {vid}: {b_err}")

            moved_count += 1
            successfully_moved_ids.add(vid)

            try:
                from services.ai_classifier import record_move
                await record_move(
                    video_id=vid,
                    title=title,
                    channel_id="",
                    channel_title=channel,
                    from_playlist_name="Watch Later",
                    from_playlist_id="WL",
                    to_playlist_name=target_cat,
                    to_playlist_id=target_pid,
                    source="watch_later_auto_sort",
                )
            except Exception as learn_err:
                log.debug(f"Could not record AI move learning: {learn_err}")

        except Exception as e:
            failed_count += 1
            errors.append(f"Failed moving '{title}': {e}")
            log.error(f"Failed to auto-sort video {vid}: {e}")

    if successfully_moved_ids:
        for snap_path in get_all_snapshot_candidate_paths():
            if os.path.exists(snap_path):
                try:
                    with open(snap_path, "r", encoding="utf-8") as f:
                        curr = json.load(f)
                    if isinstance(curr, list):
                        updated = [
                            x for x in curr
                            if (x.get("id") or x.get("vid") or extract_video_id(x.get("url", ""))) not in successfully_moved_ids
                        ]
                        with open(snap_path, "w", encoding="utf-8") as f:
                            json.dump(updated, f, indent=2, ensure_ascii=False)
                except Exception as up_err:
                    log.warning(f"Failed updating snapshot {snap_path}: {up_err}")

    return {
        "status": "ok",
        "moved": moved_count,
        "failed": failed_count,
        "errors": errors[:10],
        "message": f"Successfully processed {moved_count} video(s) into category playlists!"
    }
