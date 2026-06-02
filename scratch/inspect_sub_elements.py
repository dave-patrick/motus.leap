import os
import sys
import time

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from core import get_browser
from selenium.webdriver.common.by import By

def main():
    print("Launching browser...")
    driver = get_browser()
    try:
        playlist_url = "https://www.youtube.com/playlist?list=PLNYkxOF6rcIBDSojZWBv4QJNoT4GNYzQD"
        print(f"Navigating to {playlist_url}...")
        driver.get(playlist_url)
        time.sleep(5)
        
        elements = driver.find_elements(By.CSS_SELECTOR, "ytd-playlist-video-renderer")
        print(f"Found {len(elements)} ytd-playlist-video-renderer elements.")
        
        if elements:
            first_el = elements[0]
            print("\n=== Inner Text ===")
            print(repr(first_el.text))
            
            print("\n=== Finding all sub elements ===")
            # Use JS to query all elements and get their tagName, id, className, and innerText
            res = driver.execute_script("""
                let el = arguments[0];
                let desc = [];
                let all = el.querySelectorAll('*');
                for (let i = 0; i < all.length; i++) {
                    let sub = all[i];
                    let text = sub.innerText ? sub.innerText.trim() : "";
                    // Only log leaf-like nodes or nodes with short text to avoid giant nested text
                    if (text && text.length < 150) {
                        desc.push({
                            index: i,
                            tag: sub.tagName,
                            id: sub.id,
                            className: sub.className,
                            text: text
                        });
                    }
                }
                return desc;
            """, first_el)
            
            for item in res:
                print(f"[{item['index']}] <{item['tag']}> id='{item['id']}' class='{item['className']}': {repr(item['text'])}")
        else:
            print("No elements found!")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
