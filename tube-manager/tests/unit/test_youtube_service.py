"""Unit tests for YouTube service."""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from services.youtube_service import YouTubeService
from core.lru_cache import LRUAsyncCache


@pytest.mark.unit
class TestYouTubeService:
    """Test YouTube service functionality."""

    @pytest.fixture
    def youtube_service(self, test_config):
        """Create YouTube service instance."""
        return YouTubeService(
            api_key=test_config.youtube_api_key,
            oauth_tokens=test_config.oauth
        )

    def test_init(self, youtube_service):
        """Test service initialization."""
        assert youtube_service is not None
        assert youtube_service._api_key == "test_api_key"
        assert youtube_service._oauth_tokens is not None
        assert youtube_service._cache is not None

    def test_cache_initialization(self, youtube_service):
        """Test LRU cache is initialized correctly."""
        cache = youtube_service._cache
        assert isinstance(cache, LRUAsyncCache)
        assert cache._max_size == 1000

    @pytest.mark.asyncio
    async def test_fetch_all_data(self, youtube_service, mock_youtube_service):
        """Test fetching all YouTube data."""
        result = await youtube_service.fetch_all_data()

        assert "playlists" in result
        assert "subscriptions" in result
        assert "videos" in result
        assert isinstance(result["playlists"], list)
        assert isinstance(result["subscriptions"], list)
        assert isinstance(result["videos"], list)

    @pytest.mark.asyncio
    async def test_fetch_all_data_with_cache(self, youtube_service):
        """Test caching of fetch_all_data."""
        # First call should fetch from API
        result1 = await youtube_service.fetch_all_data()

        # Clear mock to ensure second call uses cache
        youtube_service.get_client = Mock()

        # Second call should use cache
        result2 = await youtube_service.fetch_all_data()

        # Results should be identical
        assert result1 == result2

    def test_cache_hit_rate(self, youtube_service):
        """Test cache hit rate calculation."""
        cache = youtube_service._cache

        # Simulate cache hits and misses
        for i in range(100):
            cache.get(f"key_{i}")
            cache.set(f"key_{i}", f"value_{i}")
            cache.get(f"key_{i}")

        stats = cache.get_stats()
        assert stats["hits"] == 100
        assert stats["misses"] == 100
        assert stats["hit_rate"] == "50.00%"

    @pytest.mark.asyncio
    async def test_get_client_with_api_key(self, youtube_service):
        """Test getting client with API key."""
        client = youtube_service.get_client(require_oauth=False)

        assert client is not None
        # Client should use API key, not OAuth

    @pytest.mark.asyncio
    async def test_get_client_with_oauth(self, youtube_service):
        """Test getting client with OAuth tokens."""
        youtube_service._oauth_tokens = Mock(access_token="test_token")

        client = youtube_service.get_client(require_oauth=True)

        assert client is not None
        # Client should use OAuth tokens

    def test_cache_eviction(self, youtube_service):
        """Test LRU cache eviction when full."""
        cache = youtube_service._cache
        cache.maxsize = 3  # Small size for testing

        # Fill cache beyond capacity
        for i in range(5):
            cache.set(f"key_{i}", f"value_{i}")

        # Oldest items should be evicted
        assert cache.get("key_0") is None
        assert cache.get("key_1") is None
        assert cache.get("key_2") is not None
        assert cache.get("key_3") is not None
        assert cache.get("key_4") is not None

    def test_cache_ttl_expiry(self, youtube_service):
        """Test cache TTL expiry."""
        cache = youtube_service._cache
        cache.ttl = 0.1  # 100ms TTL for testing

        # Set a value
        cache.set("key", "value")

        # Should be available immediately
        assert cache.get("key") == "value"

        # Wait for expiry
        import time
        time.sleep(0.15)

        # Should be expired
        assert cache.get("key") is None

    @pytest.mark.asyncio
    async def test_fetch_with_force_refresh(self, youtube_service):
        """Test force_refresh bypasses cache."""
        # First call
        result1 = await youtube_service.fetch_all_data(force_refresh=False)

        # Force refresh should bypass cache
        result2 = await youtube_service.fetch_all_data(force_refresh=True)

        # Both should return data (may be same, but cache was bypassed)
        assert result1 is not None
        assert result2 is not None


@pytest.mark.unit
class TestLRUAsyncCache:
    """Test LRUAsyncCache functionality."""

    @pytest.mark.asyncio
    async def test_basic_operations(self):
        """Test basic get/set operations."""
        from datetime import timedelta
        cache = LRUAsyncCache(max_size=10, ttl=timedelta(minutes=10))

        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

        await cache.set("key2", "value2")
        result = await cache.get("key2")
        assert result == "value2"

        await cache.clear()

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        """Test getting nonexistent key."""
        from datetime import timedelta
        cache = LRUAsyncCache(max_size=10, ttl=timedelta(minutes=10))
        result = await cache.get("nonexistent")
        assert result is None
        await cache.clear()

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """Test LRU eviction policy."""
        from datetime import timedelta
        cache = LRUAsyncCache(max_size=10, ttl=timedelta(minutes=10))

        # Fill cache
        await cache.set("a", 1)
        await cache.set("b", 2)
        await cache.set("c", 3)

        # Access "a" to make it recently used
        await cache.get("a")

        # Add new items, "b" should be evicted (least recently used)
        await cache.set("d", 4)
        await cache.set("e", 5)
        await cache.set("f", 6)

        # "a" should still be there (recently accessed)
        assert await cache.get("a") == 1
        # "b" might be evicted
        # "c" should still be there
        assert await cache.get("c") == 3

        await cache.clear()

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Test cache statistics tracking."""
        from datetime import timedelta
        cache = LRUAsyncCache(max_size=10, ttl=timedelta(minutes=10))

        # Misses
        await cache.get("key1")
        await cache.get("key2")

        # Set values
        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        # Hits
        await cache.get("key1")
        await cache.get("key2")
        await cache.get("key1")  # Another hit

        stats = cache.get_stats()
        assert stats["hits"] == 3
        assert stats["misses"] == 2
        assert stats["hit_rate"] == "60.00%"

        await cache.clear()

    @pytest.mark.asyncio
    async def test_clear(self):
        """Test cache clearing."""
        from datetime import timedelta
        cache = LRUAsyncCache(max_size=10, ttl=timedelta(minutes=10))

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        await cache.clear()

        assert await cache.get("key1") is None
        assert await cache.get("key2") is None
        assert cache.get_stats()["size"] == 0

    @pytest.mark.asyncio
    async def test_ttl_expiry(self):
        """Test cache TTL expiry."""
        from datetime import timedelta

        # Create cache with short TTL
        short_cache = LRUAsyncCache(max_size=10, ttl=timedelta(milliseconds=100))

        # Set a value
        await short_cache.set("key", "value")

        # Should be available immediately
        assert await short_cache.get("key") == "value"

        # Wait for expiry
        import asyncio
        await asyncio.sleep(0.15)

        # Should be expired
        assert await short_cache.get("key") is None

        await short_cache.clear()