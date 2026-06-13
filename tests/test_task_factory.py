"""Tests for task factory."""
import pytest

from tube_manager.task_factory import complete, fail, mark, new_task


@pytest.mark.parametrize(
    "task_type,priority",
    [
        ("generic", "low"),
        ("code", "high"),
        ("home", None),
    ],
)
def test_new_task_sets_fields(task_type, priority):
    task = new_task(title="Demo", task_type=task_type, priority=priority)
    assert task["id"]
    assert task["type"] == task_type
    assert task["title"] == "Demo"
    assert task["priority"] == priority
    assert task["status"] == "pending"


def test_new_task_generates_unique_ids():
    ids = {new_task(title="T", task_type="generic")["id"] for _ in range(20)}
    assert len(ids) == 20


def test_mark_changes_status():
    task = new_task(title="Demo", task_type="generic")
    mark(task, "running")
    assert task["status"] == "running"


def test_complete_and_fail_helpers():
    t1 = complete(new_task(title="T1", task_type="code"))
    t2 = fail(new_task(title="T2", task_type="home"))
    assert t1["status"] == "completed"
    assert t2["status"] == "failed"
