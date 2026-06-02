import json
import os
import sys
import time

# Ensure current directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core import get_browser, move_video

def mass_move_multiple(moves_list):
    report_path = 'playlists_report.json'
    if not os.path.exists(report_path):
        print(f"Error: {report_path} not found. Run 'scan' first.")
        return
        
    with open(report_path, 'r', encoding='utf-8') as f:
        playlists = json.load(f)
        
    driver = get_browser()
    try:
        for channel_name, target_playlist_name in moves_list:
            print(f"\n=== Processing Channel: {channel_name} -> {target_playlist_name} ===")
            
            to_move = []
            for p in playlists:
                if p['name'].lower() == target_playlist_name.lower():
                    continue
                for v in p['videos']:
                    if v['channel'] == channel_name:
                        to_move.append({
                            'title': v['title'],
                            'url': v['url'],
                            'source_name': p['name']
                        })
            
            if not to_move:
                print(f"No videos found for '{channel_name}' to move.")
                continue
                
            print(f"Found {len(to_move)} videos to move.")
            
            for i, item in enumerate(to_move, 1):
                print(f"[{i}/{len(to_move)}] Moving '{item['title']}' from '{item['source_name']}'...")
                try:
                    move_video(item['url'], item['source_name'], target_playlist_name, driver=driver)
                except Exception as e:
                    print(f"  Error: {e}")
                time.sleep(1)
    finally:
        driver.quit()

if __name__ == "__main__":
    tasks = [
        ("Uncle Jessy", "3D Printing Watch"),
        ("The Next Layer", "3D Printing Watch"),
        ("LRN2DIY", "Home Improvement")
    ]
    mass_move_multiple(tasks)
