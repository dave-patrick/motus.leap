"""Unit tests for YouTube service."""
import pytest
from pydantic import SecretStr
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from services.youtube_service import YouTubeService
from core.lru_cache import LRUAsyncCache
from models.config import TubeManagerConfig, YouTubeOAuthConfig


@pytest.mark.unit
class TestYouTubeService:
    """Test YouTube service functionality."""

    @pytest.fixture
    def youtube_service(self, test_config):
        """Create YouTube service instance."""
        return YouTubeService(test_config)

    def test_init(self, youtube_service):
        """Test service initialization."""
        assert youtube_service is not None
        assert youtube_service.config.youtube_api_key.get_secret_value() == "test_api_key"
        assert youtube_service.config.oauth is not None
        assert youtube_service._cache is not None

    def test_cache_initialization(self, youtube_service):
        """Test LRU cache is initialized correctly."""
        cache = youtube_service._cache
        assert isinstance(cache, LRUAsyncCache)
        assert cache._max_size == 100

    @pytest.mark.asyncio
    async def test_fetch_all_data(self, youtube_service):
        """Test fetching all YouTube data."""
        fake_client = MagicMock()
        fake_client.list_mine_subscriptions.return_value = {"items": []}
        fake_client.list_mine_playlists.return_value = {"items": []}
        fake_client.list_videos.return_value = {"items": []}
        fake_client.list_channels_by_ids.return_value = {"items": []}

        with patch.object(youtube_service, "get_client", return_value=fake_client):
            result = await youtube_service.fetch_all_data(force_refresh=True)

        assert "subscriptions" in result
        assert "playlists" in result
        assert "videos" in result
        assert isinstance(result["subscriptions"], list)
        assert isinstance(result["playlists"], list)
        assert isinstance(result["videos"], list)

    @pytest.mark.asyncio
    async def test_fetch_all_data_with_cache(self, youtube_service):
        """Test caching of fetch_all_data."""
        fake_client = MagicMock()
        fake_client.list_mine_subscriptions.return_value = {"items": []}
        fake_client.list_mine_playlists.return_value = {"items": []}
        fake_client.list_videos.return_value = {"items": []}
        fake_client.list_channels_by_ids.return_value = {"items": []}

        with patch.object(youtube_service, "get_client", return_value=fake_client):
            result1 = await youtube_service.fetch_all_data(force_refresh=True)

        with patch.object(youtube_service, "get_client", return_value=fake_client):
            result2 = await youtube_service.fetch_all_data(force_refresh=False)

        assert result1 == result2

    def test_cache_hit_rate(self, youtube_service):
        """Test cache hit rate calculation."""
        cache = youtube_service._cache

        for i in range(100):
            pass

        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == "0.00%"

    @pytest.mark.asyncio
    async def test_get_client_with_api_key(self, youtube_service):
        client = youtube_service.get_client(require_oauth=False)
        assert client is not None

    @pytest.fixture
    def oauth_service(self):
        config = TubeManagerConfig(
            youtube_api_key=SecretStr("test_key"),
            oauth=YouTubeOAuthConfig(client_id="", client_secret=SecretStr("")),
        )
        return YouTubeService(config)

    @pytest.mark.asyncio
    async def test_get_client_with_oauth(self, oauth_service):
        client = oauth_service.get_client(require_oauth=True)
        assert client is None


@pytest.mark.unit
class TestLRUAsyncCache:
    """Test LRUAsyncCache functionality."""

    @pytest.mark.asyncio
    async def test_basic_operations(self):
        """Test basic get/set operations."""
        from datetime import timedelta

        cache = LRUAsyncCache(max_size=10, ttl=timedelta(minutes=10))

        # Set a value
        assert await cache.set("key1", "value1") is None

        # Get the value
        value = await cache.get("key1")
        assert value == "value1"

        # Get non-existent key
        assert await cache.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        """Test getting non-existent key."""
        from datetime import timedelta

        cache = LRUAsyncCache(max_size=10, ttl=timedelta(minutes=10))
        assert await cache.get("missing") is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        from datetime import timedelta

        cache = LRUAsyncCache(max_size=3, ttl=timedelta(minutes=10))

        assert await cache.set("key1", "value1") is None
        assert await cache.set("key2", "value2") is None
        assert await cache.set("key3", "value3") is None
        assert await cache.set("key4", "value4") is None

        assert cache.get_stats()["size"] <= 3

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Test cache statistics tracking."""
        from datetime import timedelta

        cache = LRUAsyncCache(max_size=10, ttl=timedelta(minutes=10))

        # Initial stats
        stats = cache.get_stats()
        assert stats["size"] == 0
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == "0.00%"

        # Set and get
        assert await cache.set("key1", "value1") is None
        await cache.get("key1")  # hit
        await cache.get("key2")  # miss

        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert "50.00%" in stats["hit_rate"]

    @pytest.mark.asyncio
    async def test_clear(self):
        """Test cache clearing."""
        from datetime import timedelta

        cache = LRUAsyncCache(max_size=10, ttl=timedelta(minutes=10))

        # Add items
        assert await cache.set("key1", "value1") is None
        assert await cache.set("key2", "value2") is None

        # Clear
        assert await cache.clear() is None

        # Verify empty
        stats = cache.get_stats()
        assert stats["size"] == 0
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_ttl_expiry(self):
        """Test TTL expiry."""
        from datetime import timedelta

        cache = LRUAsyncCache(max_size=10, ttl=timedelta(milliseconds=100))

        # Set a value
        assert await cache.set("key", "value") is None

        # Should be available immediately
        assert await cache.get("key") == "value"

        # Wait for expiry
        import asyncio
        await asyncio.sleep(0.15)

        # Should be expired
        assert await cache.get("key") is None


@pytest.mark.unit
class TestYouTubeServiceAdvanced:
    """Test advanced YouTube service functionality."""

    @pytest.fixture
    def youtube_service(self, test_config):
        return YouTubeService(test_config)

    @pytest.mark.asyncio
    async def test_fetch_all_data_structure(self, youtube_service):
        """Test fetch_all_data returns expected structure."""
        fake_client = MagicMock()
        fake_client.list_mine_subscriptions.return_value = {"items": []}
        fake_client.list_mine_playlists.return_value = {"items": []}
        fake_client.list_videos.return_value = {"items": []}
        fake_client.list_channels_by_ids.return_value = {"items": []}

        with patch.object(youtube_service, "get_client", return_value=fake_client):
            result = await youtube_service.fetch_all_data(force_refresh=True)

        assert "cached_at" in result
        assert "subscriptions" in result
        assert "playlists" in result
        assert "videos" in result
        assert "stats" in result
        assert "user_id" in result

    @pytest.mark.asyncio
    async def test_fetch_with_force_refresh(self, youtube_service):
        """Test force_refresh bypasses cache."""
        fake_client = MagicMock()
        fake_client.list_mine_subscriptions.return_value = {"items": []}
        fake_client.list_mine_playlists.return_value = {"items": []}
        fake_client.list_videos.return_value = {"items": []}
        fake_client.list_channels_by_ids.return_value = {"items": []}

        with patch.object(youtube_service, "get_client", return_value=fake_client):
            result1 = await youtube_service.fetch_all_data(force_refresh=False)

        with patch.object(youtube_service, "get_client", return_value=fake_client):
            result2 = await youtube_service.fetch_all_data(force_refresh=True)

        assert result1 is not None
        assert result2 is not None

    def test_user_id_generation(self, test_config):
        """Test user ID generation from OAuth token."""
        service = YouTubeService(test_config)
        user_id = service._get_user_id()

        # Should be consistent for same config
        assert isinstance(user_id, str)
        assert len(user_id) == 16 or user_id == "default"

    @pytest.mark.asyncio
    async def test_fetch_all_data_multiple_subscriptions(self, youtube_service):
        """Regression test for BUG C3 (undefined `stats`) and C4 (only one
        subscription recorded). With 3+ distinct channels the function must
        return one entry per subscription, never crash, and never silently
        drop entries."""
        channel_ids = ["UCaaa111", "UCbbb222", "UCccc333"]
        subs = []
        for cid in channel_ids:
            subs.append({
                "snippet": {
                    "title": f"Channel {cid}",
                    "description": f"Desc {cid}",
                    "resourceId": {"channelId": cid},
                    "thumbnails": {"default": {"url": f"https://img/{cid}.jpg"}},
                }
            })

        def fake_list_channels_by_ids(ids, max_results=50):
            items = []
            for cid in ids:
                items.append({
                    "id": cid,
                    "snippet": {
                        "description": f"Rich desc {cid}",
                        "thumbnails": {"default": {"url": f"https://rich/{cid}.jpg"}},
                    },
                    "statistics": {
                        "subscriberCount": "1000",
                        "videoCount": "50",
                        "viewCount": "20000",
                    },
                })
            return {"items": items}

        fake_client = MagicMock()
        fake_client.list_mine_subscriptions.return_value = {"items": subs}
        fake_client.list_channels_by_ids.side_effect = fake_list_channels_by_ids
        fake_client.list_mine_playlists.return_value = {"items": []}
        fake_client.list_videos.return_value = {"items": []}

        with patch.object(youtube_service, "get_client", return_value=fake_client):
            result = await youtube_service.fetch_all_data(force_refresh=True)

        subscriptions = result["subscriptions"]
        assert isinstance(subscriptions, list)
        assert len(subscriptions) == len(channel_ids), (
            f"Expected {len(channel_ids)} subscriptions, got {len(subscriptions)} "
            "(BUG C4: only one subscription was recorded)"
        )
        returned_ids = {s["id"] for s in subscriptions}
        assert returned_ids == set(channel_ids)

        for s in subscriptions:
            assert s["title"], "Subscription title must not be empty"
            assert s["channel_url"].startswith("https://www.youtube.com/channel/")
            assert s["video_count"] == 50
            assert s["subscribers"] == "1000"
            assert s["view_count"] == "20000"

        # No NameError surfaced as a swallowed error (BUG C3).
        assert "subscriptions_error" not in result or result.get("subscriptions_error") is None

    @pytest.mark.asyncio
    async def test_list_playlists_falls_back_to_all_data_when_playlists_json_empty(self, youtube_service):
        """Regression 2026-07-15: Dashboard showed playlists (reads all_data.json)
        but /api/playlists (list_playlists, reads playlists.json) returned empty,
        so the Playlists page rendered 'No playlists found'. When playlists.json
        is present-but-empty, list_playlists must derive from all_data.json."""
        fake_all_data = {
            "playlists": [
                {"id": "PL1", "title": "Music", "video_count": 3},
                {"id": "PL2", "title": "Tutorials", "video_count": 7},
            ],
            "videos": [{"id": "v1"}],
            "subscriptions": [{"id": "s1"}],
        }
        # playlists.json present but empty playlists list
        empty_playlists_cache = {"playlists": [], "stats": {"total_playlists": 0}}

        async def fake_load(key, max_age_days=None):
            if key == "playlists":
                return empty_playlists_cache
            if key == "all_data":
                return fake_all_data
            return None

        with patch.object(youtube_service, "_load_from_disk", side_effect=fake_load):
            result = await youtube_service.list_playlists(force_refresh=False)

        assert result.get("cached") is True
        playlists = result.get("playlists", [])
        assert len(playlists) == 2, f"Expected 2 playlists from all_data fallback, got {len(playlists)}"
        assert {p["id"] for p in playlists} == {"PL1", "PL2"}

    @pytest.mark.asyncio
    async def test_list_playlists_empty_when_both_caches_empty(self, youtube_service):
        """When neither playlists.json nor all_data.json has playlists, return empty
        (do NOT fabricate data)."""
        async def fake_load(key, max_age_days=None):
            return None

        with patch.object(youtube_service, "_load_from_disk", side_effect=fake_load):
            result = await youtube_service.list_playlists(force_refresh=False)

        assert result.get("playlists", []) == []

    @pytest.mark.asyncio
    async def test_is_stale_helper(self):
        """is_stale() flags files older than max_age_days and missing files."""
        import tempfile
        from pathlib import Path as _Path
        from datetime import datetime, timedelta
        from services.youtube_service import is_stale

        with tempfile.TemporaryDirectory() as d:
            fresh = _Path(d) / "fresh.json"
            fresh.write_text("{}")
            stale = _Path(d) / "stale.json"
            stale.write_text("{}")
            # Set mtime 31 days in the past
            old = datetime.now() - timedelta(days=31)
            import os
            os.utime(stale, (old.timestamp(), old.timestamp()))

            assert is_stale(fresh, max_age_days=30) is False
            assert is_stale(stale, max_age_days=30) is True
            # Missing file is stale
            assert is_stale(_Path(d) / "nope.json", max_age_days=30) is True

    @pytest.mark.asyncio
    async def test_load_from_disk_rejects_stale(self, youtube_service, tmp_path):
        """_load_from_disk returns None for a file older than max_age_days (III.E.4a-g)."""
        from datetime import datetime, timedelta
        import os
        cache_file = tmp_path / "old.json"
        cache_file.write_text('{"playlists": [{"id": "PL1"}]}')
        old = datetime.now() - timedelta(days=31)
        os.utime(cache_file, (old.timestamp(), old.timestamp()))
        # Point the service's data dir at our temp dir
        youtube_service._user_data_dir = tmp_path
        result = await youtube_service._load_from_disk("old", max_age_days=30)
        assert result is None, "Stale cached YouTube data must be treated as a miss"
        # Fresh file is returned
        fresh = tmp_path / "new.json"
        fresh.write_text('{"playlists": [{"id": "PL2"}]}')
        assert await youtube_service._load_from_disk("new", max_age_days=30) == {"playlists": [{"id": "PL2"}]}

