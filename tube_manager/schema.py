"""Task schema for Tube Manager."""


from __future__ import annotations

from enum import Enum
from typing import Literal


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskType(str, Enum):
    GENERIC = "generic"
    RESEARCH = "research"
    CODE = "code"
    HOME = "home"


TASK_TYPE_LITERAL = Literal["generic", "research", "code", "home"]
TASK_STATUS_LITERAL = Literal["pending", "running", "completed", "failed"]


def schema_v1() -> dict:
    return {
        "type": "object",
        "required": ["id", "type", "title", "status"],
        "properties": {
            "id": {
                "type": "string",
                "minLength": 1,
                "maxLength": 128,
            },
            "type": {
                "type": "string",
                "enum": ["generic", "research", "code", "home"],
            },
            "title": {
                "type": "string",
                "minLength": 1,
                "maxLength": 500,
            },
            "status": {
                "type": "string",
                "enum": ["pending", "running", "completed", "failed"],
            },
            "payload": {
                "type": ["object", "null"],
                "default": None,
            },
            "priority": {
                "type": ["string", "null"],
                "enum": ["low", "medium", "high", None],
                "default": None,
            },
            "created_at": {
                "type": "string",
                "format": "date-time",
            },
            "updated_at": {
                "type": "string",
                "format": "date-time",
            },
        },
        "additionalProperties": False,
    }

