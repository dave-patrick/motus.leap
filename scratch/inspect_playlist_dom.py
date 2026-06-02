import os
import sys
import time

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from core import get_browser

def main():
    print("Launching browser...")
    driver = get_browser()
    try:
        playlist_url = "https://www.youtube.com/playlist?list=PLNYkxOF6rcIBDSojZWBv4QJNoT4GNYzQD"
        print(f"Navigating to {playlist_url}...")
        driver.get(playlist_url)
        time.sleep(5)
        
        # Take a screenshot
        driver.save_screenshot("scratch/playlist_inspect.png")
        print("Screenshot saved to scratch/playlist_inspect.png")
        
        # Get ytd-playlist-video-renderer elements
        elements = driver.find_elements("css selector", "ytd-playlist-video-renderer")
        print(f"Found {len(elements)} ytd-playlist-video-renderer elements.")
        
        if elements:
            first_el = elements[0]
            print("\n=== Inner Text of First Element ===")
            print(first_el.text)
            
            print("\n=== Outer HTML of First Element (Truncated) ===")
            html = first_el.get_attribute("outerHTML")
            print(html[:2000])
            
            # Print text of all spans or divs inside
            print("\n=== All sub-elements text ===")
            for el in first_el.find_elements("css selector", "*"):
                tag = el.tag_name
                txt = el.text.strip()
                if txt and len(txt) < 100:
                    id_attr = el.get_attribute("id")
                    class_attr = el.get_attribute("class")
                    print(f"<{tag} id='{id_attr}' class='{class_attr}'>: {txt}")
        else:
            print("No elements found!")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
