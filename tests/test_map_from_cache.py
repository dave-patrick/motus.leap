"""map_channels_from_playlist_contents resolves names from DISK-CACHED videos
(zero YouTube API quota), not by forcing a live playlistItems.list fetch.
This is the regression test for the '0 names resolved' bug: when channels.list
is quota-exhausted, the scan must still name channels from the cache.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from services.youtube_service import YouTubeService
import app as appmod


def _make_svc():
    cfg = SimpleNamespace(oauth=SimpleNamespace(access_token="test-token"))
    return YouTubeService(config=cfg)


CACHED_PLAYLISTS = [
    {"id": "PL1", "title": "Tech"},
    {"id": "PL2", "title": "Music"},
]
CACHED_VIDEOS = {
    "PL1": {"videos": [
        {"channel_id": "UCa", "channel_title": "Maker Channel", "title": "v1"},
        {"channel_id": "UCa", "channel_title": "Maker Channel", "title": "v2"},
        {"channel_id": "UCb", "channel_title": "Code Channel", "title": "v3"},
    ]},
    "PL2": {"videos": [
        {"channel_id": "UCb", "channel_title": "Code Channel", "title": "v4"},
        {"channel_id": "UCc", "channel_title": "Song Channel", "title": "v5"},
    ]},
}


def test_resolves_names_from_cache_no_live_api():
    async def main():
        svc = _make_svc()
        svc.get_client = lambda require_oauth=True: object()  # client exists
        svc.get_videos = AsyncMock(side_effect=lambda pid, force_refresh=False: CACHED_VIDEOS[pid])
        svc.list_playlists = AsyncMock(return_value={"playlists": CACHED_PLAYLISTS})
        r = await svc.map_channels_from_playlist_contents()
        assert "error" not in r, r
        assert r["channel_titles"].get("UCa") == "Maker Channel"
        assert r["channel_titles"].get("UCb") == "Code Channel"
        assert r["channel_titles"].get("UCc") == "Song Channel"
        assert r["mapping"]["UCa"] == "PL1"
        assert r["videos_scanned"] == 5
        assert svc.get_videos.await_count == 2
    asyncio.run(main())


CACHED_ALL_DATA = {
    "videos": [
        {"playlist_id": "PL1", "channel_id": "UCa", "channel_title": "Maker Channel"},
        {"playlist_id": "PL1", "channel_id": "UCa", "channel_title": "Maker Channel"},
        {"playlist_id": "PL1", "channel_id": "UCb", "channel_title": "Code Channel"},
        {"playlist_id": "PL2", "channel_id": "UCb", "channel_title": "Code Channel"},
        {"playlist_id": "PL2", "channel_id": "UCc", "channel_title": "Song Channel"},
    ]
}


def test_resolves_names_from_all_data_cache_no_live_api():
    async def main():
        svc = _make_svc()
        svc.get_client = lambda require_oauth=True: object()
        # all_data on disk is the PRIMARY source; get_videos + live never called
        svc._load_from_disk = AsyncMock(return_value=CACHED_ALL_DATA)
        svc.get_videos = AsyncMock(side_effect=AssertionError("should not call get_videos"))
        svc.list_playlists = AsyncMock(return_value={"playlists": CACHED_PLAYLISTS})
        r = await svc.map_channels_from_playlist_contents()
        assert "error" not in r, r
        assert r["channel_titles"].get("UCa") == "Maker Channel"
        assert r["channel_titles"].get("UCb") == "Code Channel"
        assert r["channel_titles"].get("UCc") == "Song Channel"
        assert r["videos_scanned"] == 5
        assert svc.get_videos.await_count == 0
    asyncio.run(main())


def test_resolves_names_from_perplaylist_cache_no_all_data():
    async def main():
        svc = _make_svc()
        svc.get_client = lambda require_oauth=True: object()
        svc._load_from_disk = AsyncMock(return_value=None)  # no all_data
        svc.get_videos = AsyncMock(side_effect=lambda pid, force_refresh=False: CACHED_VIDEOS[pid])
        svc.list_playlists = AsyncMock(return_value={"playlists": CACHED_PLAYLISTS})
        r = await svc.map_channels_from_playlist_contents()
        assert r["channel_titles"].get("UCa") == "Maker Channel"
        assert svc.get_videos.await_count == 2
    asyncio.run(main())


def test_falls_back_to_live_when_cache_empty():
    async def main():
        svc = _make_svc()
        svc.get_client = lambda require_oauth=True: object()
        svc._load_from_disk = AsyncMock(return_value=None)  # no all_data
        svc.get_videos = AsyncMock(return_value={"videos": []})
        svc.list_playlists = AsyncMock(return_value={"playlists": CACHED_PLAYLISTS})
        import services.youtube_service as ys
        orig = ys.YouTubeService._fetch_all_paginated
        async def fake_fetch(self, fetch_fn, *a, **k):
            return [{"snippet": {"videoOwnerChannelId": "UCa", "videoOwnerChannelTitle": "Live Maker"}}]
        ys.YouTubeService._fetch_all_paginated = fake_fetch
        try:
            r = await svc.map_channels_from_playlist_contents()
            assert r["channel_titles"].get("UCa") == "Live Maker"
        finally:
            ys.YouTubeService._fetch_all_paginated = orig
    asyncio.run(main())
