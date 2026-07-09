"""Tests for deriving channel->playlist mappings from playlist contents
(majority vote), plus the preview/apply endpoint semantics.
"""
import asyncio, tempfile, json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import app as appmod
from starlette.requests import Request


def _fake_ys(playlists, items_by_pl):
    client = MagicMock()
    client.list_videos = MagicMock(
        side_effect=lambda pid, page_token=None, max_results=50: {"items": items_by_pl.get(pid, [])}
    )
    ys = MagicMock()
    ys.get_client = MagicMock(return_value=client)
    ys.list_playlists = AsyncMock(return_value={"playlists": playlists})
    # real _fetch_all_paginated behavior: single page from the fake client
    async def fetch(fn, max_results=50, max_items=500):
        return fn(max_results, None)["items"]
    ys._fetch_all_paginated = fetch
    # bind the real method under test
    from services.youtube_service import YouTubeService
    ys.map_channels_from_playlist_contents = YouTubeService.map_channels_from_playlist_contents.__get__(ys)
    return ys


def _item(cid, title="V"):
    return {"snippet": {"videoOwnerChannelId": cid, "videoOwnerChannelTitle": title}}


def test_majority_vote_maps_channel_to_dominant_playlist():
    playlists = [{"id": "PL_music"}, {"id": "PL_tech"}]
    items = {
        "PL_music": [_item("UCa"), _item("UCa"), _item("UCb")],  # UCa x2 here
        "PL_tech": [_item("UCa"), _item("UCc")],                  # UCa x1 here
    }
    ys = _fake_ys(playlists, items)

    async def main():
        res = await ys.map_channels_from_playlist_contents()
        assert res["mapping"]["UCa"] == "PL_music"  # 2 vs 1 -> music
        assert res["mapping"]["UCb"] == "PL_music"
        assert res["mapping"]["UCc"] == "PL_tech"
        assert res["videos_scanned"] == 5
        assert res["playlists_scanned"] == 2
    asyncio.run(main())


def test_endpoint_preview_then_apply(tmp_path):
    appmod.limiter.enabled = False
    cfgfile = tmp_path / "config.json"
    cfgfile.write_text(json.dumps({"oauth": {"client_id": "c", "access_token": "AT",
                       "refresh_token": "RT", "token_expiry": 1}, "channel_mappings": {"UCx": "PL_old"}}))
    appmod.config_manager.config_path = cfgfile
    appmod.config_manager._config = None
    asyncio.run(appmod.config_manager.load())

    playlists = [{"id": "PL_music"}]
    items = {"PL_music": [_item("UCa"), _item("UCx")]}  # UCx already mapped elsewhere
    appmod.youtube_service = _fake_ys(playlists, items)

    async def main():
        req = Request({"type": "http", "path": "/x", "headers": [], "method": "POST", "query_string": b""})
        # preview
        prev = await appmod.map_from_playlists(req, {"apply": False})
        assert prev["would_add"] == 1               # UCa is new
        assert prev["applied"] == 0
        assert len(prev["conflicts"]) == 1          # UCx: PL_old vs PL_music
        assert json.loads(cfgfile.read_text())["channel_mappings"] == {"UCx": "PL_old"}
        # apply (no overwrite -> keep existing UCx, add UCa)
        ap = await appmod.map_from_playlists(req, {"apply": True})
        assert ap["applied"] == 1
        disk = json.loads(cfgfile.read_text())["channel_mappings"]
        assert disk == {"UCx": "PL_old", "UCa": "PL_music"}
    asyncio.run(main())
