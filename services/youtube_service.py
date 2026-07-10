"""YouTube service for motus.leap - Optimized with Aggressive Caching."""

import json
import hashlib
import logging
import os
import ssl

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import asyncio
from functools import wraps

from services.youtube_client import YouTubeClient
from models.config import TubeManagerConfig
from core.lru_cache import LRUAsyncCache

log = logging.getLogger(__name__)


class _ReentrantAsyncLock:
    """Asyncio reentrant lock (defensive safety guarantee).

    asyncio.Lock() is NOT reentrant. The heavy data-fetch paths are wrapped in
    _data_lock for single-flight serialization; a reentrant lock guarantees that
    if any internal call path ever re-enters while the lock is held (e.g. a
    future refactor of get_basic_stats -> list_*), it will not self-deadlock.
    As of this writing, list_* do not acquire _data_lock, so this is a safety
    guarantee rather than a fix for an active deadlock — but it still provides
    correct single-flight serialization across distinct tasks.
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._owner = None
        self._depth = 0

    def __repr__(self):
        return f"_ReentrantAsyncLock(owner={self._owner}, depth={self._depth})"

    async def acquire(self):
        me = asyncio.current_task()
        if self._owner is me:
            self._depth += 1
            return True
        await self._lock.acquire()
        self._owner = me
        self._depth = 1
        return True

    def release(self):
        me = asyncio.current_task()
        if self._owner is not me:
            raise RuntimeError("release() called by non-owner task")
        self._depth -= 1
        if self._depth == 0:
            self._owner = None
            self._lock.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *exc):
        self.release()
        return False


def _best_thumbnail(thumbs: Optional[dict]) -> str:
    """Prefer the highest-resolution YouTube thumbnail available.

    YouTube returns keys default(120x90), medium(320x180), high(480x360),
    standard(640x480), maxres(1280x720). 'default' is blurry, so pick the best
    present and fall back to it only if nothing better exists.
    """
    if not thumbs:
        return ""
    for key in ("maxres", "standard", "high", "medium", "default"):
        url = (thumbs.get(key) or {}).get("url")
        if url:
            return url
    return ""

def cache_result(key_prefix: str, ttl: Optional[timedelta] = None):
    def decorator(func):
        @wraps(func)
        async def wrapper(instance: "YouTubeService", *args, **kwargs):
            force_refresh = kwargs.get('force_refresh', False)
            # Generate unique key from args and kwargs, excluding 'instance' from args for hashing
            # Use json.dumps to handle complex types in args/kwargs for hashing
            cache_key = f"{key_prefix}_{instance._get_user_id()}_{hashlib.sha256(json.dumps(args).encode() + json.dumps(kwargs).encode()).hexdigest()}"

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
        self._enrich_lock = asyncio.Lock()  # Prevent concurrent enrichment from crashing (heap corruption)
        # Reentrant single-flight lock (defensive). asyncio.Lock is NOT
        # reentrant; a reentrant lock guarantees that if any internal call path
        # ever re-enters while _data_lock is held (e.g. future refactor of
        # get_basic_stats -> list_*) it will not self-deadlock. As of this
        # writing, list_* do NOT acquire _data_lock, so this is a safety
        # guarantee rather than a fix for an active deadlock — but it still
        # provides correct single-flight serialization across distinct tasks.
        self._data_lock = _ReentrantAsyncLock()    # Single-flight: serialize ALL heavy data fetches to prevent heap corruption

        # User-specific storage path — configurable via TUBE_MANAGER_DATA_DIR (defaults to /app/data on Render, tmp in tests)
        _data_dir = Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data"))
        self._user_data_dir = _data_dir / "users" / self._get_user_id()
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
                log.error("YouTube client is None – check OAuth token configuration")
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

    async def disk_cache_cleanup(self, max_age_days: int = 7) -> int:
        """Remove stale JSON files from the disk cache directory.

        Args:
            max_age_days: Maximum age in days before a cache file is considered stale.

        Returns:
            Number of files removed.
        """
        removed = 0
        cutoff = datetime.now() - timedelta(days=max_age_days)
        try:
            if not await asyncio.to_thread(self._user_data_dir.exists):
                return 0
            # Wrap sync glob() in asyncio.to_thread() to avoid blocking event loop (M6)
            json_files = await asyncio.to_thread(lambda: list(self._user_data_dir.glob("*.json")))
            for file_path in json_files:
                try:
                    file_stat = await asyncio.to_thread(file_path.stat)
                    file_mtime = datetime.fromtimestamp(file_stat.st_mtime)
                    if file_mtime < cutoff:
                        await asyncio.to_thread(file_path.unlink)
                        removed += 1
                        log.debug(f"Removed stale cache file: {file_path.name}")
                except Exception as e:
                    log.warning(f"Failed to remove cache file {file_path}: {e}")
            if removed:
                log.info(f"Disk cache cleanup: removed {removed} stale files (older than {max_age_days} days)")
        except Exception as e:
            log.warning(f"Disk cache cleanup failed: {e}")
        return removed

    async def _get_cached(self, key: str):
        """Get value from internal cache."""
        return await self._cache.get(key)

    async def _set_cached(self, key: str, value, ttl=None):
        """Set value in internal cache with optional TTL."""
        await self._cache.set(key, value, ttl=ttl)

    async def _cache_invalidate_playlist(self, playlist_id: str) -> None:
        """Remove cached data for a specific playlist from memory and disk."""
        # Invalidate memory cache entries matching this playlist
        async with self._cache._lock:
            keys_to_remove = [
                key for key in self._cache._cache
                if playlist_id in key
            ]
            for key in keys_to_remove:
                await self._cache._evict(key)

        # Invalidate disk cache files for this playlist
        disk_keys = [f"playlist_videos_{playlist_id}"]
        for key in disk_keys:
            cache_file = self._user_data_dir / f"{key}.json"
            try:
                if await asyncio.to_thread(cache_file.exists):
                    await asyncio.to_thread(cache_file.unlink)
                    log.info(f"Invalidated disk cache for playlist {playlist_id}")
            except Exception as e:
                log.warning(f"Failed to remove disk cache for playlist {playlist_id}: {e}")

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
            "thumbnail": _best_thumbnail(snippet.get("thumbnails")),
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
            "thumbnail": _best_thumbnail(snippet.get("thumbnails")),
        }

    @cache_result("basic_stats", ttl=timedelta(minutes=10))
    async def get_basic_stats(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Return lightweight playlist/video counts without fetching video durations."""
        async with self._data_lock:
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
                    max_items=500,
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
                max_items=500,
            )
            current_playlists = sorted((self._playlist_item_to_dict(pl) for pl in playlist_items), key=lambda x: x["title"].lower())
            
            # Detect changes compared to disk cache:
            #   - structural change (addition/removal): needs a full sync to
            #     fetch video durations for new/changed playlists.
            #   - rename-only (same count + same IDs, titles differ): does NOT
            #     need a full re-sync — patch the titles in place. A rename
            #     previously triggered fetch_all_data(force_refresh=True), which
            #     re-fetched every subscription + up to 2000 video durations for
            #     a trivial title change (quota burn + multi-second latency).
            structural_change = False
            rename_only = False
            if disk_playlists_payload:
                dp_playlists = disk_playlists_payload.get("playlists", [])
                if not dp_playlists or len(dp_playlists) != len(current_playlists):
                    structural_change = True
                else:
                    cached_by_id = {p["id"]: p for p in dp_playlists}
                    titles_differ = False
                    for curr in current_playlists:
                        cid = curr["id"]
                        if cid not in cached_by_id:
                            structural_change = True
                            break
                        if cached_by_id[cid]["title"] != curr["title"]:
                            log.info(f"[SYNC DETECT] Playlist renamed: '{cached_by_id[cid]['title']}' -> '{curr['title']}'")
                            titles_differ = True
                    if not structural_change and titles_differ:
                        rename_only = True
            else:
                # No disk cache: treat as structural so we build a full cache.
                structural_change = True

            # A forced refresh always does a full sync.
            if force_refresh:
                structural_change = True

            # Rename-only: patch titles in the cached all_data and return
            # current_playlists without a quota-burning full re-sync.
            if rename_only and not structural_change:
                try:
                    all_data = await self._load_from_disk("all_data")
                    if all_data and "playlists" in all_data:
                        title_by_id = {p["id"]: p["title"] for p in current_playlists}
                        for pl in all_data.get("playlists", []):
                            if pl.get("id") in title_by_id:
                                pl["title"] = title_by_id[pl["id"]]
                        await self._save_to_disk("all_data", all_data)
                except Exception as patch_err:
                    log.warning(f"[SYNC DETECT] Rename patch of all_data failed (non-fatal): {patch_err}")
                stats = {
                    "total_playlists": len(current_playlists),
                    "total_videos": sum(pl["video_count"] for pl in current_playlists),
                }
                payload = {"playlists": current_playlists, "stats": stats}
                await self._save_to_disk("playlists", payload)
                return payload

            # Structural change (addition/removal) or forced: full fresh sync
            # to fetch video durations for new/changed playlists.
            if structural_change:
                log.info("[SYNC DETECT] Playlist change (removal or addition) detected! Performing full fresh sync...")
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
                max_items=500,
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
                async with self._enrich_lock:
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
            for sub in all_subs:
                snippet = sub.get("snippet", {}) or {}
                resource = snippet.get("resourceId", {}) or {}
                cid = resource.get("channelId", "")
                if not cid:
                    continue
                # PRIMARY (zero quota): title + avatar come straight from the
                # subscriptions.list snippet, which always carries them. Do NOT
                # depend on channels.list (quota-blocked on Render) for the
                # basics — that was why names/avatars came back empty.
                sub_snip = snippet
                stats = channel_stats.get(cid, {})
                st_snip = stats.get("snippet", {}) or {}
                statistics = stats.get("statistics", {}) or {}
                title = (sub_snip.get("title") or st_snip.get("title") or "Unknown").strip()
                thumb = _best_thumbnail(sub_snip.get("thumbnails")) or _best_thumbnail(st_snip.get("thumbnails"))
                subscriptions.append({
                    "id": cid,
                    "subscription_id": sub.get("id", ""),
                    "title": title,
                    "thumbnail": thumb,
                    "description": (st_snip.get("description") or sub_snip.get("description", "")),
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

    async def map_channels_from_playlist_contents(
        self, max_items_per_playlist: int = 500
    ) -> Dict[str, Any]:
        """Derive channel->playlist mappings from videos already IN each
        playlist. For every playlist, read its items and tally each video's
        owner channel. A channel is mapped to the playlist where it appears
        most often (majority vote).

        NAME RESOLUTION (channel_titles) is the priority and runs at ZERO
        YouTube API quota: it reads the DISK-CACHED combined all_data.json
        (videos carry channel_id + channel_title), which the earlier auto-map
        / background sync populated. We do NOT depend on list_playlists() for
        naming — list_playlists returns empty on Render under quota, so any
        dependency there would silently yield 0 names. A live fetch is only a
        fallback when all_data is missing.

        Returns {"votes": {channel_id: {playlist_id: count}},
                 "mapping": {channel_id: playlist_id},
                 "channel_titles": {channel_id: title},
                 "playlists_scanned": int, "videos_scanned": int,
                 "all_data_scanned": int}.
        """
        client = self.get_client(require_oauth=True)
        if not client:
            return {"error": "YouTube not connected. OAuth required."}

        # ---- NAME RESOLUTION: primary path is the disk cache (zero quota) ----
        all_data = None
        try:
            all_data = await self._load_from_disk("all_data")
        except Exception as e:  # noqa: BLE001
            log.warning(f"[map_from_playlists] all_data read failed: {e}")

        votes: Dict[str, Dict[str, int]] = {}
        titles: Dict[str, str] = {}
        all_data_scanned = 0
        videos_scanned = 0

        # Primary: harvest names + votes from the cached all_data videos.
        if all_data and all_data.get("videos"):
            for v in all_data["videos"]:
                cid = v.get("channel_id")
                title = v.get("channel_title")
                if not cid:
                    snip = v.get("snippet") or {}
                    cid = snip.get("videoOwnerChannelId") or snip.get("channelId")
                    title = snip.get("videoOwnerChannelTitle") or snip.get("channelTitle")
                if not cid:
                    continue
                pid = v.get("playlist_id")
                if pid:
                    pl_votes = votes.setdefault(cid, {})
                    pl_votes[pid] = pl_votes.get(pid, 0) + 1
                titles.setdefault(cid, title or cid)
                all_data_scanned += 1

        # ---- PLAYLIST ENUMERATION (best-effort; do NOT gate naming on it) ----
        pl_data = await self.list_playlists(force_refresh=False)
        playlists = pl_data.get("playlists") or []
        if not playlists:
            pl_data = await self.list_playlists(force_refresh=True)
            playlists = pl_data.get("playlists") or []

        # Per-playlist cache / live fallback to flesh out any playlists whose
        # videos were NOT in all_data (e.g. playlists fetched after the last
        # all_data build). Skipped entirely if list_playlists is empty.
        for pl in playlists:
            pid = pl.get("id")
            if not pid:
                continue
            # If all_data already contributed votes for this pid, skip re-scan.
            if any(pid in v_counts for v_counts in votes.values()):
                continue
            items = []
            try:
                vdata = await self.get_videos(pid, force_refresh=False)
                items = vdata.get("videos") or []
            except Exception as e:  # noqa: BLE001
                log.warning(f"[map_from_playlists] cache read {pid}: {e}")
                items = []
            if not items and client:
                try:
                    items = await self._fetch_all_paginated(
                        lambda mr, pt, _pid=pid: client.list_videos(_pid, page_token=pt, max_results=mr),
                        max_results=50,
                        max_items=max_items_per_playlist,
                    )
                except Exception as e:  # noqa: BLE001
                    log.warning(f"[map_from_playlists] live {pid}: {e}")
                    continue
            for it in items:
                cid = it.get("channel_id")
                title = it.get("channel_title")
                if not cid:
                    snip = it.get("snippet") or {}
                    cid = snip.get("videoOwnerChannelId") or snip.get("channelId")
                    title = snip.get("videoOwnerChannelTitle") or snip.get("channelTitle")
                if not cid:
                    continue
                pl_votes = votes.setdefault(cid, {})
                pl_votes[pid] = pl_votes.get(pid, 0) + 1
                titles.setdefault(cid, title or cid)
                videos_scanned += 1

        mapping = {
            cid: max(pl_counts.items(), key=lambda kv: kv[1])[0]
            for cid, pl_counts in votes.items()
        }
        return {
            "votes": votes,
            "mapping": mapping,
            "channel_titles": titles,
            "playlists_scanned": len(playlists),
            "videos_scanned": videos_scanned,
            "all_data_scanned": all_data_scanned,
        }

    async def resolve_channel_handles(self, handles: List[str]) -> Dict[str, str]:
        """Resolve YouTube handles to channel IDs via the API-key client
        (channels.list forHandle, ~1 quota unit each, no OAuth needed).
        Handles may or may not include a leading '@'.
        Returns {handle_lower: channel_id} for those that resolved."""
        if not handles:
            return {}
        client = self.get_client(require_oauth=False)
        if not client:
            return {}

        def _lookup() -> Dict[str, str]:
            out: Dict[str, str] = {}
            for h in handles:
                handle = (h or "").strip().lstrip("@")
                if not handle:
                    continue
                try:
                    resp = client.channels().list(part="id,snippet", forHandle=handle).execute()
                    items = resp.get("items") or []
                    if items:
                        cid = items[0].get("id")
                        if cid:
                            out[handle.lower()] = cid
                except Exception as e:  # noqa: BLE001
                    log.warning(f"[resolve_channel_handles] {handle}: {e}")
            return out

        return await asyncio.to_thread(_lookup)


    async def _fetch_all_paginated(self, fetch_fn, max_results: int = 50, max_items: int = 500) -> List[Any]:
        """Fetch paginated results with caps and early exit."""
        all_items = []
        page_token = None
        consecutive_errors = 0
        max_consecutive_errors = 3

        while len(all_items) < max_items:
            # Run the blocking sync fetch_fn in a separate thread to unblock the main FastAPI event loop
            try:
                resp = await asyncio.to_thread(fetch_fn, max_results, page_token)
            except ssl.SSLError as e:
                consecutive_errors += 1
                log.warning(f"_fetch_all_paginated: SSL error ({consecutive_errors}/{max_consecutive_errors}): {e}")
                if consecutive_errors >= max_consecutive_errors:
                    log.error("_fetch_all_paginated: Too many consecutive SSL errors, stopping pagination")
                    break
                continue
            except (ConnectionError, OSError) as e:
                consecutive_errors += 1
                log.warning(f"_fetch_all_paginated: connection error ({consecutive_errors}/{max_consecutive_errors}): {e}")
                if consecutive_errors >= max_consecutive_errors:
                    log.error("_fetch_all_paginated: Too many consecutive connection errors, stopping pagination")
                    break
                continue
            except httpx.HTTPStatusError as e:
                # 4xx errors (401/403/404) won't succeed on retry — raise immediately
                err_msg = f"_fetch_all_paginated: HTTP {e.response.status_code} on API call: {e}. Stopping pagination."
                log.warning(err_msg)
                raise
            except Exception as e:
                log.warning(f"_fetch_all_paginated: fetch_fn raised: {e}. Stopping pagination.")
                break

            # Reset error counter on successful fetch
            consecutive_errors = 0

            if resp is None or "items" not in resp:
                log.warning(f"_fetch_all_paginated: fetch_fn returned None or missing 'items'. Response: {resp}. Stopping pagination.")
                break
            # Check for API-level errors. If the fetch function caught an
            # error and returned it, stop pagination.
            if isinstance(resp, dict) and resp.get("error"):
                log.warning(f"_fetch_all_paginated: fetch_fn returned error: {resp['error']}. Stopping pagination.")
                break
            items = resp.get("items", [])
            all_items.extend(items)

            # Yield control to event loop to prevent blocking on 512MB Render instances
            if len(all_items) % 50 == 0:
                await asyncio.sleep(0)

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

            # Early exit if approaching quota
            if len(all_items) + max_results > max_items:
                log.warning(f"Approaching item cap {max_items}, stopping pagination")
                break

        if len(all_items) >= max_items:
            log.warning(f"_fetch_all_paginated: hit cap at {max_items} items — results may be truncated")
        return all_items[:max_items]


    async def fetch_all_data(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Single-flight wrapper: concurrent callers share one in-flight fetch."""
        async with self._data_lock:
            return await self._fetch_all_data_locked(force_refresh=force_refresh)

    async def _fetch_all_data_locked(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Body of fetch_all_data — must be called while _data_lock is held."""
        if not force_refresh:
            # Check cache first without acquiring the lock
            cached = await self._cache.get("all_data")
            if cached is not None:
                return cached
            disk_data = await self._load_from_disk("all_data")
            if disk_data:
                await self._cache.set("all_data", disk_data, timedelta(minutes=10))
                return disk_data
        # No cache — run the actual fetch
        try:
            result = await self._fetch_all_data_impl(force_refresh=force_refresh)
        except httpx.HTTPStatusError as e:
            log.error(f"[FETCH] HTTP error in fetch_all_data: {e.response.status_code} {e}")
            try:
                detail = e.response.json().get("error", {}).get("message", str(e))
            except Exception:
                detail = str(e)
            return {"error": f"YouTube API error ({e.response.status_code}): {detail}"}
        except Exception as e:
            log.error(f"[FETCH] Unexpected error in fetch_all_data: {e}")
            return {"error": str(e)}
        # Cache the result for subsequent callers
        if "error" not in result:
            await self._cache.set("all_data", result, timedelta(minutes=10))
        return result

    async def _fetch_all_data_impl(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Actual fetch implementation. Caller is responsible for caching."""
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

            # Inline subscription fetching to avoid circular calls
            # (previously delegated to self.list_subscriptions which called fetch_all_data back)
            subscriptions = []
            sub_fetch_error = None
            try:
                all_subs = await self._fetch_all_paginated(
                    lambda max_results, page_token: client.list_mine_subscriptions(max_results=max_results, page_token=page_token),
                    max_results=50,
                    max_items=500,
                )

                if not all_subs:
                    log.warning("[FETCH] Subscriptions returned 0 items (possible API error or auth scope issue)")
                    sub_fetch_error = "API returned 0 subscriptions"

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
                    async with self._enrich_lock:
                        log.info(f"[FETCH] Enriching {len(channel_ids)} channel stats...")
                        try:
                            enriched = await asyncio.to_thread(client.list_channels_by_ids, channel_ids, 50) or {}
                            for item in enriched.get("items", []):
                                cid = item.get("id", "")
                                if cid:
                                    channel_stats[cid] = item
                        except Exception as e:
                            log.warning(f"Channel enrichment failed: {e}")

                # PRIMARY (zero quota): title + avatar from the subscriptions.list
                # snippet, NOT channels.list (quota-blocked on Render).
                for sub in all_subs:
                    snippet = sub.get("snippet", {}) or {}
                    resource = snippet.get("resourceId", {}) or {}
                    cid = resource.get("channelId", "")
                    if not cid:
                        continue
                    # Title + avatar come straight from the subscriptions.list
                    # snippet, which always carries them. Channel stats only
                    # enrich description/subscribers/video+view counts.
                    sub_snip = snippet
                    stats = channel_stats.get(cid, {})
                    st_snip = stats.get("snippet", {}) or {}
                    statistics = stats.get("statistics", {}) or {}
                    title = (sub_snip.get("title") or st_snip.get("title") or "Unknown").strip()
                    thumb = _best_thumbnail(sub_snip.get("thumbnails")) or _best_thumbnail(st_snip.get("thumbnails"))

                    subscriptions.append({
                        "id": cid,
                        "title": title,
                        "thumbnail": thumb,
                        "description": (st_snip.get("description") or sub_snip.get("description", "")),
                        "subscribers": statistics.get("subscriberCount", "0"),
                        "video_count": int(statistics.get("videoCount", "0") or "0"),
                        "view_count": statistics.get("viewCount", "0"),
                        "channel_url": f"https://www.youtube.com/channel/{cid}",
                    })

                subscriptions.sort(key=lambda x: x["title"].lower())
            except Exception as e:
                err_msg = f"Failed to fetch subscriptions: {e}"
                log.warning(err_msg)
                result["subscriptions_error"] = err_msg
            if sub_fetch_error and not result.get("subscriptions_error"):
                result["subscriptions_error"] = sub_fetch_error

            result["subscriptions"] = subscriptions
            result["stats"]["total_subscriptions"] = len(subscriptions)
            
            # Step 2: Fetch all playlists (1 API call with pagination)
            log.info("[FETCH] Getting playlists...")
            playlist_error = None
            try:
                all_playlists = await self._fetch_all_paginated(
                    lambda max_results, page_token: client.list_mine_playlists(max_results=max_results, page_token=page_token),
                    max_results=50,
                    max_items=500,
                )
                if not all_playlists:
                    log.warning("[FETCH] Playlists returned 0 items")
                    playlist_error = "API returned 0 playlists"
                playlists = sorted((self._playlist_item_to_dict(pl) for pl in all_playlists), key=lambda x: x["title"].lower())
                total_videos = sum(pl["video_count"] for pl in playlists)
            except Exception as e:
                playlist_error = f"Failed to fetch playlists: {e}"
                log.warning(playlist_error)
                playlists = []
                total_videos = 0
            result["playlists"] = playlists
            result["stats"]["total_playlists"] = len(playlists)
            result["stats"]["total_videos"] = total_videos
            if playlist_error:
                result["playlists_error"] = playlist_error
            # _set_cached for basic_stats will be handled by its own decorator

            # Step 3: Fetch videos from playlists with duration (BATCH OPTIMIZED)
            log.info(f"[FETCH] Getting video durations for {total_videos} videos...")
            
            videos = []
            total_duration = 0
            
            # Fetch the FULL library — no artificial cap that silently truncates
            # large libraries. The previous caps (10/50 playlists, 500/2000 videos)
            # dropped ~80% of a 9,287-video / 61-playlist library, so duplicate
            # scans run against the synced cache undercounted badly. Both values
            # now exceed the largest known library with headroom. The per-playlist
            # fetch still paginates fully and we stay sequential (Semaphore(1))
            # below to keep Render's heap safe.
            max_playlists = 200 if force_refresh else 150
            max_total_videos = 12000 if force_refresh else 10000

            # Use semaphore to limit concurrent playlist fetches (1 on Render to avoid heap corruption)
            semaphore = asyncio.Semaphore(1)
            
            async def fetch_playlist_videos(playlist):
                pl_id = playlist["id"]
                async with semaphore:
                    try:
                        video_items = await self._fetch_all_paginated(
                            lambda max_results, page_token: client.list_videos(pl_id, max_results=max_results, page_token=page_token),
                            max_results=50,
                            max_items=500,
                        )
                        playlist_videos = []
                        for vid in video_items:
                            try:
                                video = self._video_item_to_dict(vid, pl_id, playlist["title"])
                                playlist_videos.append(video)
                            except (KeyError, ValueError, TypeError) as e:
                                log.warning(f"Skipping malformed video in playlist {pl_id}: {e}")
                                continue
                        return playlist_videos
                    except ssl.SSLError as e:
                        log.warning(f"SSL error fetching videos for playlist {pl_id}: {e}. Skipping playlist.")
                        return []
                    except ConnectionError as e:
                        log.warning(f"Connection error fetching videos for playlist {pl_id}: {e}. Skipping playlist.")
                        return []
                    except Exception as e:
                        log.warning(f"Failed to fetch videos for playlist {pl_id}: {e}. Skipping playlist.")
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
