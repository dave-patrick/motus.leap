"""YouTube service for motus.leap - Optimized with Aggressive Caching."""

import json
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import asyncio
from functools import wraps

from services.youtube_client import YouTubeClient
from models.config import TubeManagerConfig
from core.lru_cache import LRUAsyncCache

log = logging.getLogger(__name__)

def cache_result(key_prefix: str, ttl: Optional[timedelta] = None):
    def decorator(func):
        @wraps(func)
        async def wrapper(instance: "YouTubeService", *args, **kwargs):
            force_refresh = kwargs.get('force_refresh', False)
            # Generate unique key from args and kwargs, excluding 'instance' from args for hashing
            # Use json.dumps to handle complex types in args/kwargs for hashing
            cache_key = f"{key_prefix}_{instance._get_user_id()}_{hashlib.sha256(json.dumps(args).encode()).hexdigest()}_{hashlib.sha256(json.dumps(kwargs).encode()).hexdigest()}"

            if not force_refresh:
                cached_data = await instance._cache.get(cache_key)
                if cached_data:
                    log.debug(f"Cache hit for {key_prefix}")
                    return cached_data

            log.debug(f"Cache miss or force_refresh for {key_prefix}, fetching...")
            result = await func(instance, *args, **kwargs)
            await instance._cache.set(cache_key, result, ttl=ttl)
            return result
        return wrapper
    return decorator

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
        self._watch_later_cache_ttl = timedelta(minutes=15) # Shorter TTL for Watch Later

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
                log.error("YouTube client is None – check OAuth token configuration");
                return None

        return self._client

    async def _save_to_disk(self, key: str, data: Any) -> None:
        """Save data to persistent disk storage asynchronously."""
        try:
            cache_file = self._user_data_dir / f"{key}.json"
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(cache_file.write_text, json.dumps(data, indent=2))
            log.debug(f"Saved to disk: {key}")
        except Exception as e:
            log.warning(f"Failed to save {key} to disk: {e}")

    async def _load_from_disk(self, key: str) -> Optional[Any]:
        """Load data from persistent disk storage asynchronously."""
        try:
            cache_file = self._user_data_dir / f"{key}.json"
            if await asyncio.to_thread(cache_file.exists):
                content = await asyncio.to_thread(cache_file.read_text)
                return json.loads(content)
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

    def _parse_duration(self, duration_str: str) -> int:
        """Parse ISO 8601 duration string (e.g., PT1H30M15S) to total seconds."""
        import re
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_str)
        if not match:
            return 0
        
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        
        return hours * 3600 + minutes * 60 + seconds

    def _format_duration(self, seconds: int) -> str:
        """Format seconds to human-readable duration."""
        if seconds is None:
            return "0s"
        
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
            "thumbnail": (snippet.get("thumbnails", {}) or {}).get("default", {}).get("url", ""),
        }

    @cache_result("basic_stats", ttl=timedelta(minutes=10))
    async def get_basic_stats(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Return lightweight playlist/video counts without fetching video durations."""

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
            subscriptions_data = await self.list_subscriptions(force_refresh=force_refresh)
            total_subscriptions = subscriptions_data.get("total_subscriptions", 0)
            stats = {
                "total_playlists": len(playlists),
                "total_videos": total_videos,
                "total_subscriptions": total_subscriptions,
            }
            return stats
        except Exception as e:
            log.warning(f"Failed to fetch lightweight stats: {e}")
            return {
                "total_playlists": 0,
                "total_videos": 0,
                "total_subscriptions": 0,
            }

    @cache_result("playlists", ttl=timedelta(minutes=10))
    async def list_playlists(self, force_refresh: bool = False) -> Dict[str, Any]:
        """List user's playlists with lightweight change detection (renames/removals force a sync)."""
        
        # 1. Try persistent disk cache first for fast initial load
        disk_playlists_payload = await self._load_from_disk("playlists")
        if disk_playlists_payload and not force_refresh:
            log.info("list_playlists: returning from disk cache for instant load.")
            return disk_playlists_payload

        client = self.get_client(require_oauth=True)
        if not client:
            return {"playlists": [], "error": "YouTube not connected. OAuth required."}

        try:
            # Fetch current playlists from YouTube (lightweight, 1 API call with pagination if >50)
            playlist_items = await self._fetch_all_paginated(
                lambda max_results, page_token: client.list_mine_playlists(max_results=max_results, page_token=page_token),
                max_results=50,
                max_items=5000,
            )
            current_playlists = sorted((self._playlist_item_to_dict(pl) for pl in playlist_items), key=lambda x: x["title"].lower())
            
            # Detect mismatch (addition, removal, or name changes) compared to disk_playlists if it existed
            mismatch = False
            if disk_playlists_payload: # if there was a disk cache, compare against it
                dp_playlists = disk_playlists_payload.get("playlists", [])
                if not dp_playlists or len(dp_playlists) != len(current_playlists):
                    mismatch = True
                else:
                    cached_by_id = {p["id"]: p for p in dp_playlists}
                    for curr in current_playlists:
                        cid = curr["id"]
                        if cid not in cached_by_id:
                            mismatch = True
                            break
                        # Detect renaming
                        if cached_by_id[cid]["title"] != curr["title"]:
                            log.info(f"[SYNC DETECT] Playlist renamed: '{cached_by_id[cid]['title']}' -> '{curr['title']}'")
                            mismatch = True
                            break
            else: # no disk cache, so consider it a mismatch to trigger full sync
                mismatch = True

            # If a change was detected externally or forced, run a full fresh sync
            if mismatch or force_refresh:
                log.info("[SYNC DETECT] Playlist change (rename, removal, or addition) detected! Performing full fresh sync...")
                sync_result = await self.fetch_all_data(force_refresh=True)
                if "error" not in sync_result:
                    playlists = sync_result.get("playlists", [])
                    stats = {
                        "total_playlists": len(playlists),
                        "total_videos": sum(pl["video_count"] for pl in playlists),
                    }
                    payload = {"playlists": playlists, "stats": stats}
                    await self._save_to_disk("playlists", payload)
                    return payload
            
            # If no change detected or initial fetch, save current_playlists if no disk cache existed
            if not disk_playlists_payload:
                stats = {
                    "total_playlists": len(current_playlists),
                    "total_videos": sum(pl["video_count"] for pl in current_playlists),
                }
                payload = {"playlists": current_playlists, "stats": stats}
                await self._save_to_disk("playlists", payload)
                return payload
            
            # If no mismatch and disk cache existed, return the current_playlists as payload to be cached by decorator
            stats = {
                "total_playlists": len(current_playlists),
                "total_videos": sum(pl["video_count"] for pl in current_playlists),
            }
            return {"playlists": current_playlists, "stats": stats}

        except Exception as e:
            log.warning(f"Failed to check/list playlists: {e}")
            if disk_playlists_payload: 
                return disk_playlists_payload
            return {"playlists": [], "error": str(e)}

    @cache_result("subscriptions", ttl=timedelta(minutes=10))
    async def list_subscriptions(self, force_refresh: bool = False) -> Dict[str, Any]:
        """List user's subscriptions with channel stats (cached)."""
        client = self.get_client(require_oauth=True)
        if not client:
            return {"channels": [], "error": "YouTube not connected. OAuth required."}
        
        try:
            all_subs = await self._fetch_all_paginated(
                lambda max_results, page_token: client.list_mine_subscriptions(max_results=max_results, page_token=page_token),
                max_results=50,
                max_items=5000,
            )
            
            channel_ids = []
            seen_channels = set()
            for sub in all_subs:
                snippet = sub.get("snippet", {}) or {}
                resource = snippet.get("resourceId", {}) or {}
                cid = resource.get("channelId", "")
                if cid and cid not in seen_channels:
                    seen_channels.add(cid)
                    channel_ids.append(cid)
            
            channel_stats = {}
            if channel_ids:
                log.info(f"[FETCH] Enriching {len(channel_ids)} channel stats...")
                try:
                    enriched = await asyncio.to_thread(client.list_channels_by_ids, channel_ids, 50) or {}
                    for item in enriched.get("items", []):
                        cid = item.get("id", "")
                        if cid:
                            channel_stats[cid] = item
                except Exception as e:
                    log.warning(f"Channel enrichment failed: {e}")
            
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
            return {"channels": subscriptions, "total_subscriptions": len(subscriptions)}
        except Exception as e:
            log.warning(f"Failed to list subscriptions: {e}")
            return {"channels": [], "error": str(e)}

    # This method is not using the decorator, it directly handles its own caching
    async def list_watch_later_items_cached(self, playlist_id: Optional[str] = None, force_refresh: bool = False) -> Dict[str, Any]:
        user_id = self._get_user_id()
        cache_key = f"watch_later_items_{user_id}_{playlist_id or 'auto'}"

        if not force_refresh:
            cached_data = await self._cache.get(cache_key) # Use _cache.get directly
            if cached_data:
                log.info(f"Using cached Watch Later items for {playlist_id or 'auto'}")
                return cached_data

        client = self.get_client(require_oauth=True)
        if not client:
            return {"items": [], "error": "YouTube not connected. OAuth required."}

        try:
            # Try browser scraper first (bypasses API restriction) if no specific playlist_id is provided
            if not playlist_id:
                from services.browser_scraper import has_cookies, scrape_watch_later_videos
                if has_cookies():
                    log.info("[WATCH LATER CACHE] YouTube cookies found. Attempting browser scrape for native Watch Later...")
                    scraped = await asyncio.to_thread(scrape_watch_later_videos, 200)
                    if scraped.get("items"):
                        log.info(f"[WATCH LATER CACHE] Browser scrape retrieved {len(scraped['items'])} videos from native Watch Later!")
                        await self._cache.set(cache_key, scraped, ttl=self._watch_later_cache_ttl) # Use _cache.set with ttl
                        return scraped
                    else:
                        log.info("[WATCH LATER CACHE] Browser scrape returned 0 videos. Falling back to API...")

            # Fallback to API if no cookies, scrape failed, or specific playlist_id was requested
            resp = await asyncio.to_thread(client.list_watch_later_items, max_results=50, playlist_id=playlist_id)
            items = resp.get("items", [])
            result = {"items": items}
            await self._cache.set(cache_key, result, ttl=self._watch_later_cache_ttl) # Use _cache.set with ttl
            log.info(f"Fetched {len(items)} Watch Later items via API for {playlist_id or 'auto'}")
            return result
        except Exception as e:
            log.error(f"Failed to fetch Watch Later items (cached): {e}")
            return {"items": [], "error": str(e)}

    async def _fetch_all_paginated(self, fetch_fn, max_results: int = 50, max_items: int = 500) -> List[Any]:
        """Fetch paginated results with caps and early exit."""
        all_items = []
        page_token = None

        while len(all_items) < max_items:
            # Run the blocking sync fetch_fn in a separate thread to unblock the main FastAPI event loop
            resp = await asyncio.to_thread(fetch_fn, max_results, page_token)
            if resp is None or "items" not in resp:
                log.warning(f"_fetch_all_paginated: fetch_fn returned None or missing 'items'. Response: {resp}. Stopping pagination.")
                break
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


    @cache_result("all_data", ttl=timedelta(minutes=10)) # Cache for 10 minutes
    async def fetch_all_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Fetch ALL YouTube data in one optimized request sequence with caching."""

        # This is the QUOTA-OPTIMIZED entry point. It fetches:
        # - Subscriptions with channel stats
        # - All playlists with video counts
        # - Playlist videos with duration
        # - Channel mapping data

        # All data is cached for 10 minutes to minimize API calls.

        # Args:
        #     force_refresh: If True, bypass cache and fetch fresh data

        # Returns:
        #     Dictionary containing all YouTube data
        # """
        user_id = self._get_user_id()
        
        # 1. Try persistent disk cache if not in memory (decorator already handled memory)
        disk_data = await self._load_from_disk("all_data")
        if disk_data and not force_refresh:
            log.info("Using cached all_data from disk, caching in memory")
            return disk_data # Return disk data, decorator will cache it in memory

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
            
            # Use the cached list_subscriptions method
            subscriptions_data = await self.list_subscriptions(force_refresh=force_refresh)
            subscriptions = subscriptions_data.get("channels", [])
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
            # _set_cached for basic_stats will be handled by its own decorator

            # Step 3: Fetch videos from playlists with duration (BATCH OPTIMIZED)
            log.info(f"[FETCH] Getting video durations for {total_videos} videos...")
            
            videos = []
            total_duration = 0
            
            # Process more playlists and videos if force_refresh is True (explicit user sync)
            max_playlists = 50 if force_refresh else 10
            max_total_videos = 2000 if force_refresh else 500
            
            # Process only the playlists needed to keep duration scans quota-safe.
            # Use semaphore to limit concurrent playlist fetches (max 5 concurrent)
            semaphore = asyncio.Semaphore(5)
            
            async def fetch_playlist_videos(playlist):
                pl_id = playlist["id"]
                async with semaphore:
                    try:
                        video_items = await self._fetch_all_paginated(
                            lambda max_results, page_token: client.list_videos(pl_id, max_results=max_results, page_token=page_token),
                            max_results=50,
                            max_items=max(0, max_total_videos - len(videos)),
                        )
                        playlist_videos = []
                        for vid in video_items:
                            video = self._video_item_to_dict(vid, pl_id, playlist["title"])
                            playlist_videos.append(video)
                        return playlist_videos
                    except Exception as e:
                        log.warning(f"Failed to fetch videos for playlist {pl_id}: {e}")
                        return []
            
            # Create tasks for all playlists
            playlist_tasks = [fetch_playlist_videos(pl) for pl in playlists[:max_playlists]]
            playlist_results = await asyncio.gather(*playlist_tasks, return_exceptions=True)
            
            videos = []
            total_duration = 0
            for playlist_videos in playlist_results:
                if isinstance(playlist_videos, Exception):
                    continue
                for video in playlist_videos:
                    total_duration += video["duration_seconds"]
                    videos.append(video)
                if len(videos) >= max_total_videos:
                    break
            
            result["videos"] = videos
            result["stats"]["total_duration_seconds"] = total_duration
            result["stats"]["total_duration_formatted"] = self._format_duration(total_duration)
            
            # Save to persistent disk storage
            await self._save_to_disk("all_data", result)
            
            # The decorator will handle caching in memory
            
            log.info(f"[FETCH] Complete! {len(subscriptions)} subs, {len(playlists)} playlists, {len(videos)} videos with duration")
            
            return result

        except Exception as e:
            log.error(f"Failed to fetch all data: {e}")
            return {"error": str(e)}

    @cache_result("subscriptions", ttl=timedelta(minutes=10)) # Cache for 10 minutes
    async def list_subscriptions(self, force_refresh: bool = False) -> Dict[str, Any]:
        """List user's subscriptions with channel stats (cached)."""

        # Args:
        #     force_refresh: If True, bypass cache and fetch fresh data

        # Returns:
        #     Dictionary containing channels list or error
        # """
        # Use fetch_all_data for efficiency
        all_data = await self.fetch_all_data(force_refresh=force_refresh)
        if "error" in all_data:
            return {"channels": [], "error": all_data["error"]}
        
        return {"channels": all_data.get("subscriptions", [])}

    async def get_stats(self) -> Dict[str, Any]:
        """Get YouTube statistics without fetching every video duration."""
        return await self.get_basic_stats(force_refresh=False)

    @cache_result("playlist_videos", ttl=timedelta(minutes=5)) # Cache playlist videos for 5 minutes
    async def get_videos(self, playlist_id: str, force_refresh: bool = False) -> Dict[str, Any]:
        """Get videos with duration (cached)."""

        # Args:
        #     playlist_id: If provided, filter by playlist
        #     force_refresh: If True, bypass cache and fetch fresh data

        # Returns:
        #     Dictionary containing videos list or error
        # """
        # If no playlist_id is provided, use the global cache (fetch_all_data already cached)
        if not playlist_id:
            all_data = await self.fetch_all_data(force_refresh=force_refresh)
            if "error" in all_data:
                return {"videos": [], "error": all_data["error"]}
            return {"videos": all_data.get("videos", [])}
        
        # If playlist_id is provided, check if we have cached videos for this specific playlist
        # Decorator will handle the memory cache, we just need to handle disk for initial load
        disk_cached = await self._load_from_disk(f"playlist_videos_{playlist_id}")
        if disk_cached is not None and not force_refresh:
            log.info(f"Using disk-cached videos for playlist {playlist_id}")
            return {"videos": disk_cached}

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
                
            # Cache the videos for this specific playlist in disk
            await self._save_to_disk(f"playlist_videos_{playlist_id}", videos)
            return {"videos": videos}
        except Exception as e:
            log.error(f"Error fetching videos for playlist {playlist_id}: {e}")
            return {"videos": [], "error": str(e)}
