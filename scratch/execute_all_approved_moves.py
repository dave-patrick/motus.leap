import json
import os
import sys
import time

# Ensure current directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import get_browser, move_video
from cli import parse_rules

def execute_approved_moves():
    report_path = 'playlists_report.json'
    if not os.path.exists(report_path):
        print(f"Error: {report_path} not found. Run 'scan' first.")
        return
        
    with open(report_path, 'r', encoding='utf-8') as f:
        playlists = json.load(f)
        
    channel_map, category_to_id = parse_rules()
    
    to_move = []
    
    # 1. Rules for approved moves
    for p in playlists:
        p_name = p['name']
        for v in p['videos']:
            title = v['title']
            channel = v['channel']
            title_lower = title.lower()
            url = v['url']
            
            target_cat = None
            
            # Star Wars (Skip if already in Star Wars)
            if p_name.lower() != "star wars":
                if channel_map.get(channel) == "Star Wars" or \
                   any(k in title_lower for k in ["star wars", "vader", "kenobi", " darth ", " jedi "]):
                    # Double check for false positives like LotR
                    if "lord of the rings" not in title_lower and "game of thrones" not in title_lower:
                        target_cat = "Star Wars"
            
            # Arizona (Skip if already in Arizona)
            if not target_cat and p_name.lower() != "arizona":
                if "arizona" in title_lower:
                    target_cat = "Arizona"
                    
            # The Charismatic Voice -> Music (Skip if already in Music)
            if not target_cat and p_name.lower() != "music":
                if channel == "The Charismatic Voice":
                    target_cat = "Music"
            
            # Channel Mappings (Uncle Jessy, etc.)
            if not target_cat:
                mapped_cat = channel_map.get(channel)
                if mapped_cat and mapped_cat in ["3D Printing Watch", "Home Improvement", "Woodworking"]:
                    if p_name.lower() != mapped_cat.lower():
                        target_cat = mapped_cat

            if target_cat:
                to_move.append({
                    'title': title,
                    'url': url,
                    'source': p_name,
                    'target': target_cat
                })
                
    if not to_move:
        print("No approved moves found.")
        return
        
    print(f"Found {len(to_move)} approved moves.")
    
    driver = get_browser()
    try:
        for i, item in enumerate(to_move, 1):
            print(f"[{i}/{len(to_move)}] Moving '{item['title']}' from '{item['source']}' to '{item['target']}'...")
            try:
                # Note: core.move_video(video_url, source_playlist_name, target_playlist_name, driver=None)
                move_video(item['url'], item['source'], item['target'], driver=driver)
            except Exception as e:
                print(f"  Error: {e}")
            time.sleep(1)
    finally:
        driver.quit()

if __name__ == "__main__":
    execute_approved_moves()
