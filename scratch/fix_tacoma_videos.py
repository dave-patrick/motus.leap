import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import core

# Load playlists_report.json
report_path = "playlists_report.json"
if not os.path.exists(report_path):
    print("playlists_report.json not found!")
    sys.exit(1)

with open(report_path, "r", encoding="utf-8") as f:
    playlists = json.load(f)

# Find all Tacoma videos not in 'Truck'
tacoma_moves = []
for p in playlists:
    p_name = p.get("name", "")
    if p_name.lower() == "truck":
        continue
    videos = p.get("videos", [])
    for v in videos:
        title = v.get("title", "")
        if "tacoma" in title.lower():
            tacoma_moves.append({
                "source": p_name,
                "title": title,
                "url": v.get("url")
            })

print(f"Found {len(tacoma_moves)} Tacoma videos to move to 'Truck':")
for idx, m in enumerate(tacoma_moves):
    print(f"{idx+1}. [{m['source']}] {m['title']} -> Truck ({m['url']})")

if not tacoma_moves:
    print("No Tacoma videos to move.")
    sys.exit(0)

# Ask for confirmation or just execute? Since this is a specialized script to do the user's task directly, we execute.
print("\nInitializing Camofox browser...")
driver = core.get_browser()
try:
    success_count = 0
    for idx, m in enumerate(tacoma_moves):
        print(f"\nMoving {idx+1}/{len(tacoma_moves)}: {m['title']} from '{m['source']}' to 'Truck'...")
        try:
            success = core.move_video(m["url"], m["source"], "Truck", driver=driver)
            if success:
                print("Move succeeded!")
                success_count += 1
            else:
                print("Move failed!")
                driver.save_screenshot(f"scratch/tacoma_fail_{idx+1}.png")
        except Exception as loop_err:
            print(f"Error moving video: {loop_err}")
            try:
                driver.save_screenshot(f"scratch/tacoma_error_{idx+1}.png")
            except: pass
            
        # Small cooldown between videos
        time.sleep(2)
            
    print(f"\nFinished: Successfully moved {success_count}/{len(tacoma_moves)} Tacoma videos to 'Truck'!")
finally:
    driver.quit()
