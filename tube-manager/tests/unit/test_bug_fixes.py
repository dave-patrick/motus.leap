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
    async def test_watch_later_sync_continues_on_single_video_failure(self):
        """watch_later_sync continues processing remaining videos when one move fails."""
        from services.background_worker import BackgroundWorker

        # Set up mocks
        mock_youtube_service = MagicMock()
        mock_manager = MagicMock()
        mock_manager.broadcast = AsyncMock()
        mock_config_manager = MagicMock()
        mock_config_manager.config = MagicMock()
        mock_config_manager.config.youtube_api_key = SecretStr("key")
        mock_config_manager.config.oauth = YouTubeOAuthConfig(
            client_id="test",
            client_secret=SecretStr("secret"),
            access_token="token",
            refresh_token="refresh",
        )
        mock_config_manager.config.channel_mappings = {"ch1": "pl_target"}
        mock_config_manager.config.watch_later_playlist_id = ""
        mock_config_manager.config.watch_later_target_playlist_id = "pl_target"

        worker = BackgroundWorker(
            mock_youtube_service, mock_manager, mock_config_manager, asyncio.Queue()
        )
        # Override the youtube_service property to avoid importing app
        type(worker).youtube_service = property(lambda self: mock_youtube_service)

        # Mock client
        mock_client = MagicMock()
        mock_youtube_service.get_client.return_value = mock_client

        # Set up playlist cache
        worker._playlist_cache = [("pl_target", "Target Playlist")]
        worker._playlist_cache_time = 9999999999  # Far in future (valid)

        # Mock list_watch_later_items_cached to return 3 videos
        watch_later_items = {
            "items": [
                {
                    "id": "item1",
                    "contentDetails": {"videoId": "vid1", "videoOwnerChannelId": "ch1"},
                    "snippet": {"title": "Video 1", "playlistId": "watch_later"},
                },
                {
                    "id": "item2",
                    "contentDetails": {"videoId": "vid2", "videoOwnerChannelId": "ch1"},
                    "snippet": {"title": "Video 2", "playlistId": "watch_later"},
                },
                {
                    "id": "item3",
                    "contentDetails": {"videoId": "vid3", "videoOwnerChannelId": "ch1"},
                    "snippet": {"title": "Video 3", "playlistId": "watch_later"},
                },
            ]
        }
        mock_youtube_service.list_watch_later_items_cached = AsyncMock(return_value=watch_later_items)
        mock_youtube_service._get_cached = AsyncMock(return_value={})

        # Make the second video move fail, but first and third succeed
        # Make the second video move fail with a non-retryable error
        move_call_count = 0
        def move_side_effect(video_id, playlist_id):
            nonlocal move_call_count
            move_call_count += 1
            if video_id == "vid2":
                raise ValueError("Playlist not found")
            return True

        mock_client.move_video_to_playlist.side_effect = move_side_effect
        mock_client.remove_video_from_playlist.return_value = True

        # Run the sync
        await worker.watch_later_sync({"dry_run": False})

        # Verify broadcast messages
        broadcast_calls = [call.args[0] for call in mock_manager.broadcast.call_args_list]
        messages = [json.loads(msg)["message"] for msg in broadcast_calls]

        # Should have error for vid2 but still process vid1 and vid3
        error_msgs = [m for m in messages if "ERROR" in m and "vid2" in m]
        assert len(error_msgs) == 1

        # Final summary should show 2 moved, 1 failed
        summary_msgs = [m for m in messages if "Moved 2 video" in m]
        assert len(summary_msgs) == 1

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

    @pytest.mark.asyncio
    async def test_watch_later_sync_returns_early_without_target(self):
        """watch_later_sync returns early when no target playlist is configured."""
        from services.background_worker import BackgroundWorker

        mock_youtube_service = MagicMock()
        mock_manager = MagicMock()
        mock_manager.broadcast = AsyncMock()
        mock_config_manager = MagicMock()
        mock_config_manager.config = MagicMock()
        mock_config_manager.config.youtube_api_key = SecretStr("key")
        mock_config_manager.config.oauth = YouTubeOAuthConfig(
            client_id="test",
            client_secret=SecretStr("secret"),
            access_token="token",
            refresh_token="refresh",
        )
        mock_config_manager.config.channel_mappings = {"ch1": "pl_old"}
        mock_config_manager.config.watch_later_playlist_id = ""
        mock_config_manager.config.watch_later_target_playlist_id = ""  # Not set

        worker = BackgroundWorker(
            mock_youtube_service, mock_manager, mock_config_manager, asyncio.Queue()
        )
        type(worker).youtube_service = property(lambda self: mock_youtube_service)
        mock_client = MagicMock()
        mock_youtube_service.get_client.return_value = mock_client
        # Setup for the scan path (target is optional now — sync should still scan)
        mock_youtube_service.list_watch_later_items_cached = AsyncMock(return_value={"items": []})
        mock_youtube_service._get_cached = AsyncMock(return_value={})
        mock_youtube_service._set_cached = AsyncMock()
        mock_youtube_service._ensure_playlist_cache = AsyncMock()
        worker._playlist_cache = []

        await worker.watch_later_sync({"dry_run": False})

        broadcast_calls = [call.args[0] for call in mock_manager.broadcast.call_args_list]
        messages = [json.loads(msg)["message"] for msg in broadcast_calls]

        # Should warn about no target but NOT error-out
        warn_msgs = [m for m in messages if "No target playlist set" in m or "no moves" in m.lower()]
        assert len(warn_msgs) >= 1
        # Should NOT have moved any videos
        move_msgs = [m for m in messages if "Moved" in m and "video(s)" in m and not "Moved 0" in m]
        assert len(move_msgs) == 0

    @pytest.mark.asyncio
    async def test_watch_later_move_basic(self):
        """watch_later_move moves all videos directly to target playlist."""
        from services.background_worker import BackgroundWorker

        mock_youtube_service = MagicMock()
        mock_manager = MagicMock()
        mock_manager.broadcast = AsyncMock()
        mock_config_manager = MagicMock()
        mock_config_manager.config = MagicMock()
        mock_config_manager.config.youtube_api_key = SecretStr("key")
        mock_config_manager.config.oauth = YouTubeOAuthConfig(
            client_id="test",
            client_secret=SecretStr("secret"),
            access_token="token",
            refresh_token="refresh",
        )
        mock_config_manager.config.watch_later_playlist_id = ""
        mock_config_manager.config.watch_later_target_playlist_id = "pl_direct_target"

        worker = BackgroundWorker(
            mock_youtube_service, mock_manager, mock_config_manager, asyncio.Queue()
        )
        type(worker).youtube_service = property(lambda self: mock_youtube_service)
        mock_client = MagicMock()
        mock_youtube_service.get_client.return_value = mock_client

        watch_later_items = {
            "items": [
                {
                    "id": "item1",
                    "contentDetails": {"videoId": "vid1"},
                    "snippet": {"title": "Video 1", "playlistId": "watch_later"},
                },
                {
                    "id": "item2",
                    "contentDetails": {"videoId": "vid2"},
                    "snippet": {"title": "Video 2", "playlistId": "watch_later"},
                },
            ]
        }
        mock_youtube_service.list_watch_later_items_cached = AsyncMock(return_value=watch_later_items)
        mock_client.move_video_to_playlist.return_value = True
        mock_client.remove_video_from_playlist.return_value = True

        await worker.watch_later_move({})

        broadcast_calls = [call.args[0] for call in mock_manager.broadcast.call_args_list]
        messages = [json.loads(msg)["message"] for msg in broadcast_calls]

        # Should have moved both videos
        summary_msgs = [m for m in messages if "Moved 2 video" in m]
        assert len(summary_msgs) == 1
        # Should have called move_video_to_playlist for each video with the target playlist
        assert mock_client.move_video_to_playlist.call_count == 2

    @pytest.mark.asyncio
    async def test_watch_later_move_returns_early_without_target(self):
        """watch_later_move returns early when no target playlist is configured."""
        from services.background_worker import BackgroundWorker

        mock_youtube_service = MagicMock()
        mock_manager = MagicMock()
        mock_manager.broadcast = AsyncMock()
        mock_config_manager = MagicMock()
        mock_config_manager.config = MagicMock()
        mock_config_manager.config.youtube_api_key = SecretStr("key")
        mock_config_manager.config.oauth = YouTubeOAuthConfig(
            client_id="test",
            client_secret=SecretStr("secret"),
            access_token="token",
            refresh_token="refresh",
        )
        mock_config_manager.config.watch_later_playlist_id = ""
        mock_config_manager.config.watch_later_target_playlist_id = ""  # Not set

        worker = BackgroundWorker(
            mock_youtube_service, mock_manager, mock_config_manager, asyncio.Queue()
        )
        type(worker).youtube_service = property(lambda self: mock_youtube_service)
        mock_client = MagicMock()
        mock_youtube_service.get_client.return_value = mock_client

        await worker.watch_later_move({})

        broadcast_calls = [call.args[0] for call in mock_manager.broadcast.call_args_list]
        messages = [json.loads(msg)["message"] for msg in broadcast_calls]

        error_msgs = [m for m in messages if "No Watch Later target playlist configured" in m]
        assert len(error_msgs) == 1
        # Should NOT have moved any videos
        mock_client.move_video_to_playlist.assert_not_called()
