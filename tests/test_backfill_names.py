"""Backfill + auto-map persist channel titles into channel_metadata (free quota path)."""
import asyncio, json, os
from pathlib import Path
from unittest.mock import MagicMock
from services import youtube_service as ytsvc
import app as appmod


def _fake_map(titles):
    async def _coro():
        return {
            "mapping": {"UCa": "PL1", "UCb": "PL2"},
            "channel_titles": titles,
            "playlists_scanned": 2,
            "videos_scanned": 10,
        }
    return _coro


async def _prep(titles, seed_metadata=None):
    cfgfile = Path("/tmp/_bf_cfg.json")
    cfgfile.write_text(json.dumps({
        "oauth": {"client_id": "c", "access_token": "AT"},
        "channel_mappings": {"UCa": "PL1", "UCb": "PL2"},
        "channel_metadata": seed_metadata or {},
    }))
    os.environ["TUBE_MANAGER_DATA_DIR"] = "/tmp"
    appmod.limiter.enabled = False
    appmod.config_manager.config_path = cfgfile
    appmod.config_manager._config = None
    await appmod.config_manager.load()
    appmod.youtube_service = MagicMock()
    appmod.youtube_service.map_channels_from_playlist_contents = _fake_map(titles)
    return cfgfile


def test_backfill_persists_titles():
    async def main():
        cfgfile = await _prep({"UCa": "Maker Channel", "UCb": "Tech Channel"})
        r = await appmod.backfill_channel_names(MagicMock())
        disk = json.loads(cfgfile.read_text())
        assert disk["channel_metadata"]["UCa"]["title"] == "Maker Channel"
        assert disk["channel_metadata"]["UCb"]["title"] == "Tech Channel"
        assert r["names_added"] == 2
    asyncio.run(main())


def test_backfill_skips_raw_id_and_existing():
    async def main():
        cfgfile = await _prep({"UCa": "Maker Channel", "UCb": "UCb"},
                              seed_metadata={"UCa": {"title": "Existing Name", "thumbnail": "x"}})
        r = await appmod.backfill_channel_names(MagicMock())
        disk = json.loads(cfgfile.read_text())
        # UCa keeps existing name (not overwritten); UCb value 'UCb' ignored
        assert disk["channel_metadata"]["UCa"]["title"] == "Existing Name"
        assert "UCb" not in disk["channel_metadata"]
        assert r["names_added"] == 0
    asyncio.run(main())


def test_automap_preview_does_not_persist_but_apply_does():
    async def main():
        cfgfile = await _prep({"UCa": "Maker Channel"})
        r = await appmod.map_from_playlists(MagicMock(), {"apply": False})
        disk = json.loads(cfgfile.read_text())
        assert "channel_metadata" not in disk or not disk.get("channel_metadata")
        r = await appmod.map_from_playlists(MagicMock(), {"apply": True})
        disk = json.loads(cfgfile.read_text())
        assert disk["channel_metadata"]["UCa"]["title"] == "Maker Channel"
    asyncio.run(main())
