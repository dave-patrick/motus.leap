import json
import os

def deduplicate_report():
    report_path = "playlists_report.json"
    if not os.path.exists(report_path):
        print("playlists_report.json not found.")
        return
        
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
        
    print(f"Total items in original report: {len(report)}")
    
    # Deduplicate by URL
    deduped = {}
    for p in report:
        url = p.get("url")
        if not url:
            continue
        
        # Normalize/clean URL to prevent matching issues
        clean_url = url
        if "list=" in url:
            clean_url = "https://www.youtube.com/playlist?list=" + url.split("list=")[1].split("&")[0]
            
        if clean_url in deduped:
            existing = deduped[clean_url]
            existing_videos = existing.get("videos", [])
            p_videos = p.get("videos", [])
            
            # Count videos with non-null/non-empty published dates
            existing_pub_count = sum(1 for v in existing_videos if v.get("published"))
            p_pub_count = sum(1 for v in p_videos if v.get("published"))
            
            # Decide which one to keep:
            # 1. Prefer the one with more published dates
            # 2. If equal, prefer the one with more videos
            # 3. If equal, keep existing
            if p_pub_count > existing_pub_count:
                deduped[clean_url] = p
            elif p_pub_count == existing_pub_count and len(p_videos) > len(existing_videos):
                deduped[clean_url] = p
        else:
            deduped[clean_url] = p
            
    new_report = list(deduped.values())
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(new_report, f, indent=2, ensure_ascii=False)
        
    print(f"Successfully deduplicated report from {len(report)} to {len(new_report)} entries.")

if __name__ == "__main__":
    deduplicate_report()
