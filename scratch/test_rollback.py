import os
import sys
import time
import json
import threading
import requests
from unittest.mock import patch, MagicMock

# Add parent directory to sys.path to import server.py and apply_maintenance.py
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

# Set mock environment variable
os.environ["MOCK_YOUTUBE"] = "1"

# Path to maintenance history
HISTORY_PATH = os.path.join(parent_dir, "maintenance_history.json")
SETTINGS_PATH = os.path.join(parent_dir, "settings.json")

def setup_settings():
    # If settings.json does not exist, create a dummy one for testing
    settings_existed = os.path.exists(SETTINGS_PATH)
    old_content = None
    if settings_existed:
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                old_content = f.read()
        except: pass
    
    dummy_settings = {
        "gemini_api_key": "dummy_key",
        "notification_webhook": "https://discord.com/api/webhooks/dummy_id/dummy_token"
    }
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(dummy_settings, f)
        
    return settings_existed, old_content

def restore_settings(settings_existed, old_content):
    if settings_existed and old_content is not None:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            f.write(old_content)
    elif os.path.exists(SETTINGS_PATH):
        try:
            os.remove(SETTINGS_PATH)
        except: pass

def run_server():
    import uvicorn
    from server import app
    # Run uvicorn server in a way that allows stopping it programmatically or exits when thread dies
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

def main():
    print("--- YouTube Playlist Agent: Rollback & Webhook Verification Test ---")
    
    # 1. Verify Discord Webhook Report Generation
    print("\n1. Verifying Discord Webhook Notification payload...")
    settings_existed, old_settings = setup_settings()
    
    from apply_maintenance import send_discord_history_report
    
    test_action = {
        "action_id": "test_act_123",
        "type": "MISPLACED",
        "title": "Star Wars Lore Video",
        "vid": "sW12345",
        "from": ["Learning"],
        "to": "Star Wars"
    }
    
    with patch("requests.post") as mock_post:
        # Call the function
        send_discord_history_report([test_action])
        
        # Verify it attempted to send to the dummy webhook
        if mock_post.called:
            print("✓ requests.post was called to send the Discord report.")
            call_args = mock_post.call_args
            url = call_args[0][0]
            kwargs = call_args[1]
            payload = kwargs.get("json", {})
            
            print(f"  Target URL: {url}")
            print(f"  Message: {payload.get('content')}")
            embeds = payload.get("embeds", [])
            print(f"  Number of embeds: {len(embeds)}")
            if embeds:
                embed = embeds[0]
                print(f"  Embed Title: {embed.get('title')}")
                print(f"  Embed URL: {embed.get('url')}")
                print(f"  Embed Description:\n{embed.get('description')}")
                
                # Check for rollback URL
                rollback_url = "http://127.0.0.1:8000/api/maintenance/rollback?action_id=test_act_123"
                if rollback_url in embed.get('description', ''):
                    print("✓ Rollback URL is correctly embedded in the Discord notification!")
                else:
                    print("   Rollback URL is missing or incorrect in the embed!")
                    sys.exit(1)
            else:
                print("✗ No embeds found in the payload!")
                sys.exit(1)
        else:
            print("✗ requests.post was NOT called! Is the webhook URL missing or settings.json incorrect?")
            sys.exit(1)
            
    # Clean up settings
    restore_settings(settings_existed, old_settings)
    
    # 2. Setup Dummy Action in history
    print("\n2. Writing dummy action to maintenance_history.json...")
    
    dummy_history = [
        {
            "action_id": "dummy_action_xxx",
            "timestamp": "2026-05-20 14:00:00",
            "type": "MISPLACED",
            "title": "How to 3D Print",
            "vid": "3dp999",
            "from": ["Learning"],
            "to": "3D Printing Watch"
        }
    ]
    
    # Backup original history if any
    history_existed = os.path.exists(HISTORY_PATH)
    old_history = None
    if history_existed:
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                old_history = f.read()
        except: pass
        
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(dummy_history, f, indent=2, ensure_ascii=False)
    print("✓ Dummy history entry created.")
    
    # 3. Start local server
    print("\n3. Starting local FastAPI server on http://127.0.0.1:8000 ...")
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait for server to boot
    time.sleep(2.5)
    
    # 4. Make rollback GET request
    print("\n4. Sending GET request to rollback endpoint...")
    rollback_endpoint = "http://127.0.0.1:8000/api/maintenance/rollback?action_id=dummy_action_xxx"
    try:
        response = requests.get(rollback_endpoint, timeout=10)
        print(f"  Response status code: {response.status_code}")
        
        # Verify the HTML response contains "Rollback Complete" or similar
        if response.status_code == 200 and "Rollback Complete" in response.text:
            print("✓ Rollback response indicates success!")
        else:
            print(f"✗ Rollback endpoint returned error or unexpected HTML: {response.text[:200]}")
            # Clean up before exit
            if history_existed and old_history is not None:
                with open(HISTORY_PATH, "w", encoding="utf-8") as f:
                    f.write(old_history)
            else:
                if os.path.exists(HISTORY_PATH): os.remove(HISTORY_PATH)
            sys.exit(1)
            
    except Exception as e:
        print(f"✗ Failed to connect or request rollback: {e}")
        if history_existed and old_history is not None:
            with open(HISTORY_PATH, "w", encoding="utf-8") as f:
                f.write(old_history)
        else:
            if os.path.exists(HISTORY_PATH): os.remove(HISTORY_PATH)
        sys.exit(1)
        
    # 5. Verify database state & history cleaning
    print("\n5. Verifying that the history is cleaned...")
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                current_history = json.load(f)
            
            # Check if our action_id is gone
            action_present = any(a.get("action_id") == "dummy_action_xxx" for a in current_history)
            if not action_present:
                print("✓ Success! Action 'dummy_action_xxx' has been removed from maintenance_history.json.")
            else:
                print("✗ Failure! Action 'dummy_action_xxx' is still present in history.")
                sys.exit(1)
        except Exception as e:
            print(f"✗ Error reading/parsing history after rollback: {e}")
            sys.exit(1)
    else:
        print("✓ History file not found or cleared.")
        
    # Restore original history if it existed
    if history_existed and old_history is not None:
        with open(HISTORY_PATH, "w", encoding="utf-8") as f:
            f.write(old_history)
        print("✓ Restored original maintenance history.")
    else:
        if os.path.exists(HISTORY_PATH):
            try:
                os.remove(HISTORY_PATH)
                print("✓ Removed temporary maintenance_history.json.")
            except: pass
            
    print("\nAll tests completed successfully!")

if __name__ == "__main__":
    main()
