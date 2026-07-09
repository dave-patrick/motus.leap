"""
Regression tests for BackgroundWorker.full_cluster_scan (BUG C2).

BUG C2: the OUTER playlist-pagination loop and the INNER per-playlist video
pagination loop both used the same variable `page_token`. The inner loop
clobbered the outer loop's value, so after page 1 the outer loop re-fetched
page 1 forever (appending duplicate playlists and never advancing past the
first 50). This hangs/never-completes for any account with >50 playlists
(Dave has 61).

The fix renames the OUTER token to `playlist_page_token` and the INNER token
to `video_page_token` so the two loops no longer share state.

These tests exercise the real `full_cluster_scan` method with a MagicMock
YouTube client (no network) that returns TWO playlist pages, asserting the
scan COMPLETES (does not loop forever) and that BOTH pages are collected
(no duplicates / it advanced to page 2).
"""

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest
import pytest_asyncio

# Ensure a temp data dir before importing app modules.
os.environ.setdefault("TUBE_MANAGER_DATA_DIR", tempfile.mkdtemp(prefix="motus_scan_test_"))

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.background_worker import BackgroundWorker
from core.config_manager import ConfigManager


def _make_mock_client(num_playlists_page1, num_playlists_page2):
    """Build a MagicMock YouTube client.

    list_mine_playlists returns TWO pages:
      - page 1: `num_playlists_page1` playlists + nextPageToken="A"
      - page 2: `num_playlists_page2` playlists, no nextPageToken
    list_videos returns ONE page (no nextPageToken) per playlist call.
    """
    client = MagicMock()

    all_first = [
        {"id": f"pl1_{i}", "snippet": {"title": f"Playlist 1-{i}"}}
        for i in range(num_playlists_page1)
    ]
    all_second = [
        {"id": f"pl2_{i}", "snippet": {"title": f"Playlist 2-{i}"}}
        for i in range(num_playlists_page2)
    ]

    def list_mine_playlists(max_results=50, page_token=None):
        if page_token is None:
            resp = {"items": all_first}
            if num_playlists_page2 > 0:
                resp["nextPageToken"] = "A"
            return resp
        # Any non-None token => second (final) page.
        return {"items": all_second}

    client.list_mine_playlists = MagicMock(side_effect=list_mine_playlists)

    def list_videos(pl_id, max_results=50, page_token=None):
        return {
            "items": [
                {
                    "id": f"{pl_id}_vid0",
                    "contentDetails": {"videoId": f"{pl_id}_vid0"},
                    "snippet": {
                        "title": f"Video in {pl_id}",
                        "videoOwnerChannelId": "ownerchannel",
                    },
                }
            ]
        }

    client.list_videos = MagicMock(side_effect=list_videos)
    return client


def _make_worker(num_page1, num_page2):
    client = _make_mock_client(num_page1, num_page2)

    mock_youtube_service = MagicMock()
    mock_youtube_service.get_client = MagicMock(return_value=client)
    # Called at the end of the scan to refresh cache; must be awaitable.
    mock_youtube_service.fetch_all_data = AsyncMock()

    # The BackgroundWorker.youtube_service *property* prefers app.youtube_service
    # over the injected instance, so patch the module global to our mock.
    import app as _app
    _app.youtube_service = mock_youtube_service

    manager = MagicMock()
    manager.broadcast = AsyncMock()

    # Real ConfigManager in a temp dir; .config auto-creates a default config.
    config_manager = ConfigManager(Path(tempfile.mkdtemp(prefix="motus_cfg_")) / "config.json")

    worker = BackgroundWorker(mock_youtube_service, manager, config_manager, asyncio.Queue())
    return worker, manager, client


@pytest.mark.asyncio
async def test_full_cluster_scan_advances_past_page_one_no_infinite_loop():
    """C2 regression: 2-page playlist result must complete and collect both pages.

    Without the fix, the inner video loop clobbers the outer `page_token`,
    the outer loop re-fetches page 1 forever and this test hangs until the
    asyncio.wait_for timeout aborts it.
    """
    num_page1, num_page2 = 3, 4  # total 7 playlists across 2 pages
    worker, manager, client = _make_worker(num_page1, num_page2)

    # Guard: if the bug regresses, the scan would loop forever. Fail fast.
    await asyncio.wait_for(worker.full_cluster_scan({}), timeout=10)

    # Outer loop must have fetched BOTH pages (not just page 1 repeatedly).
    # Page 1 called with token=None; page 2 called with token="A".
    page1_calls = [
        c for c in client.list_mine_playlists.call_args_list
        if c.kwargs.get("page_token") is None
    ]
    page2_calls = [
        c for c in client.list_mine_playlists.call_args_list
        if c.kwargs.get("page_token") == "A"
    ]
    assert len(page1_calls) == 1, "page 1 should be fetched exactly once"
    assert len(page2_calls) == 1, "page 2 should be fetched exactly once (bug re-fetched page 1)"

    # The collected count is only observable via broadcasts. The "[SCAN] Found N
    # playlists" log must report the TOTAL across both pages (no duplicates).
    found_msgs = [
        c.args[0] for c in manager.broadcast.call_args_list
        if isinstance(c.args[0], str) and c.args[0].startswith('{"type": "log", "message": "[SCAN] Found')
    ]
    assert found_msgs, "expected a '[SCAN] Found N playlists' broadcast"
    # Parse N out of the message.
    import json
    last = json.loads(found_msgs[-1])
    msg = last["message"]
    assert f"[SCAN] Found {num_page1 + num_page2} playlists" in msg, (
        f"expected total {num_page1 + num_page2} playlists, got: {msg}"
    )


@pytest.mark.asyncio
async def test_full_cluster_scan_single_page_still_works():
    """Sanity: a single-page account (<=50 playlists) still completes cleanly."""
    num_page1, num_page2 = 5, 0
    worker, manager, client = _make_worker(num_page1, num_page2)

    await asyncio.wait_for(worker.full_cluster_scan({}), timeout=10)

    # Only page 1 should be fetched (no nextPageToken => loop breaks).
    page1_calls = [
        c for c in client.list_mine_playlists.call_args_list
        if c.kwargs.get("page_token") is None
    ]
    page2_calls = [
        c for c in client.list_mine_playlists.call_args_list
        if c.kwargs.get("page_token") == "A"
    ]
    assert len(page1_calls) == 1
    assert len(page2_calls) == 0

    import json
    found_msgs = [
        c.args[0] for c in manager.broadcast.call_args_list
        if isinstance(c.args[0], str) and c.args[0].startswith('{"type": "log", "message": "[SCAN] Found')
    ]
    msg = json.loads(found_msgs[-1])["message"]
    assert f"[SCAN] Found {num_page1} playlists" in msg


@pytest.mark.asyncio
async def test_video_pagination_does_not_clobber_playlist_token():
    """Directly confirm the two pagination loops use distinct variables.

    With the fix, paginating videos (inner loop) must NOT cause an extra
    page-1 playlist fetch. We count playlist page-1 fetches: with the bug,
    the inner video loop resets `page_token` to None each playlist, so after
    the first playlist the outer loop re-fetches page 1 -> 2 playlist
    page-1 fetches (for >1 playlist). With the fix there is exactly 1.
    """
    num_page1, num_page2 = 2, 0  # 2 playlists, single page
    worker, manager, client = _make_worker(num_page1, num_page2)

    await asyncio.wait_for(worker.full_cluster_scan({}), timeout=10)

    page1_calls = [
        c for c in client.list_mine_playlists.call_args_list
        if c.kwargs.get("page_token") is None
    ]
    # Exactly one page-1 fetch proves the inner video loop never reset the
    # outer playlist token back to None.
    assert len(page1_calls) == 1, (
        f"inner video loop clobbered outer token: {len(page1_calls)} page-1 fetches"
    )
