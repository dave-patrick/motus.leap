"""Task validation and normalization."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from tube_manager.schema import TaskStatus, TaskType, schema_v1


REQUIRED_FIELDS = ("id", "type", "title", "status")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


_VALID_TYPES = {e.value for e in TaskType}
_VALID_STATUSES = {e.value for e in TaskStatus}
_VALID_PRIORITIES = {"low", "medium", "high", None}


def validate(task: dict[str, Any]) -> dict[str, Any]:
    schema = schema_v1()

    required = schema["required"]
    missing = [field for field in required if field not in task or task[field] in (None, "")]
    if missing:
        raise ValueError(f"missing required fields: {missing}")

    if task["type"] not in _VALID_TYPES:
        raise ValueError(f"invalid type: {task['type']!r}")

    if task["status"] not in _VALID_STATUSES:
        raise ValueError(f"invalid status: {task['status']!r}")

    priority = task.get("priority")
    if priority is not None and priority not in _VALID_PRIORITIES:
        raise ValueError(f"invalid priority: {priority!r}")

    if "payload" in task and task["payload"] is not None and not isinstance(task["payload"], dict):
        raise TypeError("task.payload must be an object or null")

    return task


def normalize(task: dict[str, Any]) -> dict[str, Any]:
    task.setdefault("payload", None)
    task.setdefault("priority", None)
    task.setdefault("created_at", _now())
    task["updated_at"] = _now()
    return validate(task)
