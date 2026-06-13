"""Tests for task schema, validation, and normalization."""

from datetime import datetime, timezone

from tube_manager.schema import schema_v1
from tube_manager.task import normalize, validate


def test_schema_v1_has_required():
    schema = schema_v1()
    assert schema["required"] == ["id", "type", "title", "status"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["type"]["enum"] == ["generic", "research", "code", "home"]
    assert schema["properties"]["status"]["enum"] == ["pending", "running", "completed", "failed"]
    assert schema["properties"]["priority"]["enum"] == ["low", "medium", "high", None]


def test_validate_accepts_minimal_task():
    task = {
        "id": "task-123",
        "type": "generic",
        "title": "Demo task",
        "status": "pending",
    }
    validated = validate(task)
    assert validated["id"] == "task-123"


def test_validate_rejects_empty_id():
    task = {
        "id": "   ",
        "type": "generic",
        "title": "Demo task",
        "status": "pending",
    }
    try:
        validate(task)
    except ValueError as exc:
        assert "missing required fields" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_validate_rejects_invalid_type():
    task = {
        "id": "task-123",
        "type": "unknown",
        "title": "Demo task",
        "status": "pending",
    }
    try:
        validate(task)
    except ValueError as exc:
        assert "invalid type" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_validate_rejects_payload_if_not_object_or_none():
    task = {
        "id": "task-123",
        "type": "generic",
        "title": "Demo task",
        "status": "pending",
        "payload": "not-an-object",
    }
    try:
        validate(task)
    except TypeError:
        pass
    else:
        raise AssertionError("expected TypeError for invalid payload")


def test_normalize_sets_timestamps_and_defaults():
    task = normalize({
        "id": "task-123",
        "type": "code",
        "title": "Review schema.py",
        "status": "pending",
    })
    assert "created_at" in task
    assert "updated_at" in task
    assert task["payload"] is None
    assert task["priority"] is None
    datetime.fromisoformat(task["created_at"])
    datetime.fromisoformat(task["updated_at"])
