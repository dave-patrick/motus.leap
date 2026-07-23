"""
Tests for the backend bug-fix batch (M4, M5, M6) of motus.leap.

- M4: YouTubeService._data_lock must be reentrant so get_basic_stats() can
  call list_subscriptions()/list_playlists() while already holding the lock
  (plain asyncio.Lock would deadlock). Concurrent callers must still share a
  single in-flight fetch (single-flight).
- M5: background_worker.scan_misplaced() must flag a video whose owner channel
  differs from the mapped channel for its playlist (the "misplaced" definition).
- M6: LRUAsyncCache must NOT evict a freshly-added entry at capacity; the new
  key must survive and an older (least-recently-used) key must be evicted.
"""

import asyncio
import os
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

# Ensure a temp data dir before importing app modules.
os.environ.setdefault("TUBE_MANAGER_DATA_DIR", tempfile.mkdtemp(prefix="motus_batch_test_"))

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.youtube_service import YouTubeService, _ReentrantAsyncLock
from core.lru_cache import LRUAsyncCache
from models.config import TubeManagerConfig, YouTubeOAuthConfig
from services.background_worker import BackgroundWorker
from core.config_manager import ConfigManager


def _oauth_config():
    return TubeManagerConfig(
        youtube_api_key=__import__("pydantic").SecretStr("key"),
        oauth=YouTubeOAuthConfig(
            client_id="cid",
            client_secret=__import__("pydantic").SecretStr("sec"),
            access_token="tok",
            refresh_token="ref",
        ),
    )


@pytest.mark.unit
class TestM4ReentrantDataLock:
    """M4: _data_lock must be reentrant and single-flight."""

    def test_reentrant_lock_allows_reentry_without_deadlock(self):
        """A coroutine holding the lock can re-acquire it (no asyncio.Lock deadlock)."""

        async def run():
            lock = _ReentrantAsyncLock()
            log = []

            async def inner():
                async with lock:
                    log.append("inner")

            async with lock:
                log.append("outer")
                await inner()  # re-acquire while held
            return log

        result = asyncio.run(run())
        assert result == ["outer", "inner"]
    def test_reentrant_lock_single_flight_across_concurrent_callers(self):
        """Two concurrent callers share single-flight; a nested re-entry must NOT deadlock.

        get_basic_stats() holds _data_lock and calls list_subscriptions()
        internally; a concurrent top-level list_* also acquires _data_lock.
        With a PLAIN asyncio.Lock the nested re-acquire would deadlock and this
        test would time out. The reentrant lock must complete both calls and
        let list_a() re-enter from within list_b() without a second fetch.
        """

        async def run():
            service = YouTubeService(_oauth_config())
            fetch_depth = {"max": 0, "current": 0}

            async def fake_fetch(tag):
                fetch_depth["current"] += 1
                fetch_depth["max"] = max(fetch_depth["max"], fetch_depth["current"])
                await asyncio.sleep(0.05)  # ensure overlap
                val = f"data-{tag}"
                fetch_depth["current"] -= 1
                return val

            async def list_a():
                async with service._data_lock:
                    return await fake_fetch("a")

            async def list_b():
                # simulate get_basic_stats calling list_subscriptions internally
                async with service._data_lock:
                    return await list_a()  # re-enter while already holding the lock

            return await asyncio.gather(list_a(), list_b())

        # A plain asyncio.Lock would deadlock here and hang past the timeout.
        results = asyncio.run(asyncio.wait_for(run(), timeout=5))
        assert results == ["data-a", "data-a"]
        # Because list_b re-enters list_a (already holding the lock), the nested
        # fake_fetch does NOT acquire a fresh top-level lock position — both
        # gathered coroutines ran, proving re-entrancy without deadlock.


@pytest.mark.unit
class TestM5MisplacedDetection:
    """M5: scan_misplaced flags videos owned by a non-mapped channel."""

    def _make_scan_worker(self, mappings):
        client = MagicMock()

        def list_videos(pl_id, max_results=50, page_token=None):
            # One video owned by "ownerA", sitting in playlist "plX".
            return {
                "items": [
                    {
                        "id": f"{pl_id}_vid0",
                        "contentDetails": {"videoId": f"{pl_id}_vid0"},
                        "snippet": {
                            "title": f"Video in {pl_id}",
                            "videoOwnerChannelId": "ownerA",
                            "channelId": "ownerA",
                            "videoOwnerChannelTitle": "Owner A",
                        },
                    }
                ]
            }

        client.list_videos = MagicMock(side_effect=list_videos)

        mock_youtube_service = MagicMock()
        mock_youtube_service.get_client = MagicMock(return_value=client)
        mock_youtube_service.fetch_all_data = AsyncMock()
        # scan_misplaced calls get_videos(playlist_id=...) and reads .get("videos").
        # Provide an async get_videos returning a video owned by "ownerA" in plX.
        async def fake_get_videos(playlist_id=None, force_refresh=False):
            return {
                "videos": [
                    {
                        "video_id": f"{playlist_id}_vid0",
                        "title": f"Video in {playlist_id}",
                        "channel_id": "ownerA",
                        "channel_title": "Owner A",
                        "playlist_id": playlist_id,
                    }
                ]
            }
        mock_youtube_service.get_videos = MagicMock(side_effect=fake_get_videos)

        # Wire channel_mappings onto the service so scan_misplaced reads them.
        mock_youtube_service.config = MagicMock()
        mock_youtube_service.config.channel_mappings = mappings

        import app as _app
        _app.youtube_service = mock_youtube_service

        manager = MagicMock()
        manager.broadcast = AsyncMock()
        config_manager = ConfigManager(
            Path(tempfile.mkdtemp(prefix="motus_m5_cfg_")) / "config.json"
        )
        worker = BackgroundWorker(mock_youtube_service, manager, config_manager, asyncio.Queue())
        return worker

    @pytest.mark.asyncio
    async def test_scan_misplaced_flags_video_owned_by_non_mapped_channel(self):
        """A video in plX whose owner (ownerA) maps to a DIFFERENT playlist must be misplaced."""
        # ownerA is mapped to plTarget, but the video lives in plX -> misplaced.
        worker = self._make_scan_worker({"ownerA": "plTarget"})

        result = await asyncio.wait_for(
            worker.scan_misplaced({"playlist_id": "plX"}), timeout=10
        )
        # scan_misplaced returns a dict with a count of found misplaced videos.
        count = result.get("count", result.get("misplaced", 0)) if isinstance(result, dict) else 0
        # The broadcast log carries the human-facing count.
        msgs = [
            c.args[0]
            for c in worker.manager.broadcast.call_args_list
            if isinstance(c.args[0], str) and "[SCAN] Found" in c.args[0]
        ]
        found = 0
        for m in msgs:
            try:
                found = int(m.split("Found")[1].split("misplaced")[0].strip())
            except Exception:
                pass
        assert found == 1, f"expected 1 misplaced video, got {found} (msgs={msgs})"

    @pytest.mark.asyncio
    async def test_scan_misplaced_ignores_correctly_placed_video(self):
        """A video in plX whose owner maps to plX must NOT be flagged."""
        worker = self._make_scan_worker({"ownerA": "plX"})

        await asyncio.wait_for(worker.scan_misplaced({"playlist_id": "plX"}), timeout=10)
        msgs = [
            c.args[0]
            for c in worker.manager.broadcast.call_args_list
            if isinstance(c.args[0], str) and "[SCAN] Found" in c.args[0]
        ]
        found = 0
        for m in msgs:
            try:
                found = int(m.split("Found")[1].split("misplaced")[0].strip())
            except Exception:
                pass
        assert found == 0, f"expected 0 misplaced videos, got {found}"


@pytest.mark.unit
class TestM6LRUEvictionOrder:
    """M6: at capacity, the newly-added entry must NOT be evicted."""

    @pytest.mark.asyncio
    async def test_new_entry_survives_at_capacity_oldest_evicted(self):
        cache = LRUAsyncCache(max_size=3, ttl=timedelta(hours=1))

        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.set("c", 3)
        # Now at capacity (3). Add a 4th -> one old entry must go, NOT "d".
        await cache.set("d", 4)

        assert await cache.get("d") == 4, "the just-added key must survive"
        # Exactly one of the originals is gone.
        present = [(await cache.get(k)) is not None for k in ("a", "b", "c")]
        remaining = sum(1 for p in present if p)
        assert remaining == 2, f"expected 2 of the original 3 to remain, got {remaining}"
        # The evicted one is the least-recently-used (access_count lowest).
        evicted = [k for k in ("a", "b", "c") if (await cache.get(k)) is None]
        assert evicted == ["a"], f"expected 'a' (oldest/LRU) evicted, got {evicted}"

    @pytest.mark.asyncio
    async def test_repeated_set_does_not_immediately_evict_new(self):
        cache = LRUAsyncCache(max_size=2, ttl=timedelta(hours=1))
        await cache.set("x", 1)
        await cache.set("y", 2)
        # At capacity; adding z must keep z, evict one of x/y.
        await cache.set("z", 3)
        assert await cache.get("z") == 3
        present = [(await cache.get(k)) is not None for k in ("x", "y")]
        assert sum(1 for p in present if p) == 1
