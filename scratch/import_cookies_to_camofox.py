import os
import sys
import requests
import json

# Insert project path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import scratch.decrypt_chrome_cookies as decryptor

def import_cookies():
    print("Decrypting cookies from Chrome user_data profile...")
    cookies = decryptor.get_cookies()
    if not cookies:
        print("No cookies decrypted!")
        return False
        
    print(f"Decrypted {len(cookies)} cookies total.")
    
    # Filter only relevant domains to prevent hitting payload/cookie size limits
    # e.g., google.com, youtube.com
    relevant_domains = ["google.com", "youtube.com"]
    filtered_cookies = []
    for c in cookies:
        domain = c.get("domain", "")
        if any(d in domain for d in relevant_domains):
            filtered_cookies.append(c)
            
    print(f"Filtered to {len(filtered_cookies)} Google/YouTube cookies.")
    
    # POST to Camofox API
    url = "http://localhost:9377/sessions/youtube_playlist_agent_default/cookies"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer my_secret_cookie_key"
    }
    payload = {
        "cookies": filtered_cookies
    }
    
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        print("Server Response Status:", r.status_code)
        print("Server Response Body:", r.text)
        if r.status_code == 200:
            print("Successfully imported cookies into Camofox session!")
            return True
        else:
            print("Failed to import cookies.")
            return False
    except Exception as e:
        print("Error POSTing cookies:", e)
        return False

if __name__ == "__main__":
    import_cookies()
