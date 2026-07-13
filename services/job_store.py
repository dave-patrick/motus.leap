"""Atomic persistence for scheduled jobs (P3).

Jobs live in data/scheduled_jobs.json — a NEW file, separate from config.json
(we must keep config.json clean and never risk clobbering the live credential
store). Persistence mirrors the P1 atomic-write lesson: write to a temp file in
the same directory, then os.replace() (POSIX-atomic) over the target.

next_run is recomputed for every enabled job on load so schedules stay correct
across restarts without storing a possibly-stale timestamp.
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import List, Optional

from models.scheduled_job import ScheduledJob
from services import cron_util

log = logging.getLogger(__name__)

# Single-process lock so concurrent create/delete/persist calls don't race
# (the scheduler writer and the API writer can both call save()).
_STORE_LOCK = threading.Lock()


def _jobs_path() -> Path:
    data_dir = Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "scheduled_jobs.json"


def _compute_next(job: ScheduledJob) -> None:
    if not job.enabled or not cron_util.cron_valid(job.cron):
        job.next_run = None
        return
    nxt = cron_util.next_run(job.cron)
    job.next_run = nxt.isoformat() if nxt else None


def load_jobs() -> List[ScheduledJob]:
    """Load all jobs, recomputing next_run for enabled ones. Returns [].

    Never raises on a missing/corrupt file — returns an empty list so the
    scheduler can start cleanly.
    """
    path = _jobs_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        jobs = [ScheduledJob(**j) for j in raw.get("jobs", [])]
        for j in jobs:
            _compute_next(j)
        return jobs
    except Exception as e:
        log.error(f"[JOBS] failed to load scheduled_jobs.json: {e}")
        return []


def save_jobs(jobs: List[ScheduledJob]) -> None:
    """Atomically persist jobs (temp file + os.replace)."""
    path = _jobs_path()
    tmp = path.with_suffix(".json.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps({"jobs": [j.model_dump() for j in jobs]}, indent=2),
                       encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def get_job(job_id: str) -> Optional[ScheduledJob]:
    return next((j for j in load_jobs() if j.id == job_id), None)


def add_job(job: ScheduledJob) -> ScheduledJob:
    """Append a job and persist. Recomputes next_run."""
    with _STORE_LOCK:
        jobs = load_jobs()
        jobs.append(job)
        _compute_next(job)
        save_jobs(jobs)
    return job


def update_job(job: ScheduledJob) -> ScheduledJob:
    """Replace an existing job (matched by id) and persist."""
    with _STORE_LOCK:
        jobs = load_jobs()
        replaced = False
        for i, j in enumerate(jobs):
            if j.id == job.id:
                jobs[i] = job
                replaced = True
                break
        if not replaced:
            jobs.append(job)
        _compute_next(job)
        save_jobs(jobs)
    return job


def remove_job(job_id: str) -> bool:
    """Remove a job by id; return True if it existed."""
    with _STORE_LOCK:
        jobs = load_jobs()
        before = len(jobs)
        jobs = [j for j in jobs if j.id != job_id]
        if len(jobs) == before:
            return False
        save_jobs(jobs)
        return True


def list_enabled_due() -> List[ScheduledJob]:
    """All enabled jobs (schedule ticker filters by next_run itself)."""
    return [j for j in load_jobs() if j.enabled]
