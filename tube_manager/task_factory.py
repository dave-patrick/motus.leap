"""Task creation/update for Tube Manager tasks."""
from __future__ import annotations

import uuid
from typing import Any


def new_task(
    title: str,
    task_type: str,
    payload: dict[str, Any] | None = None,
    priority: str | None = None,
) -> dict[str, Any]:
    return {
        "id": _make_id(),
        "type": task_type,
        "title": title,
        "status": "pending",
        "payload": payload,
        "priority": priority,
    }


def mark(task: dict[str, Any], status: str) -> dict[str, Any]:
    task["status"] = status
    return task


def complete(task: dict[str, Any]) -> dict[str, Any]:
    task["status"] = "completed"
    return task


def fail(task: dict[str, Any]) -> dict[str, Any]:
    task["status"] = "failed"
    return task


def _make_id() -> str:
    return uuid.uuid4().hex
