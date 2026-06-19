from __future__ import annotations

import os
import time
import json
import logging
from typing import Any

log = logging.getLogger(__name__)

# Retry configuration
RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5

try:
    from googleapiclient.discovery import build  # type: ignore
    from googleapiclient.errors import HttpError  # type: ignore
    import httplib2  # type: ignore
except Exception:  # pragma: no cover
    build = None  # type: ignore
    HttpError = Exception  # type: ignore
    httplib2 = None  # type: ignore

try:
    import httpx
except Exception:  # pragma: no cover
    httpx = None  # type: ignore

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

if httpx is not None:
    _shared_client = httpx.Client(timeout=45.0)  # reuse connections across calls
else:  # pragma: no cover
    _shared_client = None  # type: ignore


def _with_retry(sync_func, *args, **kwargs):
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return sync_func(*args, **kwargs)
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            if attempt < RETRY_ATTEMPTS - 1:
                log.warning(f"API call failed (attempt {attempt + 1}/{RETRY_ATTEMPTS}): {e}. Retrying in {RETRY_DELAY_SECONDS} seconds...")
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                log.error(f"API call failed after {RETRY_ATTEMPTS} attempts: {e}")
                raise


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
            log.debug("[YOUTUBE] _ensure_oauth_client: missing access_token or refresh_token")
            return False

        if build is None:
            log.debug("[YOUTUBE] _ensure_oauth_client: googleapiclient not available")
            return False

        if self.token_expiry <= time.time():
            log.warning("[YOUTUBE] _ensure_oauth_client: access token expired, refreshing...")
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
            log.info("[YOUTUBE] _ensure_oauth_client: OAuth client built successfully")
            return True
        except Exception as e:
            log.error(f"[YOUTUBE] _ensure_oauth_client: Failed to build OAuth client: {e}")
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
            client = _shared_client or httpx.Client(timeout=45.0)
            resp = _with_retry(client.post, "https://oauth2.googleapis.com/token", data=data)
            resp.raise_for_status()
            tokens = resp.json()

            self.oauth_access_token = tokens.get("access_token")
            expires_in = tokens.get("expires_in", 3600)
            self.token_expiry = int(time.time()) + expires_in

            # Persist refreshed tokens so they survive app restarts
            try:
                from app import config_manager as app_config_manager
                cfg = app_config_manager.config
                cfg.oauth.access_token = self.oauth_access_token
                cfg.oauth.token_expiry = self.token_expiry
                app_config_manager.save(cfg)
            except Exception:
                pass

            self._youtube_oauth = None
            return self._ensure_oauth_client()
        except Exception:
            return False

    def _get_client(self, require_oauth: bool = False):
        if require_oauth:
            if self._ensure_oauth_client():
                return self._youtube_oauth
            return None
        # Prefer OAuth client if authenticated; fall back to API Key client
        if self._ensure_oauth_client():
            return self._youtube_oauth
        return self._youtube

    def _oauth_request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """Make an OAuth-authenticated request to the YouTube Data API via httpx.

        This bypasses googleapiclient for OAuth-required endpoints where the
        library was observed to return empty results despite the API returning
        data for the same token.
        """
        if httpx is None:
            raise RuntimeError("httpx is not installed")
        access_token = self.oauth_access_token
        if not access_token:
            raise RuntimeError("No OAuth access token available")
        if time.time() >= self.token_expiry - 60:
            if not self._refresh_access_token():
                raise RuntimeError("OAuth token refresh failed")
            access_token = self.oauth_access_token
        url = f"{YOUTUBE_API_BASE}/{endpoint}"
        headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        log.debug(f"[YOUTUBE] _oauth_request GET {url} params={params}")
        client = _shared_client or httpx.Client(timeout=45.0)
        resp = _with_retry(client.get, url, headers=headers, params=params)
        log.debug(f"[YOUTUBE] _oauth_request response status={resp.status_code}")
        resp.raise_for_status()
        return resp.json()

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
                pageToken=page_token or None,
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
        if not self.oauth_access_token or not self.oauth_refresh_token:
            log.error("[YOUTUBE] list_mine_playlists: no OAuth tokens available")
            return {"items": []}
        try:
            params = {"part": "snippet,contentDetails", "mine": "true", "maxResults": max_results}
            if page_token:
                params["pageToken"] = page_token
            resp = self._oauth_request("playlists", params)
            log.info(f"[YOUTUBE] list_mine_playlists returned {len(resp.get('items', []))} items")
            return resp
        except Exception as e:
            log.error(f"[YOUTUBE] list_mine_playlists error: {e}")
            raise

    def list_mine_channels(self) -> dict[str, Any]:
        if not self.oauth_access_token or not self.oauth_refresh_token:
            return {}
        try:
            return self._oauth_request("channels", {"part": "snippet,contentDetails", "mine": "true"})
        except Exception as e:
            log.error(f"[YOUTUBE] list_mine_channels error: {e}")
            return {}

    def list_mine_subscriptions(self, max_results: int = 25, page_token: str | None = None) -> dict[str, Any]:
        if not self.oauth_access_token or not self.oauth_refresh_token:
            return {"items": []}
        try:
            params = {"part": "snippet,contentDetails", "mine": "true", "maxResults": max_results}
            if page_token:
                params["pageToken"] = page_token
            return self._oauth_request("subscriptions", params)
        except Exception as e:
            log.error(f"[YOUTUBE] list_mine_subscriptions error: {e}")
            return {"items": []}

    def list_channels_by_ids(self, ids: list[str], max_results: int = 50) -> dict[str, Any]:
        client = self._get_client(require_oauth=False)
        if not client or not ids:
            return {"items": []}

        max_results = min(max_results, 50)
        all_items = []
        for start in range(0, len(ids), max_results):
            batch = ids[start : start + max_results]
            response = client.channels().list(
                part="snippet,statistics",
                id=",".join(batch),
                maxResults=max_results,
            ).execute()
            all_items.extend(response.get("items", []))

        return {"items": all_items}

    def _get_watch_later_id(self, items: list[dict[str, Any]]) -> str | None:
        if not items:
            return None
        related = items[0].get("contentDetails", {}).get("relatedPlaylists", {})
        watch_later_id = related.get("watchLater")
        if watch_later_id:
            return watch_later_id
            
        log.info("[YOUTUBE] Native watchLater playlist not found (standard YouTube API limitation). Searching user playlists as fallback...")
        try:
            pl_resp = self.list_mine_playlists(max_results=50)
            pl_items = pl_resp.get("items", [])
            target_titles = {"watch later", "watchlater", "queue", "sync queue", "wl", "sort", "1~sort", "triage"}
            for pl in pl_items:
                title = pl.get("snippet", {}).get("title", "").strip().lower()
                if title in target_titles:
                    wlid = pl.get("id")
                    log.info(f"[YOUTUBE] Found fallback watch later playlist: '{pl.get('snippet', {}).get('title')}' ({wlid})")
                    return wlid
        except Exception as e:
            log.error(f"[YOUTUBE] Failed to search for fallback watch later playlist: {e}")
            
        return None

    def watch_later(self) -> dict[str, Any]:
        if not self.oauth_access_token or not self.oauth_refresh_token:
            return {}
        try:
            resp = self._oauth_request("channels", {"part": "contentDetails", "mine": "true"})
            items = resp.get("items", [])
            watch_later_id = self._get_watch_later_id(items)
            if not watch_later_id:
                return {}
            return self.get_playlist(watch_later_id)
        except Exception as e:
            log.error(f"[YOUTUBE] watch_later error: {e}")
            return {}

    def list_watch_later_items(self, max_results: int = 50, page_token: str | None = None, playlist_id: str | None = None) -> dict[str, Any]:
        if not self.oauth_access_token or not self.oauth_refresh_token:
            return {"items": []}
        try:
            if playlist_id:
                watch_later_id = playlist_id
            else:
                resp = self._oauth_request("channels", {"part": "contentDetails", "mine": "true"})
                items = resp.get("items", [])
                watch_later_id = self._get_watch_later_id(items)
                
            if not watch_later_id:
                return {"items": []}
            params = {"part": "snippet,contentDetails", "playlistId": watch_later_id, "maxResults": max_results}
            if page_token:
                params["pageToken"] = page_token
            return self._oauth_request("playlistItems", params)
        except Exception as e:
            log.error(f"[YOUTUBE] list_watch_later_items error: {e}")
            return {"items": []}

    def move_video_to_playlist(self, video_id: str, target_playlist_id: str) -> dict[str, Any]:
        client = self._get_client(require_oauth=True)
        if not client:
            return {"error": "OAuth client not available"}
        add_body = {
            "snippet": {
                "playlistId": target_playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id,
                },
            }
        }
        return client.playlistItems().insert(part="snippet", body=add_body).execute()

    def remove_video_from_playlist(self, playlist_item_id: str) -> dict[str, Any]:
        client = self._get_client(require_oauth=True)
        if not client:
            return {"error": "OAuth client not available"}
        return client.playlistItems().delete(id=playlist_item_id).execute()
