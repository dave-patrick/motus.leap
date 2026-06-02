import os
import sys
import re
import json

def main():
    html_path = "scratch/playlist_page.html"
    if not os.path.exists(html_path):
        print("HTML file not found.")
        return
        
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    print(f"File size: {len(content)} bytes")
    
    # Check for continuation item renderer
    continuations = re.findall(r'<ytd-continuation-item-renderer[^>]*>', content)
    print(f"Found {len(continuations)} ytd-continuation-item-renderer tags in source.")
    
    # Let's search for "ytInitialData"
    # YouTube embeds the video list in ytInitialData JSON
    m = re.search(r'var ytInitialData\s*=\s*(\{.*?\});', content)
    if not m:
        m = re.search(r'window\["ytInitialData"\]\s*=\s*(\{.*?\});', content)
        
    if m:
        json_str = m.group(1)
        print(f"Found ytInitialData JSON! Length: {len(json_str)}")
        # Let's count how many video URLs are inside it
        urls = re.findall(r'"videoId"\s*:\s*"([^"]+)"', json_str)
        unique_urls = set(urls)
        print(f"Found {len(urls)} videoId references in ytInitialData ({len(unique_urls)} unique).")
    else:
        print("Did not find ytInitialData in page source.")
        
    # Let's search for how many video renderers are in the raw HTML
    renderers = re.findall(r'<ytd-playlist-video-renderer', content)
    print(f"Found {len(renderers)} raw ytd-playlist-video-renderer tags in HTML.")

if __name__ == "__main__":
    main()
