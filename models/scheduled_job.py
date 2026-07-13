"""Scheduled job model for AI Job Scheduling (P3).

Import-clean: depends only on pydantic + stdlib so it can be imported by the
model store, the background worker scheduler, and the API layer without
pulling in the (heavier) app/provider machinery.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

# Non-destructive actions that map 1:1 onto the existing BackgroundWorker
# task_queue consumer's action->handler dispatch (background_worker.py:194-207).
JOB_ACTION_TYPES = {
    "full_cluster_scan",
    "diagnose_failures",
    "apply_rules",
    "sync_playlists",
    "scan_duplicates",
    "scan_misplaced",
}

# Destructive actions — allowed ONLY with the creation-time confirm_destructive
# gate (P1-2). Once scheduled, they execute WITHOUT per-run confirm (the
# creation gate is the single informed-consent boundary).
DESTRUCTIVE_JOB_ACTIONS = {"move_video", "delete_video", "remove_duplicates"}

# Full allow-list used to validate a job's task.type (M4).
ALLOWED_JOB_ACTIONS = set(JOB_ACTION_TYPES) | set(DESTRUCTIVE_JOB_ACTIONS)


class ScheduledJobTask(BaseModel):
    """A job's unit of work. ``type`` is from ALLOWED_JOB_ACTIONS; ``payload``
    is the free-form parameter object handed to the handler."""

    type: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class ScheduledJob(BaseModel):
    """A single scheduled job persisted in data/scheduled_jobs.json.

    ``next_run`` is computed from ``cron`` (never user-supplied raw text) and
    recomputed after each fire / on load so the schedule stays correct across
    restarts.
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str
    cron: str
    task: ScheduledJobTask
    enabled: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_run: Optional[str] = None
    last_status: Optional[str] = None
    next_run: Optional[str] = None

    def to_summary(self) -> Dict[str, Any]:
        """Stable client shape (no secrets possible)."""
        return self.model_dump()
