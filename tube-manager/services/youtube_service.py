"""YouTube service for motus.leap - Optimized with Aggressive Caching."""

import json
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from services.youtube_client import YouTubeClient
from models.config import TubeManagerConfig
from core.lru_cache import LRUAsyncCache

log = logging.getLogger(__name__)

class YouTubeService:
    """Service for YouTube API operations with aggressive caching for quota optimization."""

    def __init__(self, config: TubeManagerConfig):
        """Initialize the YouTube service.

        Args:
            config: Application configuration
        """
        self.config = config
        self._client: Optional[YouTubeClient] = None
        
        # LRU cache to avoid redundant API calls with eviction policy
        self._cache = LRUAsyncCache(max_size=100, ttl=timedelta(hours=6))
        self._cache_ttl = timedelta(hours=6)
        
        # User-specific storage path
        self._user_data_dir = Path("/app/data/users") / self._get_user_id()
        self._user_data_dir.mkdir(parents=True, exist_ok=True)

    def _get_user_id(self) -> str:
        """Get unique user ID for data storage."""
        # Use OAuth token hash as user identifier
        if self.config.oauth.access_token:
            return hashlib.sha256(self.config.oauth.access_token.encode()).hexdigest()[:16]
        return "default"

    def get_client(self, require_oauth: bool = False) -> Optional[YouTubeClient]:
        """Get a YouTube API client.

        Args:
            require_oauth: If True, only return client if OAuth is configured

        Returns:
            YouTubeClient instance or None if not available
        """
        if self._client is None:
            def _secret_val(val):
                if hasattr(val, 'get_secret_value'):
                    return val.get_secret_value()
                return str(val) if val else None

            self._client = YouTubeClient(
                api_key=_secret_val(self.config.youtube_api_key),
                oauth_access_token=self.config.oauth.access_token,
                oauth_refresh_token=self.config.oauth.refresh_token,
                oauth_client_id=self.config.oauth.client_id,
                oauth_client_secret=_secret_val(self.config.oauth.client_secret),
                token_expiry=self.config.oauth.token_expiry,
            )

        if require_oauth:
            # Check if OAuth is actually configured
            if not self.config.oauth.access_token or not self.config.oauth.refresh_token:
                return None

        return self._client

    async def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached data if not expired.

        Args:
            key: Cache key

        Returns:
            Cached data or None if expired/missing
        """
        return await self._cache.get(key)

    async def _set_cached(self, key: str, data: Any) -> None:
        """Cache data with timestamp.

        Args:
            key: Cache key
            data: Data to cache
        """
        await self._cache.set(key, data)
        log.debug(f"Cached: {key}")

    async def _clear_cache(self) -> None:
        """Clear all cached data."""
        await self._cache.clear()
        log.info("Cache cleared")

    def _save_to_disk(self, key: str, data: Any) -> None:
        """Save data to persistent disk storage.

        Args:
            key: Storage key (filename)
            data: Data to save (must be JSON-serializable)
        """
        try:
            cache_file = self._user_data_dir / f"{key}.json"
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)
            log.debug(f"Saved to disk: {key}")
        except Exception as e:
            log.warning(f"Failed to save {key} to disk: {e}")

    def _load_from_disk(self, key: str) -> Optional[Any]:
        """Load data from persistent disk storage.

        Args:
            key: Storage key (filename)

        Returns:
            Loaded data or None if not found/error
        """
        try:
            cache_file = self._user_data_dir / f"{key}.json"
            if cache_file.exists():
                with open(cache_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            log.warning(f"Failed to load {key} from disk: {e}")
        return None

    def _playlist_item_to_dict(self, item: dict[str, Any]) -> dict[str, Any]:
        """Normalize a YouTube playlist API item for the UI."""
        snippet = item.get("snippet", {}) or {}
        content = item.get("contentDetails", {}) or {}
        return {
            "id": item.get("id"),
            "title": snippet.get("title", "Untitled"),
            "video_count": int(content.get("itemCount", 0) or 0),
            "channel": snippet.get("channelTitle", "Unknown"),
            "privacy": snippet.get("privacyStatus", "private"),
            "thumbnail": (snippet.get("thumbnails", {}) or {}).get("default", {}).get("url", ""),
            "description": snippet.get("description", ""),
        }

    def _video_item_to_dict(self, item: dict[str, Any], playlist_id: str, playlist_title: str) -> dict[str, Any]:
        """Normalize a playlist item API response for the UI."""
        snippet = item.get("snippet", {}) or {}
        content = item.get("contentDetails", {}) or {}
        duration_str = content.get("duration", "PT0S")
        duration_seconds = self._parse_duration(duration_str)
        return {
            "id": item.get("id", ""),
            "playlist_item_id": item.get("id", ""),
            "video_id": content.get("videoId", ""),
            "title": snippet.get("title", "Unknown"),
            "description": snippet.get("description", "")[:200],
            "channel_id": snippet.get("videoOwnerChannelId") or snippet.get("channelId", ""),
            "channel_title": snippet.get("videoOwnerChannelTitle") or snippet.get("channelTitle", "Unknown Channel"),
            "playlist_id": playlist_id,
            "playlist_title": playlist_title,
            "duration_seconds": duration_seconds,
            "duration_formatted": self._format_duration(duration_seconds),
            "duration": duration_seconds,
            "published_at": snippet.get("publishedAt", ""),
            "thumbnail": (snippet.get("thumbnails", {}) or {}).get("default", {}).get("url", ""),
        }

    async def get_basic_stats(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Return lightweight playlist/video counts without fetching video durations."""
        if not force_refresh:
            cached = await self._get_cached("basic_stats")
            if cached:
                return cached

        client = self.get_client(require_oauth=True)
        if not client:
            return {
                "total_playlists": 0,
                "total_videos": 0,
                "total_subscriptions": 0,
            }

        try:
            playlists = await self._fetch_all_paginated(
                lambda max_results, page_token: client.list_mine_playlists(max_results=max_results, page_token=page_token),
                max_results=50,
                max_items=5000,
            )
            total_videos = sum(int((pl.get("contentDetails", {}) or {}).get("itemCount", 0) or 0) for pl in playlists)
            stats = {
                "total_playlists": len(playlists),
                "total_videos": total_videos,
                "total_subscriptions": 0,
            }
            await self._set_cached("basic_stats", stats)
            return stats
        except Exception as e:
            log.warning(f"Failed to fetch lightweight stats: {e}")
            return {
                "total_playlists": 0,
                "total_videos": 0,
                "total_subscriptions": 0,
            }

    async def list_playlists(self, force_refresh: bool = False) -> Dict[str, Any]:
        """List user's playlists without fetching every video duration."""
        if not force_refresh:
            # 1. Try memory cache
            cached = await self._get_cached("playlists")
            if cached:
                return {"playlists": cached.get("playlists", []), "stats": cached.get("stats", {})}
            
            # 2. Try playlists disk cache
            disk_playlists = self._load_from_disk("playlists")
            if disk_playlists:
                await self._set_cached("playlists", disk_playlists)
                return {"playlists": disk_playlists.get("playlists", []), "stats": disk_playlists.get("stats", {})}
            
            # 3. Fallback to global all_data disk cache
            all_data = self._load_from_disk("all_data")
            if all_data and "playlists" in all_data:
                playlists = all_data["playlists"]
                stats = all_data.get("stats", {})
                basic_stats = {
                    "total_playlists": len(playlists),
                    "total_videos": sum(pl["video_count"] for pl in playlists),
                }
                cache_payload = {"playlists": playlists, "stats": stats or basic_stats}
                await self._set_cached("playlists", cache_payload)
                self._save_to_disk("playlists", cache_payload)
                return cache_payload

        client = self.get_client(require_oauth=True)
        if not client:
            return {"playlists": [], "error": "YouTube not connected. OAuth required."}

        try:
            playlist_items = await self._fetch_all_paginated(
                lambda max_results, page_token: client.list_mine_playlists(max_results=max_results, page_token=page_token),
                max_results=50,
                max_items=5000,
            )
            playlists = sorted((self._playlist_item_to_dict(pl) for pl in playlist_items), key=lambda x: x["title"].lower())
            stats = {
                "total_playlists": len(playlists),
                "total_videos": sum(pl["video_count"] for pl in playlists),
            }
            payload = {"playlists": playlists, "stats": stats}
            await self._set_cached("playlists", payload)
            self._save_to_disk("playlists", payload)
            return payload
        except Exception as e:
            log.warning(f"Failed to list playlists: {e}")
            return {"playlists": [], "error": str(e)}

    async def fetch_all_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Fetch ALL YouTube data in one optimized request sequence with caching.

        This is the QUOTA-OPTIMIZED entry point. It fetches:
        - Subscriptions with channel stats
        - All playlists with video counts
        - Playlist videos with duration
        - Channel mapping data

        All data is cached for 10 minutes to minimize API calls.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            Dictionary containing all YouTube data
        """
        user_id = self._get_user_id()
        
        # Try to load from persistent storage first (survives restarts)
        if not force_refresh:
            disk_data = self._load_from_disk("all_data")
            if disk_data:
                age_seconds = (datetime.now() - datetime.fromisoformat(disk_data.get("cached_at", "1970-01-01"))).total_seconds()
                if age_seconds < self._cache_ttl.total_seconds():
                    log.info(f"Using cached data from disk (age: {age_seconds:.0f}s)")
                    return disk_data

        client = self.get_client(require_oauth=True)
        if not client:
            return {"error": "YouTube not connected. OAuth required."}

        result = {
            "cached_at": datetime.now().isoformat(),
            "subscriptions": [],
            "playlists": [],
            "videos": [],
            "stats": {
                "total_playlists": 0,
                "total_videos": 0,
                "total_subscriptions": 0,
                "total_duration_seconds": 0,
            },
            "user_id": user_id,
        }

        try:
            # Step 1: Fetch all subscriptions (1 API call with pagination)
            log.info("[FETCH] Getting subscriptions...")
            
            all_subs = await self._fetch_all_paginated(
                lambda max_results, page_token: client.list_mine_subscriptions(max_results=max_results, page_token=page_token),
                max_results=50,
                max_items=5000,
            )
            
            # Extract channel IDs for batch lookup
            channel_ids = []
            seen_channels = set()
            
            for sub in all_subs:
                snippet = sub.get("snippet", {}) or {}
                resource = snippet.get("resourceId", {}) or {}
                cid = resource.get("channelId", "")
                if cid and cid not in seen_channels:
                    seen_channels.add(cid)
                    channel_ids.append(cid)
            
            # Batch fetch channel stats (1 API call)
            channel_stats = {}
            if channel_ids:
                log.info(f"[FETCH] Enriching {len(channel_ids)} channel stats...")
                try:
                    enriched = client.list_channels_by_ids(channel_ids, max_results=50) or {}
                    for item in enriched.get("items", []):
                        cid = item.get("id", "")
                        if cid:
                            channel_stats[cid] = item
                except Exception as e:
                    log.warning(f"Channel enrichment failed: {e}")
            
            # Build subscriptions list with stats
            subscriptions = []
            for cid in channel_ids:
                stats = channel_stats.get(cid, {})
                snippet = stats.get("snippet", {}) or {}
                statistics = stats.get("statistics", {}) or {}
                
                subscriptions.append({
                    "id": cid,
                    "title": snippet.get("title", "Unknown"),
                    "thumbnail": (snippet.get("thumbnails", {}) or {}).get("default", {}).get("url", ""),
                    "description": snippet.get("description", ""),
                    "subscribers": statistics.get("subscriberCount", "0"),
                    "video_count": int(statistics.get("videoCount", "0") or "0"),
                    "view_count": statistics.get("viewCount", "0"),
                    "channel_url": f"https://www.youtube.com/channel/{cid}",
                })
            
            subscriptions.sort(key=lambda x: x["title"].lower())
            result["subscriptions"] = subscriptions
            result["stats"]["total_subscriptions"] = len(subscriptions)
            
            # Step 2: Fetch all playlists (1 API call with pagination)
            log.info("[FETCH] Getting playlists...")
            
            all_playlists = await self._fetch_all_paginated(
                lambda max_results, page_token: client.list_mine_playlists(max_results=max_results, page_token=page_token),
                max_results=50,
                max_items=5000,
            )
            playlists = sorted((self._playlist_item_to_dict(pl) for pl in all_playlists), key=lambda x: x["title"].lower())
            total_videos = sum(pl["video_count"] for pl in playlists)
            result["playlists"] = playlists
            result["stats"]["total_playlists"] = len(playlists)
            result["stats"]["total_videos"] = total_videos
            await self._set_cached("basic_stats", {
                "total_playlists": len(playlists),
                "total_videos": total_videos,
                "total_subscriptions": result["stats"]["total_subscriptions"],
            })
            
            # Step 3: Fetch videos from playlists with duration (BATCH OPTIMIZED)
            log.info(f"[FETCH] Getting video durations for {total_videos} videos...")
            
            videos = []
            total_duration = 0
            
            # Process more playlists and videos if force_refresh is True (explicit user sync)
            max_playlists = 50 if force_refresh else 10
            max_total_videos = 2000 if force_refresh else 500
            
            # Process only the playlists needed to keep duration scans quota-safe.
            for playlist in playlists[:max_playlists]:
                pl_id = playlist["id"]
                try:
                    video_items = await self._fetch_all_paginated(
                        lambda max_results, page_token: client.list_videos(pl_id, max_results=max_results, page_token=page_token),
                        max_results=50,
                        max_items=max(0, max_total_videos - len(videos)),
                    )
                    for vid in video_items:
                        video = self._video_item_to_dict(vid, pl_id, playlist["title"])
                        total_duration += video["duration_seconds"]
                        videos.append(video)
                    if len(videos) >= max_total_videos:
                        break
                
                except Exception as e:
                    log.warning(f"Failed to fetch videos for playlist {pl_id}: {e}")
            
            result["videos"] = videos
            result["stats"]["total_duration_seconds"] = total_duration
            result["stats"]["total_duration_formatted"] = self._format_duration(total_duration)
            
            # Save to persistent disk storage
            self._save_to_disk("all_data", result)
            
            # Also cache in memory
            await self._set_cached(f"all_data_{user_id}", result)
            
            log.info(f"[FETCH] Complete! {len(subscriptions)} subs, {len(playlists)} playlists, {len(videos)} videos with duration")
            
            return result

        except Exception as e:
            log.error(f"Failed to fetch all data: {e}")
            return {"error": str(e)}

    def _parse_duration(self, duration_str: str) -> int:
        """Parse ISO 8601 duration string to seconds.

        Args:
            duration_str: Duration string like "PT10M30S"

        Returns:
            Duration in seconds
        """
        import re
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
        if not match:
            return 0
        
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        
        return hours * 3600 + minutes * 60 + seconds

    def _format_duration(self, seconds: int) -> str:
        """Format seconds to human-readable duration.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted string like "1h 30m 15s"
        """
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")
        
        return " ".join(parts)
    async def _fetch_all_paginated(self, fetch_fn, max_results: int = 50, max_items: int = 500):
        """Fetch paginated results with caps and early exit.

        Args:
            fetch_fn: Function to fetch paginated results
            max_results: Results per page
            max_items: Maximum total items to fetch

        Returns:
            List of items
        """
        all_items = []
        page_token = None

        while len(all_items) < max_items:
            resp = fetch_fn(max_results=max_results, page_token=page_token)
            items = resp.get("items", [])
            all_items.extend(items)

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

            # Early exit if approaching quota
            if len(all_items) + max_results > max_items:
                log.warning(f"Approaching item cap {max_items}, stopping pagination")
                break

        return all_items[:max_items]


    async def list_subscriptions(self, force_refresh: bool = False) -> Dict[str, Any]:
        """List user's subscriptions with channel stats (cached).

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            Dictionary containing channels list or error
        """
        # Use fetch_all_data for efficiency
        all_data = await self.fetch_all_data(force_refresh=force_refresh)
        if "error" in all_data:
            return {"channels": [], "error": all_data["error"]}
        
        return {"channels": all_data.get("subscriptions", [])}


    async def get_stats(self) -> Dict[str, Any]:
        """Get YouTube statistics without fetching every video duration."""
        return await self.get_basic_stats(force_refresh=False)

    async def get_videos(self, playlist_id: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
        """Get videos with duration (cached).

        Args:
            playlist_id: If provided, filter by playlist
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            Dictionary containing videos list or error
        """
        # If no playlist_id is provided, use the global cache
        if not playlist_id:
            all_data = await self.fetch_all_data(force_refresh=force_refresh)
            if "error" in all_data:
                return {"videos": [], "error": all_data["error"]}
            return {"videos": all_data.get("videos", [])}
        
        # If playlist_id is provided, check if we have cached videos for this specific playlist
        cache_key = f"playlist_videos_{playlist_id}"
        if not force_refresh:
            # 1. Try memory cache
            cached_videos = await self._get_cached(cache_key)
            if cached_videos is not None:
                return {"videos": cached_videos}
            
            # 2. Try disk cache specifically for this playlist
            disk_cached = self._load_from_disk(cache_key)
            if disk_cached is not None:
                await self._set_cached(cache_key, disk_cached)
                return {"videos": disk_cached}
            
            # 3. Fallback to extracting from the global "all_data" disk cache
            all_data = self._load_from_disk("all_data")
            if all_data and "videos" in all_data:
                playlist_videos = [v for v in all_data["videos"] if v.get("playlist_id") == playlist_id]
                if playlist_videos:
                    await self._set_cached(cache_key, playlist_videos)
                    self._save_to_disk(cache_key, playlist_videos)
                    return {"videos": playlist_videos}
        
        # Otherwise, fetch fresh videos for this specific playlist directly
        client = self.get_client(require_oauth=True)
        if not client:
            return {"videos": [], "error": "OAuth client not available"}
            
        try:
            # Find the playlist title from list of playlists to preserve the video metadata
            playlists_data = await self.list_playlists()
            playlist_title = "Unknown Playlist"
            for pl in playlists_data.get("playlists", []):
                if pl.get("id") == playlist_id:
                    playlist_title = pl.get("title", "Unknown Playlist")
                    break
                    
            video_items = await self._fetch_all_paginated(
                lambda max_results, page_token: client.list_videos(playlist_id, max_results=max_results, page_token=page_token),
                max_results=50,
                max_items=500,
            )
            videos = []
            for vid in video_items:
                video = self._video_item_to_dict(vid, playlist_id, playlist_title)
                videos.append(video)
                
            # Cache the videos for this specific playlist in memory and disk
            await self._set_cached(cache_key, videos)
            self._save_to_disk(cache_key, videos)
            return {"videos": videos}
        except Exception as e:
            log.error(f"Error fetching videos for playlist {playlist_id}: {e}")
            return {"videos": [], "error": str(e)}