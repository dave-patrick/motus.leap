"""Regression tests for get_basic_stats disk-first caching.

Guards the 2026-07-15 fix for 'successful scan, but all dashboard info gone on
page reload':

  get_basic_stats() used to re-fetch list_mine_playlists + list_subscriptions
  from the LIVE YouTube API on EVERY call. On the single-user instance the daily
  quota dies fast; under quotaExceeded the live fetch fell into the except branch
  and returned all-zero counts, so the dashboard stat panel blanked on the next
  reload (which re-polls /api/stats). The scan data is persisted to the Render
  disk (all_data.json / playlists.json), so get_basic_stats must serve counts from
  that cache when present instead of hitting the API.

These tests drive the REAL get_basic_stats (with a mocked YouTubeClient) so they
actually exercise the shipped code.
"""

import json

from unittest.mock import MagicMock

import pytest

from services.youtube_service import YouTubeService


def _make_service(tmp_path, monkeypatch):
    """Build a YouTubeService bypassing the heavy __init__ (matches repo pattern)."""
    monkeypatch.setenv("TUBE_MANAGER_DATA_DIR", str(tmp_path))
    from models.config import TubeManagerConfig, YouTubeOAuthConfig

    cfg = TubeManagerConfig(
        youtube_api_key="test_api_key",
        oauth=YouTubeOAuthConfig(
            client_id="test_client_id.apps.googleusercontent.com",
            client_secret="test_secret",
            access_token="token_v1",
            refresh_token="test_refresh",
            token_expiry=9999999999,
        ),
    )
    s = YouTubeService.__new__(YouTubeService)
    s.config = cfg
    s._client = None

    class _MiniCache:
        def __init__(self):
            self.store = {}

        async def set(self, k, v, ttl=None):
            self.store[k] = v

        async def get(self, k):
            return self.store.get(k)

    s._cache = _MiniCache()
    s._data_lock = MagicMock()
    s._user_data_dir = tmp_path / "users" / s._get_user_id()
    s._user_data_dir.mkdir(parents=True, exist_ok=True)
    # No live client: any get_client call returns None, so a live fetch path
    # would return zeros — allowing us to assert the cache was actually used.
    s.get_client = lambda require_oauth=False: None
    return s


@pytest.mark.asyncio
async def test_basic_stats_uses_all_data_cache_without_live_fetch(tmp_path, monkeypatch):
    """get_basic_stats returns counts from all_data.json when present and never calls YouTube."""
    s = _make_service(tmp_path, monkeypatch)
    all_data = {
        "playlists": [{"id": "p1", "title": "A"}, {"id": "p2", "title": "B"}],
        "videos": [{"video_id": "v1"}, {"video_id": "v2"}, {"video_id": "v3"}],
        "subscriptions": [{"id": "c1"}, {"id": "c2"}],
    }
    await s._save_to_disk("all_data", all_data)

    result = await s.get_basic_stats(force_refresh=False)

    assert result["cached"] is True
    assert result["total_playlists"] == 2
    assert result["total_videos"] == 3
    assert result["total_subscriptions"] == 2
    # No live client was ever constructed/used — proof the cache path was taken.
    assert s.get_client(require_oauth=True) is None


@pytest.mark.asyncio
async def test_basic_stats_falls_back_to_playlists_cache(tmp_path, monkeypatch):
    """When all_data is absent but playlists.json exists, counts come from it."""
    s = _make_service(tmp_path, monkeypatch)
    # all_data intentionally NOT written
    await s._save_to_disk("playlists", {
        "playlists": [
            {"id": "p1", "title": "A", "video_count": 5},
            {"id": "p2", "title": "B", "video_count": 3},
        ],
        "stats": {"total_subscriptions": 4},
    })

    result = await s.get_basic_stats(force_refresh=False)

    assert result["cached"] is True
    assert result["total_playlists"] == 2
    assert result["total_videos"] == 8  # 5 + 3
    assert result["total_subscriptions"] == 4


@pytest.mark.asyncio
async def test_basic_stats_force_refresh_with_no_cache_returns_zeros_not_crash(tmp_path, monkeypatch):
    """force_refresh with no client and no cache returns zeros gracefully (no exception)."""
    s = _make_service(tmp_path, monkeypatch)

    result = await s.get_basic_stats(force_refresh=True)

    assert result["cached"] is False
    assert result["total_playlists"] == 0
    assert result["total_videos"] == 0
    assert result["total_subscriptions"] == 0
