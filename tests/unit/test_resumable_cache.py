"""Resumable / incremental caching tests for the YouTube sync path.

These guard the fix for 'the 2nd sync dies on quota and the 1st sync's data
seemed to vanish':

  CHANGE 1 -- each playlist is persisted to disk the moment it is fetched.
  CHANGE 2 -- a 2nd (even force_refresh) sync skips unchanged, cached playlists
             (no API call) and re-fetches only changed/missing ones.
  CHANGE 3 -- a quota death mid-loop saves PARTIAL progress to disk rather than
             discarding everything.
  CHANGE 4 -- the disk-cache namespace is stable (client_id), not the rotating
             access-token hash, so a refresh/re-auth does not orphan the cache.

These tests drive the REAL _fetch_all_data_impl (with a mocked YouTubeClient),
so they actually exercise the shipped code rather than a paraphrase.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from models.config import TubeManagerConfig, YouTubeOAuthConfig
from services.youtube_service import YouTubeService, _extract_quota_reason


def _make_service(tmp_path, monkeypatch, access_token="token_v1"):
    monkeypatch.setenv("TUBE_MANAGER_DATA_DIR", str(tmp_path))
    cfg = TubeManagerConfig(
        youtube_api_key="test_api_key",
        oauth=YouTubeOAuthConfig(
            client_id="test_client_id.apps.googleusercontent.com",
            client_secret="test_secret",
            access_token=access_token,
            refresh_token="test_refresh",
            token_expiry=9999999999,
        ),
    )
    s = YouTubeService.__new__(YouTubeService)
    s.config = cfg
    s._client = None
    s._enrich_lock = MagicMock()
    s._data_lock = MagicMock()

    class _MiniCache:
        def __init__(self):
            self.store = {}
        async def set(self, k, v, ttl=None):
            self.store[k] = v
        async def get(self, k):
            return self.store.get(k)
    s._cache = _MiniCache()
    s._user_data_dir = tmp_path / "users" / s._get_user_id()
    s._user_data_dir.mkdir(parents=True, exist_ok=True)
    return s


def _fake_client(playlists=None, subs=None, per_playlist=None):
    """Mocked YouTubeClient.

    NOTE: the real client methods are *synchronous* (the service runs them via
    asyncio.to_thread), so the mocks return plain dicts, not coroutines.
    `per_playlist` maps pl_id -> list of raw video items (or _QUOTA_DEATH).
    """
    client = MagicMock()
    client.list_mine_playlists = MagicMock(return_value={"items": playlists or []})
    client.list_mine_subscriptions = MagicMock(return_value={"items": subs or []})
    client.list_channels_by_ids = MagicMock(return_value={"items": []})

    def _list_videos(pl_id, max_results=50, page_token=None):
        if per_playlist is None:
            return {"items": []}
        if pl_id in per_playlist:
            if per_playlist[pl_id] is _QUOTA_DEATH:
                raise _QuotaError()
            return {"items": per_playlist[pl_id]}
        return {"items": []}

    client.list_videos = MagicMock(side_effect=_list_videos)
    return client


class _QuotaError(Exception):
    pass


_QUOTA_DEATH = object()


def _pl_dict(pl_id, title, count, videos):
    return {
        "id": pl_id,
        "title": title,
        "contentDetails": {"itemCount": count},
        "_videos": videos,
    }


@pytest.mark.asyncio
async def test_playlist_persisted_to_disk_as_fetched(tmp_path, monkeypatch):
    """CHANGE 1: each playlist is written to disk the moment it is fetched."""
    s = _make_service(tmp_path, monkeypatch)
    pl_id = "PL123"
    # Playlists are NORMALIZED (video_count) by the time they reach the video loop.
    pl = {"id": pl_id, "title": "My List", "contentDetails": {"itemCount": 2}}
    videos = [
        {"id": "i1", "snippet": {"title": "V1", "channelTitle": "C"}, "contentDetails": {"videoId": "v1", "duration": "PT1M"}},
        {"id": "i2", "snippet": {"title": "V2", "channelTitle": "C"}, "contentDetails": {"videoId": "v2", "duration": "PT2M"}},
    ]
    client = _fake_client(playlists=[pl], per_playlist={pl_id: videos})
    s.get_client = lambda require_oauth=False: client

    result = await s._fetch_all_data_impl(force_refresh=True)

    assert "error" not in result
    cache_file = s._user_data_dir / f"playlist_videos_{pl_id}.json"
    assert cache_file.exists(), "fetched playlist must be persisted to disk immediately"
    assert len(json.loads(cache_file.read_text())) == 2


@pytest.mark.asyncio
async def test_second_sync_skips_unchanged_playlists(tmp_path, monkeypatch):
    """CHANGE 2: a 2nd force_refresh sync does NOT re-fetch unchanged playlists."""
    s = _make_service(tmp_path, monkeypatch)
    pl_id = "PL456"
    pl = {"id": pl_id, "title": "Cached List", "contentDetails": {"itemCount": 2}}
    videos = [
        {"id": "i1", "snippet": {"title": "V1", "channelTitle": "C"}, "contentDetails": {"videoId": "v1", "duration": "PT1M"}},
        {"id": "i2", "snippet": {"title": "V2", "channelTitle": "C"}, "contentDetails": {"videoId": "v2", "duration": "PT2M"}},
    ]
    client = _fake_client(playlists=[pl], per_playlist={pl_id: videos})
    s.get_client = lambda require_oauth=False: client

    await s._fetch_all_data_impl(force_refresh=True)        # 1st: fetches + caches
    client.list_videos.reset_mock()
    await s._fetch_all_data_impl(force_refresh=True)        # 2nd: should skip

    client.list_videos.assert_not_called(), "unchanged playlist must use disk cache, no API call"


@pytest.mark.asyncio
async def test_changed_playlist_refetches(tmp_path, monkeypatch):
    """CHANGE 2: a playlist whose video_count changed is re-fetched."""
    s = _make_service(tmp_path, monkeypatch)
    pl_id = "PL789"
    # Run 1: playlist reports 2 videos, and the API returns 2.
    pl_v1 = {"id": pl_id, "title": "Grew List", "contentDetails": {"itemCount": 2}}
    videos_v1 = [
        {"id": "i1", "snippet": {"title": "V1", "channelTitle": "C"}, "contentDetails": {"videoId": "v1", "duration": "PT1M"}},
        {"id": "i2", "snippet": {"title": "V2", "channelTitle": "C"}, "contentDetails": {"videoId": "v2", "duration": "PT2M"}},
    ]
    client1 = _fake_client(playlists=[pl_v1], per_playlist={pl_id: videos_v1})
    s.get_client = lambda require_oauth=False: client1
    await s._fetch_all_data_impl(force_refresh=True)

    # Run 2: a NEW client whose playlist now reports 3 videos (added one).
    pl_v2 = {"id": pl_id, "title": "Grew List", "contentDetails": {"itemCount": 3}}
    videos_v2 = videos_v1 + [
        {"id": "i3", "snippet": {"title": "V3"}, "contentDetails": {"videoId": "v3", "duration": "PT3M"}},
    ]
    client2 = _fake_client(playlists=[pl_v2], per_playlist={pl_id: videos_v2})
    s.get_client = lambda require_oauth=False: client2

    result = await s._fetch_all_data_impl(force_refresh=True)

    # The changed playlist must have been re-fetched (3 videos now present).
    assert any(v.get("video_id") == "v3" for v in result.get("videos", [])), \
        "changed playlist must be re-fetched and include the new video"


@pytest.mark.asyncio
async def test_quota_death_preserves_partial_progress(tmp_path, monkeypatch):
    """CHANGE 3: a mid-loop quota death still persists what was fetched."""
    s = _make_service(tmp_path, monkeypatch)
    good_id = "PL_GOOD"
    dead_id = "PL_DEAD"
    good_videos = [{"id": "i1", "snippet": {"title": "V1"}, "contentDetails": {"videoId": "v1", "duration": "PT1M"}}]
    pls = [
        {"id": good_id, "title": "Good", "contentDetails": {"itemCount": 1}},
        {"id": dead_id, "title": "Dead", "contentDetails": {"itemCount": 5}},
    ]
    per_playlist = {good_id: good_videos, dead_id: _QUOTA_DEATH}
    client = _fake_client(playlists=pls, per_playlist=per_playlist)
    s.get_client = lambda require_oauth=False: client

    result = await s._fetch_all_data_impl(force_refresh=True)

    # The good playlist must still be on disk; the all_data cache must carry it.
    good_cache = s._user_data_dir / f"playlist_videos_{good_id}.json"
    assert good_cache.exists()
    all_data = await s._load_from_disk("all_data")
    assert all_data is not None
    assert any(isinstance(v, dict) and v.get("video_id") == "v1" for v in all_data.get("videos", []))


@pytest.mark.asyncio
async def test_user_id_stable_across_token_rotation(tmp_path, monkeypatch):
    """CHANGE 4: namespace must NOT depend on the rotating access_token."""
    s1 = _make_service(tmp_path, monkeypatch, access_token="token_v1")
    id_v1 = s1._get_user_id()
    s2 = _make_service(tmp_path, monkeypatch, access_token="a_completely_different_token_v2")
    id_v2 = s2._get_user_id()
    assert id_v1 == id_v2, "cache namespace must be stable across token refresh/re-auth"
    assert id_v1 != "default"


def test_extract_quota_reason_unaffected():
    """Regression guard: the quota guard helper still works as Sheldon reviewed."""
    class Resp:
        def __init__(self, body):
            self._b = body
        def json(self):
            return self._b
    assert _extract_quota_reason(Resp({"error": {"errors": [{"reason": "quotaExceeded"}]}})) == "quotaExceeded"
    assert _extract_quota_reason(Resp({"error": {"errors": [{"reason": "forbidden"}]}})) == "forbidden"
    assert _extract_quota_reason(Resp({"foo": 1})) is None
