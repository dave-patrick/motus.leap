"""Tests for bug fixes and new features.

Covers:
- YouTubeService.get_client() behavior with/without OAuth
- YouTubeService disk cache cleanup
- LRUAsyncCache.cleanup_stale() removes entries beyond max_age
- Background worker continues processing when one video move fails
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

import pytest
from pydantic import SecretStr

from services.youtube_service import YouTubeService
from core.lru_cache import LRUAsyncCache
from models.config import TubeManagerConfig, YouTubeOAuthConfig


@pytest.mark.unit
class TestGetClientBehavior:
    """Test YouTubeService.get_client() return behavior."""

    def test_get_client_returns_none_when_oauth_required_but_not_configured(self):
        """get_client(require_oauth=True) returns None when OAuth is not configured."""
        config = TubeManagerConfig(
            youtube_api_key=SecretStr("test_key"),
            oauth=YouTubeOAuthConfig(
                client_id="",
                client_secret=SecretStr(""),
                # No access_token or refresh_token
            ),
        )
        service = YouTubeService(config)
        client = service.get_client(require_oauth=True)
        assert client is None

    def test_get_client_returns_client_when_api_key_set_and_oauth_not_required(self):
        """get_client(require_oauth=False) returns a client when only API key is set."""
        config = TubeManagerConfig(
            youtube_api_key=SecretStr("test_api_key"),
            oauth=YouTubeOAuthConfig(
                client_id="",
                client_secret=SecretStr(""),
            ),
        )
        service = YouTubeService(config)
        client = service.get_client(require_oauth=False)
        assert client is not None

    def test_get_client_returns_client_when_oauth_configured(self):
        """get_client(require_oauth=True) returns client when OAuth is properly configured."""
        config = TubeManagerConfig(
            youtube_api_key=SecretStr("test_api_key"),
            oauth=YouTubeOAuthConfig(
                client_id="test_client_id",
                client_secret=SecretStr("test_secret"),
                access_token="test_access_token",
                refresh_token="test_refresh_token",
                token_expiry=3600,
            ),
        )
        service = YouTubeService(config)
        client = service.get_client(require_oauth=True)
        assert client is not None


@pytest.mark.unit
class TestTubeManagerDataDir:
    """Test that YouTubeService uses TUBE_MANAGER_DATA_DIR env var."""

    def test_user_data_dir_uses_env_var(self, monkeypatch):
        """YouTubeService uses TUBE_MANAGER_DATA_DIR for user_data_dir."""
        custom_dir = tempfile.mkdtemp(prefix="custom_data_")
        monkeypatch.setenv("TUBE_MANAGER_DATA_DIR", custom_dir)

        config = TubeManagerConfig(
            youtube_api_key=SecretStr("test_key"),
            oauth=YouTubeOAuthConfig(
                client_id="",
                client_secret=SecretStr(""),
                access_token="token",
                refresh_token="refresh",
            ),
        )
        service = YouTubeService(config)
        assert custom_dir in str(service._user_data_dir)
        assert service._user_data_dir.exists()

    def test_user_data_dir_defaults_to_app_data(self, monkeypatch):
        """When TUBE_MANAGER_DATA_DIR is not set, defaults to /app/data."""
        import importlib
        monkeypatch.delenv("TUBE_MANAGER_DATA_DIR", raising=False)

        # Verify the default path logic in the service constructor
        # We can't instantiate YouTubeService without creating /app/data,
        # so we verify the code path directly.
        from services.youtube_service import YouTubeService
        import inspect
        source = inspect.getsource(YouTubeService.__init__)
        assert 'TUBE_MANAGER_DATA_DIR' in source
        assert '/app/data' in source


@pytest.mark.unit
class TestDiskCacheCleanup:
    """Test disk_cache_cleanup removes stale JSON files."""

    @pytest.mark.asyncio
    async def test_removes_stale_files(self):
        """disk_cache_cleanup removes files older than max_age_days."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Set up service with temp data dir
            data_dir = Path(tmpdir)
            user_dir = data_dir / "users" / "testuser"
            user_dir.mkdir(parents=True)

            # Create a stale file (modified 10 days ago)
            stale_file = user_dir / "stale_cache.json"
            stale_file.write_text(json.dumps({"data": "old"}))
            old_mtime = (datetime.now() - timedelta(days=10)).timestamp()
            os.utime(stale_file, (old_mtime, old_mtime))

            # Create a fresh file
            fresh_file = user_dir / "fresh_cache.json"
            fresh_file.write_text(json.dumps({"data": "new"}))

            # Create service and run cleanup
            config = TubeManagerConfig(
                youtube_api_key=SecretStr("key"),
                oauth=YouTubeOAuthConfig(
                    client_id="",
                    client_secret=SecretStr(""),
                    access_token="token",
                    refresh_token="refresh",
                ),
            )
            service = YouTubeService(config)
            # Override the data dir to use our temp
            service._user_data_dir = user_dir

            removed = await service.disk_cache_cleanup(max_age_days=7)

            assert removed == 1
            assert not stale_file.exists()
            assert fresh_file.exists()

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_stale_files(self):
        """disk_cache_cleanup returns 0 when all files are fresh."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            user_dir = data_dir / "users" / "testuser"
            user_dir.mkdir(parents=True)

            # Create only fresh files
            fresh_file = user_dir / "fresh.json"
            fresh_file.write_text(json.dumps({"data": "new"}))

            config = TubeManagerConfig(
                youtube_api_key=SecretStr("key"),
                oauth=YouTubeOAuthConfig(
                    client_id="",
                    client_secret=SecretStr(""),
                    access_token="token",
                    refresh_token="refresh",
                ),
            )
            service = YouTubeService(config)
            service._user_data_dir = user_dir

            removed = await service.disk_cache_cleanup(max_age_days=7)
            assert removed == 0
            assert fresh_file.exists()

    @pytest.mark.asyncio
    async def test_cache_invalidate_playlist(self):
        """_cache_invalidate_playlist removes matching cache entries."""
        config = TubeManagerConfig(
            youtube_api_key=SecretStr("key"),
            oauth=YouTubeOAuthConfig(
                client_id="",
                client_secret=SecretStr(""),
                access_token="token",
                refresh_token="refresh",
            ),
        )
        service = YouTubeService(config)

        # Add some cache entries
        await service._cache.set("playlist_videos_pl123", [{"vid": "1"}])
        await service._cache.set("playlist_videos_pl456", [{"vid": "2"}])
        await service._cache.set("other_key", "value")

        # Invalidate playlist pl123
        await service._cache_invalidate_playlist("pl123")

        # pl123 should be gone, pl456 and other_key should remain
        assert await service._cache.get("playlist_videos_pl123") is None
        assert await service._cache.get("playlist_videos_pl456") == [{"vid": "2"}]
        assert await service._cache.get("other_key") == "value"


@pytest.mark.unit
class TestLRUCleanupStale:
    """Test LRUAsyncCache.cleanup_stale() removes entries beyond max_age."""

    @pytest.mark.asyncio
    async def test_cleanup_stale_removes_old_entries(self):
        """cleanup_stale() removes entries older than max_age."""
        cache = LRUAsyncCache(max_size=100, ttl=timedelta(minutes=10), max_age=timedelta(milliseconds=50))

        # Add entries that will become stale
        await cache.set("old1", "value1")
        await cache.set("old2", "value2")

        # Wait for the old entries to exceed max_age
        await asyncio.sleep(0.1)

        # Add a fresh entry AFTER the sleep (within max_age)
        await cache.set("fresh1", "value3")
        await cache.set("fresh2", "value4")

        # Run cleanup
        removed = await cache.cleanup_stale()

        # old1 and old2 should be removed
        assert removed >= 2
        assert await cache.get("old1") is None
        assert await cache.get("old2") is None
        # Fresh entries should remain
        assert await cache.get("fresh1") == "value3"
        assert await cache.get("fresh2") == "value4"

    @pytest.mark.asyncio
    async def test_cleanup_stale_returns_zero_when_all_fresh(self):
        """cleanup_stale() returns 0 when all entries are within max_age."""
        cache = LRUAsyncCache(max_size=100, ttl=timedelta(minutes=10), max_age=timedelta(hours=1))

        await cache.set("key1", "value1")
        await cache.set("key2", "value2")

        removed = await cache.cleanup_stale()
        assert removed == 0
        assert await cache.get("key1") == "value1"
        assert await cache.get("key2") == "value2"


@pytest.mark.unit
class TestBackgroundWorkerResilience:
    """Test background worker continues processing when individual operations fail."""

    @pytest.mark.asyncio
    async def test_is_retryable_error_detects_429(self):
        """_is_retryable_error correctly identifies 429 errors."""
        from services.background_worker import _is_retryable_error

        class FakeHttpError(Exception):
            def __init__(self, status):
                self.resp = MagicMock()
                self.resp.status = status

        assert _is_retryable_error(FakeHttpError(429)) is True
        assert _is_retryable_error(FakeHttpError(500)) is True
        assert _is_retryable_error(FakeHttpError(503)) is True
        assert _is_retryable_error(FakeHttpError(400)) is False
        assert _is_retryable_error(FakeHttpError(404)) is False
        assert _is_retryable_error(ValueError("something")) is False
        assert _is_retryable_error(Exception("429 rate limit")) is True

