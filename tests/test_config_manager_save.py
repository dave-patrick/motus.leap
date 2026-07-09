"""Regression: config_manager.save() must never clobber credentials/mappings
that already exist on disk but are absent from the in-memory config being
saved (e.g. when config is read before load() populated it, or a parallel
flow owns those fields). Previously a save could overwrite the real
/app/data/config.json with a blank-default config, wiping YouTube OAuth and
all channel mappings.
"""
import asyncio
from pathlib import Path
import tempfile, json
from core.config_manager import ConfigManager
from models.config import TubeManagerConfig


def test_save_preserves_existing_disk_credentials():
    p = Path(tempfile.mkdtemp()) / "config.json"
    p.write_text(json.dumps({
        "oauth": {"client_id": "cid", "client_secret": "csec",
                  "access_token": "AT", "refresh_token": "RT", "token_expiry": 1},
        "channel_mappings": {"UCx": "PLy"},
        "youtube_api_key": "key",
    }))

    async def main():
        cm = ConfigManager(config_path=p)
        # Simulate a config that lacks credentials (e.g. default returned
        # before load()). Saving it used to wipe the disk file.
        blank = TubeManagerConfig()  # everything empty
        await cm.save(blank)
        disk = json.loads(p.read_text())
        assert disk["oauth"]["access_token"] == "AT", disk
        assert disk["oauth"]["refresh_token"] == "RT", disk
        assert disk["oauth"]["client_id"] == "cid", disk
        assert disk["channel_mappings"] == {"UCx": "PLy"}, disk
        assert disk["youtube_api_key"] == "key", disk

    asyncio.run(main())


def test_save_merges_new_mappings_with_disk_credentials():
    p = Path(tempfile.mkdtemp()) / "config.json"
    p.write_text(json.dumps({
        "oauth": {"client_id": "cid", "access_token": "AT", "refresh_token": "RT",
                  "token_expiry": 1},
    }))

    async def main():
        cm = ConfigManager(config_path=p)
        cfg = await cm.load()  # loaded config has tokens
        cfg.channel_mappings = {"UCnew": "PLnew"}
        await cm.save(cfg)
        disk = json.loads(p.read_text())
        assert disk["channel_mappings"] == {"UCnew": "PLnew"}
        assert disk["oauth"]["access_token"] == "AT"

    asyncio.run(main())
