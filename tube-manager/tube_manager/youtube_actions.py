"""Browser fallback for YouTube write operations.

When the YouTube Data API can't perform an action (e.g. requires OAuth 
write scopes not yet configured), this module provides a browser-based 
fallback. Currently returns structured error responses indicating 
the action should be performed manually via the YouTube UI.
"""

import logging

log = logging.getLogger(__name__)


def execute(action: str, payload: dict) -> dict:
    """Execute a YouTube action via browser fallback.

    Args:
        action: The action to perform (add, remove, create, etc.)
        payload: Action parameters

    Returns:
        Dict with action result or error
    """
    log.info(f"Browser fallback called: action={action}, payload_keys={list(payload.keys())}")

    if action == "add":
        playlist_id = payload.get("playlist_id", "")
        video_id = payload.get("video_id", "")
        return {
            "action": "playlist",
            "status": "browser_fallback_required",
            "message": f"Add video {video_id} to playlist {playlist_id} requires browser action",
            "url": f"https://www.youtube.com/playlist?list={playlist_id}",
        }

    elif action == "remove":
        item_id = payload.get("playlist_item_id", "")
        return {
            "action": "remove",
            "status": "browser_fallback_required",
            "message": f"Remove playlist item {item_id} requires browser action",
        }

    elif action == "create":
        title = payload.get("title", "Untitled")
        return {
            "action": "create",
            "status": "browser_fallback_required",
            "message": f"Create playlist '{title}' requires browser action",
            "url": "https://www.youtube.com/feed/library",
        }

    elif action == "get_playlist":
        return {"items": [], "error": "browser_fallback_required"}

    elif action == "list_videos":
        return {"items": [], "error": "browser_fallback_required"}

    elif action == "list_mine_playlists":
        return {"items": [], "error": "browser_fallback_required"}

    elif action == "list_mine_channels":
        return {"items": [], "error": "browser_fallback_required"}

    elif action == "list_mine_subscriptions":
        return {"items": [], "error": "browser_fallback_required"}

    elif action == "get_video":
        return {"items": [], "error": "browser_fallback_required"}

    elif action == "watch_later":
        return {"items": [], "error": "browser_fallback_required"}

    else:
        return {"error": f"Unknown action: {action}"}
