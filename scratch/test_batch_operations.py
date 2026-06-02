import requests
import json
import time

def run_tests():
    # 1. Fetch playlists
    resp = requests.get("http://127.0.0.1:8000/api/playlists")
    assert resp.status_code == 200, f"Failed to get playlists: {resp.text}"
    playlists = resp.json()
    print(f"Total playlists: {len(playlists)}")
    
    wl_playlist = next((p for p in playlists if p["name"] == "Watch later"), None)
    if not wl_playlist:
        wl_playlist = playlists[0]
    
    target_playlist = next((p for p in playlists if p["name"] != wl_playlist["name"]), None)
    
    print(f"Source playlist: '{wl_playlist['name']}' ({wl_playlist['url']})")
    print(f"Target playlist: '{target_playlist['name']}' ({target_playlist['url']})")
    
    # 2. Live refresh videos in source playlist (this runs mock fetch because MOCK_YOUTUBE=1 is set)
    print("\nRefreshing playlist live...")
    resp = requests.get("http://127.0.0.1:8000/api/playlists/videos", params={"playlist_url": wl_playlist["url"], "refresh": "true"})
    assert resp.status_code == 200, f"Failed to refresh videos: {resp.text}"
    videos = resp.json().get("videos", [])
    print(f"Returned {len(videos)} videos after refresh.")
    assert len(videos) > 0, "No videos returned"
    
    # Let's save a couple of video URLs for testing batch operations
    video_urls_to_move = [v["url"] for v in videos[:2]]
    video_urls_to_delete = [v["url"] for v in videos[2:4]]
    print(f"URLs to move: {video_urls_to_move}")
    print(f"URLs to delete: {video_urls_to_delete}")
    
    # 3. Test Batch Move
    print("\nTesting Batch Move...")
    payload_move = {
        "video_urls": video_urls_to_move,
        "source_playlist": wl_playlist["name"],
        "target_playlist": target_playlist["name"]
    }
    resp = requests.post("http://127.0.0.1:8000/api/playlists/batch-move", json=payload_move)
    assert resp.status_code == 200, f"Batch move request failed: {resp.text}"
    print("Batch move spawned in background:", resp.json())
    
    # Wait for the background task to complete (should be fast in mock mode)
    for _ in range(15):
        time.sleep(1)
        status_resp = requests.get("http://127.0.0.1:8000/api/status")
        status = status_resp.json()
        print("Engine status:", status.get("engine_status"), "Active job:", status.get("active_job"))
        if status.get("engine_status") == "idle" and not status.get("active_job"):
            print("Batch move finished!")
            break
    else:
        raise RuntimeError("Timeout waiting for batch move to finish")
        
    # Check cache to verify videos were moved from WL to Target
    resp = requests.get("http://127.0.0.1:8000/api/playlists")
    updated_playlists = resp.json()
    wl_updated = next((p for p in updated_playlists if p["url"] == wl_playlist["url"]))
    target_updated = next((p for p in updated_playlists if p["url"] == target_playlist["url"]))
    
    wl_video_urls = [v["url"] for v in wl_updated.get("videos", [])]
    target_video_urls = [v["url"] for v in target_updated.get("videos", [])]
    
    for url in video_urls_to_move:
        assert url not in wl_video_urls, f"Video {url} should not be in source playlist after move"
        assert url in target_video_urls, f"Video {url} should be in target playlist after move"
    print("Batch Move cache updates verified successfully!")
    
    # 4. Test Batch Delete
    print("\nTesting Batch Delete...")
    payload_delete = {
        "video_urls": video_urls_to_delete,
        "playlist": wl_playlist["name"]
    }
    resp = requests.post("http://127.0.0.1:8000/api/playlists/batch-delete", json=payload_delete)
    assert resp.status_code == 200, f"Batch delete request failed: {resp.text}"
    print("Batch delete spawned in background:", resp.json())
    
    # Wait for the background task to complete
    for _ in range(15):
        time.sleep(1)
        status_resp = requests.get("http://127.0.0.1:8000/api/status")
        status = status_resp.json()
        print("Engine status:", status.get("engine_status"), "Active job:", status.get("active_job"))
        if status.get("engine_status") == "idle" and not status.get("active_job"):
            print("Batch delete finished!")
            break
    else:
        raise RuntimeError("Timeout waiting for batch delete to finish")
        
    # Check cache to verify videos were deleted
    resp = requests.get("http://127.0.0.1:8000/api/playlists")
    updated_playlists = resp.json()
    wl_updated = next((p for p in updated_playlists if p["url"] == wl_playlist["url"]))
    
    wl_video_urls = [v["url"] for v in wl_updated.get("videos", [])]
    for url in video_urls_to_delete:
        assert url not in wl_video_urls, f"Video {url} should not be in playlist after delete"
    print("Batch Delete cache updates verified successfully!")
    
    # 5. Check Log Output
    print("\nChecking logs...")
    resp = requests.get("http://127.0.0.1:8000/api/logs")
    logs = resp.json().get("logs", "")
    assert "[Batch Operation]" in logs, "Logs do not contain batch operation records"
    print("Log verification succeeded! Batch operations logged correctly.")
    
    print("\nAll tests passed successfully!")

if __name__ == "__main__":
    run_tests()
