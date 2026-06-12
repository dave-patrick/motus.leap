"""YouTube integration with API-first and browser fallback."""
from __future__ import annotations

import os
from typing import Any

try:
    from googleapiclient.discovery import build  # type: ignore
    from googleapiclient.errors import HttpError  # type: ignore
except Exception:  # pragma: no cover
    build = None  # type: ignore
    HttpError = Exception  # type: ignore

from tube_manager.youtube_actions import execute as browser_execute


class YouTubeClient:
    def __init__(self, api_key: str | None = None, oauth_credentials: Any | None = None):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY", "")
        self.browser_available = False
        self._youtube = None
        if build is not None and self.api_key:
            try:
                self._youtube = build("youtube", "v3", developerKey=self.api_key, cache_discovery=False)
            except Exception:
                self._youtube = None

    # Read -----------------------------------------------------------
    def get_playlist(self, playlist_id: str) -> dict[str, Any]:
        if not self._youtube:
            return self._browser_fallback("get_playlist", {"playlist_id": playlist_id})
        return self._youtube.playlists().list(part="snippet,contentDetails", id=playlist_id).execute()

    def list_videos(self, playlist_id: str, page_token: str | None = None, max_results: int = 50) -> dict[str, Any]:
        if not self._youtube:
            return self._browser_fallback("list_videos", {"playlist_id": playlist_id, "page_token": page_token, "max_results": max_results})
        return self._youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=max_results,
            pageToken=page_token or "",
        ).execute()

    def get_video(self, video_id: str) -> dict[str, Any]:
        if not self._youtube:
            return self._browser_fallback("get_video", {"video_id": video_id})
        return self._youtube.videos().list(part="snippet,contentDetails,status", id=video_id).execute()

    def list_mine_playlists(self, max_results: int = 25, page_token: str | None = None) -> dict[str, Any]:
        if not self._youtube:
            return self._browser_fallback("list_mine_playlists", {"max_results": max_results, "page_token": page_token})
        return self._youtube.playlists().list(
            part="snippet,contentDetails",
            mine=True,
            maxResults=max_results,
            pageToken=page_token or "",
        ).execute()

    def list_mine_channels(self) -> dict[str, Any]:
        if not self._youtube:
            return self._browser_fallback("list_mine_channels", {})
        return self._youtube.channels().list(part="snippet,contentDetails", mine=True).execute()
    def watch_later(self) -> dict[str, Any]:
        if not self._youtube:
            return self._browser_fallback("watch_later", {})
        resp = self._youtube.channels().list(part="contentDetails", mine=True).execute()
        items = resp.get("items", [])
        if not items:
            return {}
        watch_later_id = items[0]["contentDetails"]["relatedPlaylists"]["watchLater"]
        return self.get_playlist(watch_later_id)

    # Write -----------------------------------------------------------
    def add_to_playlist(self, playlist_id: str, video_id: str, title: str | None = None, description: str = "") -> dict[str, Any]:
        result = browser_execute("add", {"playlist_id": playlist_id, "video_id": video_id, "title": title, "description": description})
        if result.get("action") == "playlist":
            return {"kind": "youtube#playlistItem", "snippet": {"title": title or video_id, "description": description}}
        return result

    def remove_from_playlist(self, playlist_item_id: str) -> dict[str, Any]:
        return browser_execute("remove", {"playlist_item_id": playlist_item_id})

    def create_playlist(self, title: str, description: str = "", privacy_status: str = "private") -> dict[str, Any]:
        return browser_execute("create", {"title": title, "description": description, "privacy_status": privacy_status})

    # Helpers ---------------------------------------------------------
    def _browser_fallback(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        return browser_execute(action, payload)
