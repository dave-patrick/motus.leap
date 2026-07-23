"""Regression: config_manager.save() must be LOSSLESS for channel_mappings.

A concurrent save (e.g. a background scan that captured the config object
before an auto-map/bulk-import merged new entries) must never clobber
mappings it didn't know about. save() merges the on-disk mappings into the
incoming set rather than trusting the (possibly stale) in-memory object.
"""
import asyncio, tempfile, json
from pathlib import Path
from core.config_manager import ConfigManager
from models.config import TubeManagerConfig


async def _setup(seed_maps: dict):
    tmp = Path(tempfile.mktemp(suffix=".json"))
    tmp.write_text(json.dumps({
        "channel_mappings": seed_maps,
        "oauth": {"access_token": "AT", "client_id": "CID"},
    }))
    mgr = ConfigManager(config_path=tmp)
    await mgr.load()
    return mgr, tmp


def test_lossless_merge_on_stale_scan_save():
    async def run():
        # 284 live mappings on disk.
        seed = {f"UC{i:022d}": "PL_old" for i in range(284)}
        mgr, tmp = await _setup(seed)

        # User action merges 2016 NEW mappings in (auto-map). Disk now 2300.
        cfg = mgr.config
        merged = dict(cfg.channel_mappings)
        merged.update({f"UC{i:022d}": f"PL_{i}" for i in range(284, 2300)})
        cfg.channel_mappings = merged
        await mgr.save(cfg)
        assert len(json.loads(tmp.read_text())["channel_mappings"]) == 2300

        # A background scan captured the config BEFORE the merge. Its object
        # only has the stale 284. Saving it must NOT drop the new 2016.
        stale = TubeManagerConfig(**{
            "channel_mappings": {f"UC{i:022d}": "PL_old" for i in range(284)},
            "oauth": {"access_token": "AT", "client_id": "CID"},
        })
        stale.last_scan_time = "now"
        await mgr.save(stale)

        disk = json.loads(tmp.read_text())
        assert len(disk["channel_mappings"]) == 2300, disk["channel_mappings"]
        assert disk["oauth"]["access_token"] == "AT"  # creds preserved
        tmp.unlink(missing_ok=True)
    asyncio.run(run())
