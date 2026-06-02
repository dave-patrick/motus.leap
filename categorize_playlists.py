import json
from core import get_all_playlists, list_videos_in_playlist

CATEGORIES = {
    "Music": ["music", "concerts", "songs", "soundtrack", "ost", "mix", "lofi", "playlist", "beats"],
    "Tech & Dev": ["code", "programming", "python", "javascript", "tech", "development", "lessons", "tutorial", "dev", "software", "linux"],
    "Gaming": ["game", "gameplay", "walkthrough", "playthrough", "xbox", "playstation", "nintendo"],
    "Automotive & Aviation": ["auto", "cars", "aviation", "planes", "flight", "pilot", "driving", "racing", "truck"],
    "Travel & Vlog": ["travel", "vlog", "arizona", "trip", "vacation", "explore"],
    "Education & Docs": ["documentary", "history", "science", "learn", "course", "how to"],
    "Entertainment": ["comedy", "funny", "meme", "clips", "movies", "trailers", "show"],
    "News & Politics": ["news", "politics", "debate"],
    "Sports": ["sports", "football", "basketball", "nba", "nfl", "soccer", "highlights"]
}

def guess_category(text: str) -> str:
    text = text.lower()
    for cat, keywords in CATEGORIES.items():
        if any(kw in text for kw in keywords):
            return cat
    return None

def main():
    print("Fetching all playlists for categorization...")
    playlists = get_all_playlists()
    print(f"Found {len(playlists)} playlists. Categorizing...")
    
    categorized = []
    
    for p in playlists:
        name = p["name"]
        cat = guess_category(name)
        
        if not cat:
            print(f"Unsure about '{name}'. Fetching video content to check...")
            try:
                videos = list_videos_in_playlist(p["url"])
                # Check up to 5 videos for clues
                video_titles = " ".join([v["title"] for v in videos[:5]])
                cat = guess_category(video_titles)
            except Exception as e:
                print(f"  Failed to fetch videos for {name}: {e}")
                
        if not cat:
            cat = "Miscellaneous"
            
        p["category"] = cat
        categorized.append(p)
        print(f"[{cat}] {name}")
        
    with open("categorized_playlists.json", "w", encoding="utf-8") as f:
        json.dump(categorized, f, indent=2, ensure_ascii=False)
        
    print("Categorization complete! Saved to categorized_playlists.json")

if __name__ == "__main__":
    main()
