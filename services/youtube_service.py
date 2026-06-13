"""YouTube service for Tube Manager."""

import logging
from typing import Optional, Dict, Any, List
from collections import defaultdict

from tube_manager.google import YouTubeClient
from models.config import TubeManagerConfig

log = logging.getLogger(__name__)

class YouTubeService:
    """Service for YouTube API operations."""

    def __init__(self, config: TubeManagerConfig):
        """Initialize the YouTube service.

        Args:
            config: Application configuration
        """
        self.config = config
        self._client: Optional[YouTubeClient] = None

    def get_client(self, require_oauth: bool = False) -> Optional[YouTubeClient]:
        """Get a YouTube API client.

        Args:
            require_oauth: If True, only return client if OAuth is configured

        Returns:
            YouTubeClient instance or None if not available
        """
        if self._client is None:
            self._client = YouTubeClient(
                api_key=self.config.youtube_api_key.get_secret_value() if self.config.youtube_api_key else None,
                oauth_access_token=self.config.oauth.access_token,
                oauth_refresh_token=self.config.oauth.refresh_token,
                oauth_client_id=self.config.oauth.client_id,
                oauth_client_secret=self.config.oauth.client_secret.get_secret_value() if self.config.oauth.client_secret else None,
                token_expiry=self.config.oauth.token_expiry,
            )

        if require_oauth:
            # Check if OAuth is actually configured
            if not self.config.oauth.access_token or not self.config.oauth.refresh_token:
                return None

        return self._client

    async def list_subscriptions(self) -> Dict[str, Any]:
        """List user's subscriptions with channel stats.

        Returns:
            Dictionary containing channels list or error
        """
        client = self.get_client(require_oauth=True)
        if not client:
            return {"channels": [], "error": "YouTube not connected. OAuth required."}

        try:
            if not hasattr(client, "list_mine_subscriptions"):
                return {"channels": [], "error": "Subscriptions method not available"}

            all_subs: List[Dict[str, Any]] = []
            resp = client.list_mine_subscriptions(max_results=50)
            all_subs.extend(resp.get("items", []))

            next_token = resp.get("nextPageToken")
            while next_token:
                more = client.list_mine_subscriptions(max_results=50, page_token=next_token)
                all_subs.extend(more.get("items", []))
                next_token = more.get("nextPageToken")

            # Deduplicate and collect channel IDs
            seen: set[str] = set()
            channel_ids: List[str] = []
            raw: List[Dict[str, Any]] = []

            for sub in all_subs:
                snippet = sub.get("snippet", {}) or {}
                resource = snippet.get("resourceId", {}) or {}
                channel_id = resource.get("channelId", "")
                if not channel_id or channel_id in seen:
                    continue
                seen.add(channel_id)
                channel_ids.append(channel_id)
                raw.append({
                    "id": channel_id,
                    "title": snippet.get("title", "Unknown Channel"),
                    "thumbnail": (snippet.get("thumbnails") or {}).get("default", {}).get("url", ""),
                    "description": snippet.get("description", ""),
                    "channel_url": f"https://www.youtube.com/channel/{channel_id}",
                    "video_count": 0,
                    "subscribers": "Unknown",
                })

            # Enrich with channel stats
            if channel_ids:
                try:
                    enriched = client.list_channels_by_ids(channel_ids, max_results=50) or {}
                except Exception as stats_err:
                    log.warning(f"Channel stats lookup failed: {stats_err}")
                    enriched = {}

                stats_map: Dict[str, Dict[str, Any]] = {}
                for item in enriched.get("items", []):
                    cid = item.get("id", "")
                    if not cid:
                        continue
                    stats_map[cid] = (item.get("statistics", {}) or {})

                for entry in raw:
                    cid = entry["id"]
                    stats = stats_map.get(cid, {})
                    entry["subscribers"] = stats.get("subscriberCount", "Unknown")
                    entry["video_count"] = int(stats.get("videoCount", "0") or "0")

            # Sort alphabetically
            sorted_channels = sorted(raw, key=lambda item: (item.get("title") or "").lower())
            return {"channels": sorted_channels}

        except Exception as e:
            log.error(f"Failed to fetch subscriptions: {e}")
            return {"channels": [], "error": str(e)}

    async def list_playlists(self) -> Dict[str, Any]:
        """List user's playlists.

        Returns:
            Dictionary containing playlists list or error
        """
        client = self.get_client(require_oauth=True)
        if not client:
            return {"playlists": [], "error": "YouTube not connected. OAuth required."}

        try:
            all_playlists: List[Dict[str, Any]] = []
            resp = client.list_mine_playlists(max_results=50)
            items = resp.get("items", [])
            all_playlists.extend(items)

            next_token = resp.get("nextPageToken")
            while next_token:
                more = client.list_mine_playlists(max_results=50, page_token=next_token)
                items = more.get("items", [])
                all_playlists.extend(items)
                next_token = more.get("nextPageToken")

            # Format for UI
            formatted = []
            for pl in all_playlists:
                snippet = pl.get("snippet", {})
                content = pl.get("contentDetails", {})
                formatted.append({
                    "id": pl.get("id"),
                    "title": snippet.get("title", "Untitled"),
                    "video_count": content.get("itemCount", 0),
                    "channel": snippet.get("channelTitle", "Unknown"),
                    "privacy": snippet.get("privacyStatus", "private"),
                    "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                    "description": snippet.get("description", ""),
                })

            return {"playlists": formatted}

        except Exception as e:
            log.error(f"Failed to fetch playlists: {e}")
            return {"playlists": [], "error": str(e)}

    async def get_stats(self) -> Dict[str, Any]:
        """Get YouTube statistics.

        Returns:
            Dictionary containing stats
        """
        client = self.get_client()
        total_playlists = 0
        total_videos = 0

        if client:
            try:
                # Get playlists count
                playlists_resp = client.list_mine_playlists(max_results=50)
                playlists = playlists_resp.get("items", [])
                total_playlists = len(playlists)

                # Get total videos across playlist summary
                for pl in playlists:
                    count = pl.get("contentDetails", {}).get("itemCount", 0)
                    total_videos += count

                # If more playlists, fetch more
                next_token = playlists_resp.get("nextPageToken")
                while next_token:
                    more = client.list_mine_playlists(max_results=50, page_token=next_token)
                    for pl in more.get("items", []):
                        total_playlists += 1
                        total_videos += pl.get("contentDetails", {}).get("itemCount", 0)
                    next_token = more.get("nextPageToken")
            except Exception as e:
                log.warning(f"Failed to fetch real YouTube stats: {e}")

        return {
            "total_playlists": total_playlists,
            "total_videos": total_videos,
        }