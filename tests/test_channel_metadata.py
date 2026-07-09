"""Tests for POST /api/channels/metadata (persist resolved channel names)."""
import asyncio, json
from pathlib import Path
from unittest.mock import MagicMock
import app as appmod
from starlette.requests import Request


def _req(body):
    req = Request({"type": "http", "path": "/x", "headers": [], "method": "POST", "query_string": b""})
    return req


async def _call(body, seed_mappings=None):
    appmod.limiter.enabled = False
    cfgfile = Path("/tmp/_cm_cfg.json")
    cfgfile.write_text(json.dumps({"oauth": {"client_id": "c", "access_token": "AT"},
                                   "channel_mappings": seed_mappings or {"UCx": "PL1"}}))
    appmod.config_manager.config_path = cfgfile
    appmod.config_manager._config = None
    await appmod.config_manager.load()
    appmod.youtube_service = MagicMock()
    return await appmod.save_channel_metadata(_req(body), body)


def test_metadata_merges_and_persists():
    async def main():
        r = await _call({"metadata": {"UCLIVE01FAKEID000000000": {"title": "Live A", "thumbnail": "http://x/a.jpg"},
                                      "UCLIVE02FAKEID000000000": {"title": "Live B"}}})
        assert r["status"] == "success"
        assert r["count"] == 2
        disk = json.loads(Path("/tmp/_cm_cfg.json").read_text())
        assert disk["channel_metadata"]["UCLIVE01FAKEID000000000"]["title"] == "Live A"
        assert disk["channel_mappings"] == {"UCx": "PL1"}  # NOT clobbered
    asyncio.run(main())


def test_metadata_rejects_garbage_and_keeps_existing():
    async def main():
        # seed existing metadata
        cfgfile = Path("/tmp/_cm_cfg.json")
        cfgfile.write_text(json.dumps({"oauth": {"client_id": "c", "access_token": "AT"},
                                       "channel_metadata": {"UCKEEP01FAKEID00000000": {"title": "Keep"}},
                                       "channel_mappings": {"UCx": "PL1"}}))
        appmod.limiter.enabled = False
        appmod.config_manager.config_path = cfgfile
        appmod.config_manager._config = None
        await appmod.config_manager.load()
        appmod.youtube_service = MagicMock()

        r = await appmod.save_channel_metadata(_req({"metadata": {
            "not-a-uc-id": {"title": "X"},
            "UCNEW01FAKEID000000000": {},  # no title -> dropped
            "UCNEW02FAKEID000000000": {"title": "New"},
        }}), {"metadata": {"not-a-uc-id": {"title": "X"},
                           "UCNEW01FAKEID000000000": {},
                           "UCNEW02FAKEID000000000": {"title": "New"}}})
        disk = json.loads(cfgfile.read_text())
        md = disk["channel_metadata"]
        assert "not-a-uc-id" not in md
        assert "UCNEW01FAKEID000000000" not in md
        assert md["UCNEW02FAKEID000000000"]["title"] == "New"
        assert md["UCKEEP01FAKEID00000000"]["title"] == "Keep"  # preserved
    asyncio.run(main())
