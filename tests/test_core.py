"""Unit tests for Tube Manager."""

from tube_manager.storage import load_tasks, save_tasks
from tube_manager.runner import Task, run


def test_storage_round_trip(tmp_path):
    path = tmp_path / "tasks.json"
    save_tasks(path, [{"id": 1, "title": "hello"}])
    loaded = load_tasks(path)
    assert loaded == [{"id": 1, "title": "hello"}]


def test_runner_completes_task():
    results = run([Task(name="ok", fn=lambda: None)], max_concurrent=1)
    assert results == {"ok": "ok"}


def test_runner_reports_error():
    def boom():  # pragma: no cover - intentional failure
        raise RuntimeError("boom")

    results = run([Task(name="bad", fn=boom)], max_concurrent=1)
    assert results["bad"].startswith("error:")
