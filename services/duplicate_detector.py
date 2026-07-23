"""Fingerprint-based duplicate detection for motus.leap.

The legacy detector only flagged a single video *ID* appearing in more than
one playlist. That misses the far more common real-world case: a video that
has been re-uploaded (fresh ID) or saved under a slightly different title, and
which therefore lives in N playlists under different IDs.

This module fingerprints each video on ``(channel, normalized title)`` so that
every copy — same ID *or* re-upload — collapses into a single group regardless
of how many playlists it spans. Each group reports a canonical "keep" copy and
every playlist a copy was found in, so the UI can resolve them in one action.
"""

import re
from typing import Any, Dict, List, Optional

# Tokens that commonly differ between a video and its re-upload but do not
# change the underlying content. Stripped when building the *loose* title used
# for fuzzy grouping. Kept conservative to avoid false positives.
_LOOSE_STRIP = re.compile(
    r"\b(official|music video|lyric video|lyrics|video|audio|full|hd|hq|4k|"
    r"remaster(?:ed)?|remix|extended|version|original|full album|visualizer|"
    r"live|acoustic|cover|official video|episode \d+|s\d+e\d+)\b",
    re.IGNORECASE,
)


def _norm_title(title: Optional[str]) -> str:
    """Aggressive normalization for the *exact* fingerprint.

    Lower-cased, punctuation/space collapsed, trimmed. Two titles that are
    byte-for-byte identical after this pass share a fingerprint.
    """
    if not title:
        return ""
    t = title.lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _loose_title(title: Optional[str]) -> str:
    """Looser normalization for fuzzy grouping of re-uploads.

    Strips boilerplate tokens (Official Video, 4K, Remaster, Episode 3, …)
    and parenthetical qualifiers so e.g. ``Song (Official Video)`` and
    ``Song (4K Remaster)`` collapse together, while genuinely different songs
    (different core words) do not.
    """
    t = _norm_title(title)
    if not t:
        return t
    # Drop content inside parentheses/brackets first.
    t = re.sub(r"[\(\[][^\)\]]*[\)\]]", " ", t)
    t = _LOOSE_STRIP.sub(" ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _channel_key(channel_id: Optional[str], channel_title: Optional[str]) -> str:
    """Stable channel identity — prefer the ID, fall back to normalized title.

    A channel ID is globally unique; the title is only used when an ID is
    unavailable (e.g. very old playlist items) so we still group sensibly.
    """
    if channel_id:
        return f"id:{channel_id}"
    title = _norm_title(channel_title)
    return f"title:{title}" if title else "unknown"


def compute_duplicate_groups(
    videos: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Group videos into duplicate clusters via content fingerprinting.

    Args:
        videos: Each dict must carry at least ``video_id``, ``title``,
            ``playlist_id``, ``playlist_title`` and optionally ``channel_id``,
            ``channel_title``, ``thumbnail``, ``duration_seconds``.

    Returns:
        A list of duplicate-group dicts, one per fingerprint that is shared by
        two or more copies. Each entry:

            {
              "fingerprint": str,
              "video_title": str,            # display title (canonical copy)
              "channel_title": str,
              "canonical_video_id": str,     # keep this copy
              "variant_ids": [str, ...],     # all distinct video IDs seen
              "playlists": [{"id":..., "title":...}, ...],  # every pl a copy lives in
              "copies": [ {full per-copy record}, ... ],
              "copy_count": int,
              "exact_duplicate": bool,       # all same ID (true dup) vs re-upload
            }
    """
    # Exact fingerprint -> list of copies (each copy is the source video dict).
    exact: Dict[str, List[Dict[str, Any]]] = {}
    # Loose fingerprint -> set of exact fingerprints (for re-upload fuzzy merge).
    loose: Dict[str, set] = {}

    for v in videos:
        vid = v.get("video_id") or v.get("id") or ""
        title = v.get("title") or v.get("video_title") or ""
        ch_id = v.get("channel_id") or v.get("videoOwnerChannelId")
        ch_title = v.get("channel_title") or v.get("channelTitle") or ""
        pl_id = v.get("playlist_id") or ""
        pl_title = v.get("playlist_title") or v.get("playlist_title") or ""

        fp_exact = f"{_channel_key(ch_id, ch_title)}||{_norm_title(title)}"
        fp_loose = f"{_channel_key(ch_id, ch_title)}||{_loose_title(title)}"

        copy = {
            "video_id": vid,
            "title": title,
            "channel_id": ch_id or "",
            "channel_title": ch_title,
            "playlist_id": pl_id,
            "playlist_title": pl_title,
            "thumbnail": v.get("thumbnail") or "",
            "duration_seconds": v.get("duration_seconds"),
            "playlist_item_id": v.get("playlist_item_id", ""),
        }
        exact.setdefault(fp_exact, []).append(copy)
        loose.setdefault(fp_loose, set()).add(fp_exact)

    # Merge exact-fingerprint groups that share a loose fingerprint, so e.g.
    # "Song (Official Video)" and "Song (4K Remaster)" become one cluster.
    merged: Dict[str, List[Dict[str, Any]]] = {}
    seen_loose: Dict[str, str] = {}
    for fp_loose, exact_fps in loose.items():
        # Pick a stable primary key (the first seen) to merge the rest under.
        primary = seen_loose.get(fp_loose)
        if primary is None:
            primary = next(iter(exact_fps))
            seen_loose[fp_loose] = primary
        for fp_exact in exact_fps:
            merged.setdefault(primary, []).extend(exact.get(fp_exact, []))

    groups: List[Dict[str, Any]] = []
    for _primary_fp, copies in merged.items():
        if len(copies) < 2:
            continue

        variant_ids = []
        seen_ids: set = set()
        for c in copies:
            vid = c["video_id"]
            if vid and vid not in seen_ids:
                seen_ids.add(vid)
                variant_ids.append(vid)

        # Playlists: every distinct playlist a copy lives in.
        playlists = []
        seen_pls: set = set()
        for c in copies:
            pl_id = c["playlist_id"]
            if pl_id and pl_id not in seen_pls:
                seen_pls.add(pl_id)
                playlists.append({
                    "id": pl_id,
                    "title": c["playlist_title"],
                    "video_id": c["video_id"],
                    "playlist_item_id": c.get("playlist_item_id", "")
                })

        # Canonical = the longest title (most complete metadata), else first.
        canonical = max(copies, key=lambda c: (len(c["title"] or ""), c["video_id"]))
        channel_title = canonical["channel_title"]
        exact_dup = len(variant_ids) == 1  # all copies share one ID => pure dup, no re-upload

        groups.append({
            "fingerprint": _primary_fp,
            "video_title": canonical["title"] or "Unknown",
            "channel_title": channel_title,
            "canonical_video_id": canonical["video_id"],
            "variant_ids": variant_ids,
            "playlists": playlists,
            "copies": copies,
            "copy_count": len(copies),
            "exact_duplicate": exact_dup,
        })

    # Largest clusters first — most likely to be the user's pain points.
    groups.sort(key=lambda g: g["copy_count"], reverse=True)
    return groups
