"""YouTube service for Tube Manager - Optimized with Aggressive Caching."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from tube_manager.google import YouTubeClient
from models.config import TubeManagerConfig

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
        
        # Local cache to avoid redundant API calls
        self._cache: Dict[str, Any] = {}
        self._cache_timestamp: Dict[str, datetime] = {}
        self._cache_ttl = timedelta(minutes=10)  # Cache for 10 minutes (increased from 5)
        
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

    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached data if not expired.

        Args:
            key: Cache key

        Returns:
            Cached data or None if expired/missing
        """
        if key in self._cache:
            if datetime.now() - self._cache_timestamp[key] < self._cache_ttl:
                log.debug(f"Cache hit: {key}")
                return self._cache[key]
            else:
                log.debug(f"Cache expired: {key}")
                del self._cache[key]
                del self._cache_timestamp[key]
        return None

    def _set_cached(self, key: str, data: Any) -> None:
        """Cache data with timestamp.

        Args:
            key: Cache key
            data: Data to cache
        """
        self._cache[key] = data
        self._cache_timestamp[key] = datetime.now()
        log.debug(f"Cached: {key} (TTL: {self._cache_ttl.total_seconds()}s)")

    def _clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        self._cache_timestamp.clear()
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
            await manager.broadcast(json.dumps({"type": "log", "message": "[FETCH] Getting subscriptions..."}))
            
            all_subs = []
            resp = client.list_mine_subscriptions(max_results=50)
            all_subs.extend(resp.get("items", []))
            
            next_token = resp.get("nextPageToken")
            while next_token:
                more = client.list_mine_subscriptions(max_results=50, page_token=next_token)
                all_subs.extend(more.get("items", []))
                next_token = more.get("nextPageToken")
            
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
                await manager.broadcast(json.dumps({"type": "log", "message": f"[FETCH] Enriching {len(channel_ids)} channel stats..."}))
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
            await manager.broadcast(json.dumps({"type": "log", "message": "[FETCH] Getting playlists..."}))
            
            all_playlists = []
            resp = client.list_mine_playlists(max_results=50)
            all_playlists.extend(resp.get("items", []))
            
            next_token = resp.get("nextPageToken")
            while next_token:
                more = client.list_mine_playlists(max_results=50, page_token=next_token)
                all_playlists.extend(more.get("items", []))
                next_token = more.get("nextPageToken")
            
            playlists = []
            total_videos = 0
            
            for pl in all_playlists:
                snippet = pl.get("snippet", {})
                content = pl.get("contentDetails", {})
                vid_count = content.get("itemCount", 0)
                total_videos += vid_count
                
                playlists.append({
                    "id": pl.get("id"),
                    "title": snippet.get("title", "Untitled"),
                    "video_count": vid_count,
                    "channel": snippet.get("channelTitle", "Unknown"),
                    "privacy": snippet.get("privacyStatus", "private"),
                    "thumbnail": (snippet.get("thumbnails", {}) or {}).get("default", {}).get("url", ""),
                    "description": snippet.get("description", ""),
                })
            
            playlists.sort(key=lambda x: x["title"].lower())
            result["playlists"] = playlists
            result["stats"]["total_playlists"] = len(playlists)
            result["stats"]["total_videos"] = total_videos
            
            # Step 3: Fetch videos from playlists with duration (BATCH OPTIMIZED)
            await manager.broadcast(json.dumps({"type": "log", "message": f"[FETCH] Getting video durations for {total_videos} videos..."}))
            
            videos = []
            total_duration = 0
            
            # Process playlists in batches to manage memory
            for playlist in playlists[:10]:  # Limit to first 10 playlists for quota
                pl_id = playlist["id"]
                try:
                    vid_resp = client.list_videos(pl_id, max_results=50)
                    video_items = vid_resp.get("items", [])
                    
                    for vid in video_items:
                        vid_snippet = vid.get("snippet", {})
                        content = vid.get("contentDetails", {})
                        duration_str = content.get("duration", "PT0S")
                        
                        # Parse ISO 8601 duration (e.g., "PT10M30S")
                        duration_seconds = self._parse_duration(duration_str)
                        total_duration += duration_seconds
                        
                        videos.append({
                            "video_id": vid.get("contentDetails", {}).get("videoId", ""),
                            "title": vid_snippet.get("title", "Unknown"),
                            "description": vid_snippet.get("description", "")[:200],
                            "channel_id": vid_snippet.get("channelId", ""),
                            "playlist_id": pl_id,
                            "playlist_title": playlist["title"],
                            "duration_seconds": duration_seconds,
                            "duration_formatted": self._format_duration(duration_seconds),
                            "published_at": vid_snippet.get("publishedAt", ""),
                            "thumbnail": (vid_snippet.get("thumbnails", {}) or {}).get("default", {}).get("url", ""),
                        })
                    
                    next_token = vid_resp.get("nextPageToken")
                    while next_token and len(videos) < 500:  # Cap at 500 videos
                        more = client.list_videos(pl_id, max_results=50, page_token=next_token)
                        for vid in more.get("items", []):
                            vid_snippet = vid.get("snippet", {})
                            content = vid.get("contentDetails", {})
                            duration_str = content.get("duration", "PT0S")
                            duration_seconds = self._parse_duration(duration_str)
                            total_duration += duration_seconds
                            
                            videos.append({
                                "video_id": vid.get("contentDetails", {}).get("videoId", ""),
                                "title": vid_snippet.get("title", "Unknown"),
                                "description": vid_snippet.get("description", "")[:200],
                                "channel_id": vid_snippet.get("channelId", ""),
                                "playlist_id": pl_id,
                                "playlist_title": playlist["title"],
                                "duration_seconds": duration_seconds,
                                "duration_formatted": self._format_duration(duration_seconds),
                                "published_at": vid_snippet.get("publishedAt", ""),
                                "thumbnail": (vid_snippet.get("thumbnails", {}) or {}).get("default", {}).get("url", ""),
                            })
                        next_token = more.get("nextPageToken")
                
                except Exception as e:
                    log.warning(f"Failed to fetch videos for playlist {pl_id}: {e}")
            
            result["videos"] = videos
            result["stats"]["total_duration_seconds"] = total_duration
            result["stats"]["total_duration_formatted"] = self._format_duration(total_duration)
            
            # Save to persistent disk storage
            self._save_to_disk("all_data", result)
            
            # Also cache in memory
            self._set_cached(f"all_data_{user_id}", result)
            
            await manager.broadcast(json.dumps({"type": "log", "message": f"[FETCH] Complete! {len(subscriptions)} subs, {len(playlists)} playlists, {len(videos)} videos with duration"}))
            
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

    async def list_playlists(self, force_refresh: bool = False) -> Dict[str, Any]:
        """List user's playlists (cached).

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            Dictionary containing playlists list or error
        """
        # Use fetch_all_data for efficiency
        all_data = await self.fetch_all_data(force_refresh=force_refresh)
        if "error" in all_data:
            return {"playlists": [], "error": all_data["error"]}
        
        return {"playlists": all_data.get("playlists", [])}

    async def get_stats(self) -> Dict[str, Any]:
        """Get YouTube statistics (cached).

        Returns:
            Dictionary containing stats
        """
        # Use fetch_all_data for efficiency
        all_data = await self.fetch_all_data(force_refresh=False)
        if "error" in all_data:
            return {"total_playlists": 0, "total_videos": 0, "total_subscriptions": 0}
        
        return all_data.get("stats", {"total_playlists": 0, "total_videos": 0, "total_subscriptions": 0})

    async def get_videos(self, playlist_id: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
        """Get videos with duration (cached).

        Args:
            playlist_id: If provided, filter by playlist
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            Dictionary containing videos list or error
        """
        all_data = await self.fetch_all_data(force_refresh=force_refresh)
        if "error" in all_data:
            return {"videos": [], "error": all_data["error"]}
        
        videos = all_data.get("videos", [])
        
        if playlist_id:
            videos = [v for v in videos if v.get("playlist_id") == playlist_id]
        
        return {"videos": videos}