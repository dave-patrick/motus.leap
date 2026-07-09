"""Tests for POST /api/channels/titles (batch channel ID -> name/avatar)."""
import asyncio, json
from pathlib import Path
from unittest.mock import MagicMock
import app as appmod
from starlette.requests import Request


def _fake_client_with_channels(channel_map):
    """channel_map: {channel_id: {'title':..,'thumbnail':..}}"""
    items = []
    for cid, info in channel_map.items():
        items.append({
            "id": cid,
            "snippet": {
                "title": info["title"],
                "thumbnails": {"default": {"url": info.get("thumbnail", "")}},
            },
        })

    def channels_list(**kwargs):
        ids = (kwargs.get("id") or "").split(",")
        return MagicMock(execute=MagicMock(
            return_value={"items": [it for it in items if it["id"] in ids]}
        ))

    google_client = MagicMock()
    google_client.channels.return_value.list.side_effect = channels_list

    yt_client = MagicMock()
    yt_client._get_client = MagicMock(return_value=google_client)
    return yt_client


def _req(body):
    req = Request({"type": "http", "path": "/x", "headers": [], "method": "POST", "query_string": b""})
    req._json_body = body
    return req


async def _call(body):
    appmod.limiter.enabled = False
    cfgfile = Path("/tmp/_ct_cfg.json")
    cfgfile.write_text(json.dumps({"oauth": {"client_id": "c", "access_token": "AT"}, "channel_mappings": {}}))
    appmod.config_manager.config_path = cfgfile
    appmod.config_manager._config = None
    await appmod.config_manager.load()
    appmod.youtube_service = MagicMock()
    appmod.youtube_service.get_client = MagicMock(return_value=_fake_client_with_channels({
        "UC_aLPHACHANNELOFAKEID01": {"title": "Alpha Channel", "thumbnail": "http://x/a.jpg"},
        "UC_bETACHANNELOFAKEID0002": {"title": "Beta Channel"},
    }))
    return await appmod.api_channel_titles(_req(body), body)


def test_resolves_known_ids_and_ignores_unknown():
    async def main():
        r = await _call({"channel_ids": ["UC_aLPHACHANNELOFAKEID01", "UC_bETACHANNELOFAKEID0002",
                                        "UC_unknownFAKEID0000000003", "not-a-uc-id", "",
                                        "UC_aLPHACHANNELOFAKEID01"]})
        titles = r["titles"]
        assert titles["UC_aLPHACHANNELOFAKEID01"]["title"] == "Alpha Channel"
        assert titles["UC_aLPHACHANNELOFAKEID01"]["thumbnail"] == "http://x/a.jpg"
        assert titles["UC_bETACHANNELOFAKEID0002"]["title"] == "Beta Channel"
        # unknown id has no entry; invalid ids dropped
        assert "UC_unknownFAKEID0000000003" not in titles
        assert len(titles) == 2  # deduped
    asyncio.run(main())


def test_empty_input_returns_empty():
    async def main():
        r = await _call({"channel_ids": []})
        assert r["titles"] == {}
    asyncio.run(main())
