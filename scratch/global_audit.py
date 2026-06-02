import json
import os
import sys

# Ensure current directory is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cli import parse_rules

def audit_playlists(target_categories=["Star Wars", "Learning"]):
    report_path = 'playlists_report.json'
    if not os.path.exists(report_path):
        print(f"Error: {report_path} not found. Run 'scan' first.")
        return
        
    with open(report_path, 'r', encoding='utf-8') as f:
        playlists = json.load(f)
        
    channel_map, category_to_id = parse_rules()
    
    # Map target categories to their playlist names in the report
    # The rules file column 2 is the 'Category Name' used in the report/logic
    category_to_playlist_name = {cat: cat for cat in category_to_id.keys()}
    
    findings = {cat: [] for cat in target_categories + ["Arizona", "Music"]}
    
    for p in playlists:
        p_name = p['name']
        for v in p['videos']:
            title = v['title']
            channel = v['channel']
            title_lower = title.lower()
            
            detected_cat = None
            
            # Star Wars
            if "Star Wars" in target_categories:
                if channel_map.get(channel) == "Star Wars" or \
                   any(k in title_lower for k in ["star wars", "vader", "kenobi", " darth ", " jedi "]):
                    detected_cat = "Star Wars"
            
            # Learning
            if "Learning" in target_categories and not detected_cat:
                if channel_map.get(channel) == "Learning" or \
                   any(k in title_lower for k in ["science", "history", "documentary", "explained", "how it works"]):
                    detected_cat = "Learning"
            
            # Arizona
            if not detected_cat and "arizona" in title_lower:
                detected_cat = "Arizona"
                
            # The Charismatic Voice -> Music
            if not detected_cat and channel == "The Charismatic Voice":
                detected_cat = "Music"
            
            if detected_cat and p_name.lower() != detected_cat.lower():
                findings[detected_cat].append({
                    'title': title,
                    'channel': channel,
                    'current_playlist': p_name,
                    'url': v['url']
                })
                
    print("\n=== Global Audit Results ===")
    for cat, items in findings.items():
        print(f"\nCategory: {cat} ({len(items)} items found elsewhere)")
        for i, item in enumerate(items[:10], 1):
            print(f"  {i}. {item['title']} (In: {item['current_playlist']})")
        if len(items) > 10:
            print(f"  ... and {len(items) - 10} more.")

if __name__ == "__main__":
    audit_playlists()
