"""Tests for fingerprint-based duplicate detection."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from services.duplicate_detector import compute_duplicate_groups


def _vid(vid, title, playlist_id, playlist_title, channel_id="UC123", channel_title="Cool Channel"):
    return {
        "video_id": vid,
        "title": title,
        "channel_id": channel_id,
        "channel_title": channel_title,
        "playlist_id": playlist_id,
        "playlist_title": playlist_title,
        "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
    }


def test_no_duplicates_when_unique():
    videos = [
        _vid("a1", "Song One", "pl1", "Playlist 1"),
        _vid("a2", "Song Two", "pl1", "Playlist 1"),
        _vid("a3", "Song Three", "pl2", "Playlist 2"),
    ]
    groups = compute_duplicate_groups(videos)
    assert groups == []


def test_same_id_in_three_playlists_groups_together():
    """A single video ID living in N playlists collapses into one group."""
    videos = [
        _vid("dup1", "Same Clip", "pl1", "Workout"),
        _vid("dup1", "Same Clip", "pl2", "Favorites"),
        _vid("dup1", "Same Clip", "pl3", "Roadtrip"),
        _vid("dup1", "Same Clip", "pl4", "Temp"),
    ]
    groups = compute_duplicate_groups(videos)
    assert len(groups) == 1
    g = groups[0]
    assert g["canonical_video_id"] == "dup1"
    assert g["copy_count"] == 4
    assert g["exact_duplicate"] is True
    assert {p["id"] for p in g["playlists"]} == {"pl1", "pl2", "pl3", "pl4"}


def test_reupload_different_ids_grouped():
    """Same content re-uploaded under a fresh ID is detected as a duplicate."""
    videos = [
        _vid("orig", "My Song", "pl1", "Playlist 1"),
        _vid("reup", "My Song", "pl2", "Playlist 2"),
    ]
    groups = compute_duplicate_groups(videos)
    assert len(groups) == 1
    g = groups[0]
    assert set(g["variant_ids"]) == {"orig", "reup"}
    assert g["copy_count"] == 2
    assert g["exact_duplicate"] is False  # distinct IDs => re-upload


def test_loose_title_merge_official_vs_remaster():
    """'Song (Official Video)' and 'Song (4K Remaster)' should merge."""
    videos = [
        _vid("v1", "Song (Official Video)", "pl1", "Playlist 1"),
        _vid("v2", "Song (4K Remaster)", "pl2", "Playlist 2"),
    ]
    groups = compute_duplicate_groups(videos)
    assert len(groups) == 1
    assert set(groups[0]["variant_ids"]) == {"v1", "v2"}


def test_different_titles_do_not_merge():
    videos = [
        _vid("v1", "Song of the Sea", "pl1", "Playlist 1"),
        _vid("v2", "Song of the Mountain", "pl2", "Playlist 2"),
    ]
    assert compute_duplicate_groups(videos) == []


def test_different_channels_same_title_not_duplicate():
    videos = [
        _vid("v1", "Cover Song", "pl1", "Playlist 1", channel_id="UCaaa", channel_title="Artist A"),
        _vid("v2", "Cover Song", "pl2", "Playlist 2", channel_id="UCbbb", channel_title="Artist B"),
    ]
    assert compute_duplicate_groups(videos) == []


def test_mixed_exact_and_reupload_same_group():
    """One true dup (same ID) + one re-upload all identified together."""
    videos = [
        _vid("id1", "Lecture 1", "pl1", "Semester A"),
        _vid("id1", "Lecture 1", "pl2", "Semester B"),
        _vid("id1-re", "Lecture 1", "pl3", "Backup"),
    ]
    groups = compute_duplicate_groups(videos)
    assert len(groups) == 1
    g = groups[0]
    assert g["copy_count"] == 3
    # 2 distinct IDs among 3 copies => exact_duplicate is False (re-upload present)
    assert g["exact_duplicate"] is False
    assert "id1" in g["variant_ids"]
    assert "id1-re" in g["variant_ids"]


def test_copies_sorted_largest_first():
    videos = [
        _vid("a", "Clip A", "pl1", "P1"),
        _vid("b", "Clip B", "pl1", "P1"),
        _vid("b", "Clip B", "pl2", "P2"),
        _vid("b", "Clip B", "pl3", "P3"),
    ]
    groups = compute_duplicate_groups(videos)
    assert len(groups) == 1
    assert groups[0]["copy_count"] == 3
