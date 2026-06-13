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
    import httplib2  # type: ignore
except Exception:  # pragma: no cover
    build = None  # type: ignore
    HttpError = Exception  # type: ignore
    httplib2 = None  # type: ignore


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

        if build is not None and self.api_key:
            try:
                http = httplib2.Http(timeout=30) if httplib2 else None
                self._youtube = build("youtube", "v3", developerKey=self.api_key, cache_discovery=False, http=http)
            except Exception:
                self._youtube = None

    def _ensure_oauth_client(self) -> bool:
        if self._youtube_oauth is not None:
            if time.time() >= self.token_expiry - 60:
                return self._refresh_access_token()
            return True

        if not self.oauth_access_token or not self.oauth_refresh_token:
            return False

        if build is None:
            return False

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
            http = httplib2.Http(timeout=30) if httplib2 else None
            self._youtube_oauth = build("youtube", "v3", credentials=creds, cache_discovery=False, http=http)
            return True
        except Exception as e:
            log.error(f"Failed to build OAuth client: {e}")
            self._youtube_oauth = None
            return False

    def _refresh_access_token(self) -> bool:
        if not self.oauth_refresh_token or not self.oauth_client_id or not self.oauth_client_secret:
            return False

        try:
            import httpx
        except ImportError:
            return False

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

            self._youtube_oauth = None
            return self._ensure_oauth_client()
        except Exception:
            return False

    def _get_client(self, require_oauth: bool = False):
        if require_oauth:
            if self._ensure_oauth_client():
                return self._youtube_oauth
            return None
        return self._youtube or (self._ensure_oauth_client() and self._youtube_oauth)

    def get_playlist(self, playlist_id: str) -> dict[str, Any]:
        client = self._get_client()
        if not client:
            return {}
        return client.playlists().list(part="snippet,contentDetails", id=playlist_id).execute()

    def list_videos(self, playlist_id: str, page_token: str | None = None, max_results: int = 50) -> dict[str, Any]:
        client = self._get_client()
        if not client:
            return {"items": []}
        try:
            return client.playlistItems().list(
                part="snippet,contentDetails",
                playlistId=playlist_id,
                maxResults=max_results,
                pageToken=page_token or "",
            ).execute()
        except HttpError as e:
            status_code = e.resp.status if hasattr(e, "resp") and e.resp else "unknown"
            error_content = e.content.decode("utf-8") if hasattr(e, "content") and e.content else "no content"
            error_reason = "unknown"
            try:
                error_data = json.loads(error_content)
                error_reason = error_data.get("error", {}).get("errors", [{}])[0].get("reason", "unknown")
            except Exception:
                pass
            log.error(f"YouTube API error in list_videos (playlist={playlist_id}): status={status_code}, reason={error_reason}, content={error_content[:500]}")
            raise

    def get_video(self, video_id: str) -> dict[str, Any]:
        client = self._get_client()
        if not client:
            return {}
        return client.videos().list(part="snippet,contentDetails,status", id=video_id).execute()

    def list_mine_playlists(self, max_results: int = 25, page_token: str | None = None) -> dict[str, Any]:
        client = self._get_client(require_oauth=True)
        if not client:
            return {"items": []}
        return client.playlists().list(
            part="snippet,contentDetails",
            mine=True,
            maxResults=max_results,
            pageToken=page_token or "",
        ).execute()

    def list_mine_channels(self) -> dict[str, Any]:
        client = self._get_client(require_oauth=True)
        if not client:
            return {}
        return client.channels().list(part="snippet,contentDetails", mine=True).execute()

    def list_mine_subscriptions(self, max_results: int = 25, page_token: str | None = None) -> dict[str, Any]:
        client = self._get_client(require_oauth=True)
        if not client:
            return {"items": []}
        return client.subscriptions().list(
            part="snippet,contentDetails",
            mine=True,
            maxResults=max_results,
            pageToken=page_token or "",
        ).execute()

    def list_channels_by_ids(self, ids: list[str], max_results: int = 50) -> dict[str, Any]:
        client = self._get_client(require_oauth=False)
        if not client:
            return {"items": []}
        return client.channels().list(
            part="snippet,statistics",
            id=",".join(ids[:max_results]) if ids else "",
            maxResults=max_results,
        ).execute()

    def watch_later(self) -> dict[str, Any]:
        client = self._get_client(require_oauth=True)
        if not client:
            return {}
        resp = client.channels().list(part="contentDetails", mine=True).execute()
        items = resp.get("items", [])
        if not items:
            return {}
        watch_later_id = items[0]["contentDetails"]["relatedPlaylists"]["watchLater"]
        return self.get_playlist(watch_later_id)