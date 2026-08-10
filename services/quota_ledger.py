"""Lightweight daily YouTube API quota ledger.

Why this exists
---------------
motus.leap's daily YouTube Data API budget is 10,000 units (1 unit per read,
50 per playlistItems mutation). When that's spent, every subsequent call
returns 403 quotaExceeded and any in-flight batch dies mid-way. This module
tracks units spent *per UTC day* on disk so that:

  * before spending units on a mutation we can ask ``can_spend(n)`` and
  * when we are close to the cap we DEFER (return a structured
    "quota_deferred" result) instead of blindly firing the call and
    failing — which both wastes the little budget left and leaves the
    user with a confusing mid-batch error.

Design notes
------------
* The ledger is process-global but writes to disk so it survives restarts
  (Render reboots reset in-memory state, but the daily cap is per Google
  account, not per process).
* ``DAILY_CAP`` mirrors Google's default; ``SAFE_MARGIN`` leaves headroom
  for the reads a maintenance flow still needs (playlist listings etc.).
* Only MUTATIONS (50-unit playlistItems insert/delete) are metered here;
  reads are cheap (1 unit) and already served from cache wherever possible.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Google's default YouTube Data API daily quota.
DAILY_CAP = 10_000
# Stop authorising new mutations once we've used this much; the remainder is
# reserved for the read calls a flow still has to make to report status.
SAFE_MARGIN = 1_000
SOFT_CAP = DAILY_CAP - SAFE_MARGIN  # 9_000

_LEDGER_FILE = "quota_ledger.json"
_lock = threading.Lock()


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class QuotaLedger:
    """Tracks units spent per UTC day; persisted next to the other disk caches."""

    def __init__(self, data_dir: Optional[Path] = None):
        self._data_dir = Path(data_dir) if data_dir else Path(".")
        self._cache: dict[str, Any] = {}

    # -- persistence ----------------------------------------------------
    def _load(self) -> dict[str, Any]:
        today = _utc_day()
        if self._cache.get("__day") == today and "ledger" in self._cache:
            return self._cache["ledger"]
        try:
            raw = (self._data_dir / _LEDGER_FILE).read_text(encoding="utf-8")
            data = json.loads(raw)
        except Exception:
            data = {}
        # Drop any entry older than today (quota resets at midnight PT/UTC window).
        if data.get("day") != today:
            data = {"day": today, "used": 0}
        self._cache = {"__day": today, "ledger": data}
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self._cache = {"__day": data.get("day", _utc_day()), "ledger": data}
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            (self._data_dir / _LEDGER_FILE).write_text(
                json.dumps(data), encoding="utf-8"
            )
        except Exception:
            # Never let ledger I/O block or crash a mutation.
            pass

    # -- API ------------------------------------------------------------
    def used_today(self) -> int:
        with _lock:
            return int(self._load().get("used", 0))

    def can_spend(self, units: int) -> bool:
        """True if we have headroom under the soft cap for `units` more."""
        with _lock:
            data = self._load()
            return (int(data.get("used", 0)) + units) <= SOFT_CAP

    def spend(self, units: int) -> int:
        """Record `units` as spent; returns the new running total."""
        with _lock:
            data = self._load()
            data["used"] = int(data.get("used", 0)) + units
            self._save(data)
            return int(data["used"])

    def remaining(self) -> int:
        return max(0, SOFT_CAP - self.used_today())

    def deferred_result(self, action: str, needed: int, video_id: Optional[str] = None) -> dict[str, Any]:
        """Structured response used when we refuse to spend (near cap)."""
        return {
            "status": "quota_deferred",
            "action": action,
            "video_id": video_id,
            "needed_units": needed,
            "used_units_today": self.used_today(),
            "soft_cap": SOFT_CAP,
            "error": (
                f"Daily YouTube API quota nearly exhausted "
                f"({self.used_today()}/{SOFT_CAP} units used). Deferring '{action}' "
                f"until the quota resets. Your pending items remain queued."
            ),
        }


# Module-level default instance, lazily pointed at the app's data dir.
_ledger: Optional[QuotaLedger] = None


def configure(data_dir: Path) -> None:
    global _ledger
    _ledger = QuotaLedger(data_dir)


def ledger() -> QuotaLedger:
    global _ledger
    if _ledger is None:
        _ledger = QuotaLedger(Path("."))
    return _ledger
