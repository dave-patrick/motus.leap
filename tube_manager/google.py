"""YouTube integration with API-first and browser fallback."""
from __future__ import annotations

import os
import time
import json
import logging
from typing import Any

log = logging.getLogger(__name__)

try:
    from googleapiclient.discovery import build  # type: ignore
    from googleapiclient.errors import HttpError  # type: ignore
except Exception:  # pragma: no cover
    build = None  # type: ignore
    HttpError = Exception  # type: ignore

from tube_manager.youtube_actions import execute as browser_execute


class YouTubeClient:
    def __init__(
        self,
        api_key: str | None = None,
        oauth_access_token: str | None = None,
        oauth_refresh_token: str | None = None,
        oauth_client_id: str | None = None,
        oauth_client_secret: str | None = None,
        token_expiry: int | None = None,
    ):
        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY", "")
        self.oauth_access_token = oauth_access_token
        self.oauth_refresh_token = oauth_refresh_token
        self.oauth_client_id = oauth_client_id
        self.oauth_client_secret = oauth_client_secret
        self.token_expiry = token_expiry or 0

        self._youtube = None
        self._youtube_oauth = None

        # Build API key client for public operations
        if build is not None and self.api_key:
            try:
                self._youtube = build("youtube", "v3", developerKey=self.api_key, cache_discovery=False)
            except Exception:
                self._youtube = None

    def _ensure_oauth_client(self) -> bool:
        """Build OAuth-authenticated YouTube client if credentials available."""
        # Check if we have an existing OAuth client
        if self._youtube_oauth is not None:
            # Check if token needs refresh
            if time.time() >= self.token_expiry - 60:  # Refresh 60s before expiry
                return self._refresh_access_token()
            return True
        
        # No existing OAuth client - check if we have credentials
        if not self.oauth_access_token or not self.oauth_refresh_token:
            return False
            
        if build is None:
            return False
            
        # Check if access token is expired (token_expiry = 0 means never set/expired)
        if self.token_expiry <= time.time():
            log.warning("Access token expired, refreshing...")
            return self._refresh_access_token()
            
        try:
            from google.oauth2.credentials import Credentials
            creds = Credentials(
                token=self.oauth_access_token,
                refresh_token=self.oauth_refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.oauth_client_id,
                client_secret=self.oauth_client_secret,
            )
            self._youtube_oauth = build("youtube", "v3", credentials=creds, cache_discovery=False)
            return True
        except Exception as e:
            log.error(f"Failed to build OAuth client: {e}")
            self._youtube_oauth = None
            return False
    def _refresh_access_token(self) -> bool:
        """Refresh OAuth access token using refresh token."""
        if not self.oauth_refresh_token or not self.oauth_client_id or not self.oauth_client_secret:
            return False
            
        import httpx
        try:
            data = {
                "client_id": self.oauth_client_id,
                "client_secret": self.oauth_client_secret,
                "refresh_token": self.oauth_refresh_token,
                "grant_type": "refresh_token",
            }
            resp = httpx.post("https://oauth2.googleapis.com/token", data=data, timeout=30.0)
            resp.raise_for_status()
            tokens = resp.json()
            
            self.oauth_access_token = tokens.get("access_token")
            expires_in = tokens.get("expires_in", 3600)
            self.token_expiry = int(time.time()) + expires_in
            
            # Rebuild OAuth client with new token
            self._youtube_oauth = None
            return self._ensure_oauth_client()
        except Exception:
            return False

    def _get_client(self, require_oauth: bool = False):
        """Get appropriate YouTube client."""
        if require_oauth:
            if self._ensure_oauth_client():
                return self._youtube_oauth
            return None
        return self._youtube or (self._ensure_oauth_client() and self._youtube_oauth)

    # Read -----------------------------------------------------------
    def get_playlist(self, playlist_id: str) -> dict[str, Any]:
        client = self._get_client()
        if not client:
            return self._browser_fallback("get_playlist", {"playlist_id": playlist_id})
        return client.playlists().list(part="snippet,contentDetails", id=playlist_id).execute()

    def list_videos(self, playlist_id: str, page_token: str | None = None, max_results: int = 50) -> dict[str, Any]:
        client = self._get_client()
        if not client:
            return self._browser_fallback("list_videos", {"playlist_id": playlist_id, "page_token": page_token, "max_results": max_results})
        return client.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=max_results,
            pageToken=page_token or "",
        ).execute()

    def get_video(self, video_id: str) -> dict[str, Any]:
        client = self._get_client()
        if not client:
            return self._browser_fallback("get_video", {"video_id": video_id})
        return client.videos().list(part="snippet,contentDetails,status", id=video_id).execute()

    def list_mine_playlists(self, max_results: int = 25, page_token: str | None = None) -> dict[str, Any]:
        """List user's playlists (requires OAuth)."""
        client = self._get_client(require_oauth=True)
        if not client:
            return self._browser_fallback("list_mine_playlists", {"max_results": max_results, "page_token": page_token})
        return client.playlists().list(
            part="snippet,contentDetails",
            mine=True,
            maxResults=max_results,
            pageToken=page_token or "",
        ).execute()

    def list_mine_channels(self) -> dict[str, Any]:
        """List user's channels (requires OAuth)."""
        client = self._get_client(require_oauth=True)
        if not client:
            return self._browser_fallback("list_mine_channels", {})
        return client.channels().list(part="snippet,contentDetails", mine=True).execute()

    def list_mine_subscriptions(self, max_results: int = 25, page_token: str | None = None) -> dict[str, Any]:
        """List user's subscriptions (requires OAuth)."""
        client = self._get_client(require_oauth=True)
        if not client:
            return self._browser_fallback("list_mine_subscriptions", {"max_results": max_results, "page_token": page_token})
        return client.subscriptions().list(
            part="snippet,contentDetails",
            mine=True,
            maxResults=max_results,
            pageToken=page_token or "",
        ).execute()

    def watch_later(self) -> dict[str, Any]:
        """Get Watch Later playlist (requires OAuth)."""
        client = self._get_client(require_oauth=True)
        if not client:
            return self._browser_fallback("watch_later", {})
        resp = client.channels().list(part="contentDetails", mine=True).execute()
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