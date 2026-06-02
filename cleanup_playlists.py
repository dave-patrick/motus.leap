import json
from collections import Counter
from core import move_video, remove_video_from_playlist, add_video_to_playlist, get_browser

def main():
    with open('playlists_report.json', 'r', encoding='utf-8') as f:
        report = json.load(f)
        
    driver = get_browser()
    
    try:
        # 1. Clean Music Videos
        print("--- Cleaning Music Videos ---")
        for p in report:
            if p.get('name') == 'Music Videos':
                for v in p.get('videos', []):
                    if v.get('channel') == 'The Charismatic Voice':
                        try:
                            move_video(v['url'], 'Music Videos', 'Music', driver=driver)
                            print(f"Moved Charismatic Voice video: {v['title']}")
                        except Exception as e:
                            print(f"Failed to move {v['title']}: {e}")
                            
        # 2. Clean Music (Anomalies and Duplicates)
        print("\n--- Cleaning Music ---")
        music_anomalies = ['Cleo Abram', 'Real Engineering', 'Megaprojects', 'The Origin Vault', 'Fact Quickie', 'The Sumer Codex and The Origin Vault']
        for p in report:
            if p.get('name') == 'Music':
                videos = p.get('videos', [])
                for v in videos:
                    if v.get('channel') in music_anomalies:
                        try:
                            move_video(v['url'], 'Music', 'Learning', driver=driver)
                            print(f"Moved {v['channel']} video: {v['title']}")
                        except Exception as e:
                            print(f"Failed to move {v['title']}: {e}")
                
                urls = [v['url'] for v in videos]
                dupes = [url for url, count in Counter(urls).items() if count > 1]
                for d in dupes:
                    title = next((v['title'] for v in videos if v['url'] == d), d)
                    print(f"Resolving duplicate in Music: {title}")
                    try:
                        remove_video_from_playlist(d, 'Music', driver=driver)
                        add_video_to_playlist(d, 'Music', driver=driver)
                        print(f"Fixed duplicate for {title}")
                    except Exception as e:
                        print(f"Failed duplicate fix for {title}: {e}")

        # 3. Clean Star Wars (Anomalies and Duplicates)
        print("\n--- Cleaning Star Wars ---")
        sw_anomalies = {
            'SWEROK+': 'Entertainment',
            'The Vintage Fame': 'Entertainment',
            'AppX': 'Tech',
            'Giant Freakin Robot': 'Entertainment',
            'AI Golden Age Studios': 'Entertainment',
            'Mr Sunday Movies': 'Entertainment',
            'This Is The Wayseekers': 'GX7',
            'Hoplite VFX': 'Entertainment',
            'Nerdist': 'Entertainment',
            'Rotten Tomatoes Trailers': 'Entertainment',
            'Bad Lip Reading': 'Entertainment',
            'Vanity Fair': 'Entertainment'
        }
        for p in report:
            if p.get('name') == 'Star Wars':
                videos = p.get('videos', [])
                for v in videos:
                    target_cat = sw_anomalies.get(v.get('channel'))
                    if target_cat:
                        try:
                            move_video(v['url'], 'Star Wars', target_cat, driver=driver)
                            print(f"Moved {v['channel']} video to {target_cat}: {v['title']}")
                        except Exception as e:
                            print(f"Failed to move {v['title']}: {e}")
                            
                urls = [v['url'] for v in videos]
                dupes = [url for url, count in Counter(urls).items() if count > 1]
                for d in dupes:
                    title = next((v['title'] for v in videos if v['url'] == d), d)
                    print(f"Resolving duplicate in Star Wars: {title}")
                    try:
                        remove_video_from_playlist(d, 'Star Wars', driver=driver)
                        add_video_to_playlist(d, 'Star Wars', driver=driver)
                        print(f"Fixed duplicate for {title}")
                    except Exception as e:
                        print(f"Failed duplicate fix for {title}: {e}")
                        
        print("\nCleanup Script Complete!")
    finally:
        driver.quit()

if __name__ == '__main__':
    main()
