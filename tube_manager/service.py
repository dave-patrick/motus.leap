"""Application service layer for Tube Manager."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from tube_manager.config import load as load_config
from tube_manager.handlers import execute
from tube_manager.runner import Task, run
from tube_manager.storage import load_tasks, save_tasks
from tube_manager.task import validate
from tube_manager.task_factory import new_task


class TubeManager:
    def __init__(self, config_path: Path | None = None):  # noqa: F821
        self._config = load_config(config_path)
        storage_cfg = self._config.get("storage", {})
        self._tasks_path = Path(
            storage_cfg.get("path", "./data/tasks.json")
        )
        self._max_concurrent = int(self._config.get("runner", {}).get("max_concurrent", 4))

    @property
    def tasks_path(self) -> Path:
        return self._tasks_path

    def list_tasks(self, status: str | None = None):
        tasks = load_tasks(self._tasks_path)
        if status:
            tasks = [t for t in tasks if t.get("status") == status]
        return tasks

    def get_task(self, task_id: str):
        for task in self.list_tasks():
            if task.get("id") == task_id:
                return task
        return None

    def add_task(
        self,
        title: str,
        task_type: str,
        priority: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        task = new_task(
            title=title,
            task_type=task_type,
            payload=payload,
            priority=priority,
        )
        task = validate(task)
        tasks = self.list_tasks()
        tasks.append(task)
        save_tasks(self._tasks_path, tasks)
        return task

    def update_task(self, task_id: str, **changes) -> dict[str, Any]:
        tasks = self.list_tasks()
        for idx, task in enumerate(tasks):
            if task.get("id") == task_id:
                task.update(changes)
                tasks[idx] = validate(task)
                save_tasks(self._tasks_path, tasks)
                return tasks[idx]
        raise KeyError(f"task not found: {task_id}")

    def remove_task(self, task_id: str) -> None:
        tasks = [t for t in self.list_tasks() if t.get("id") != task_id]
        if len(tasks) == len(self.list_tasks()):
            raise KeyError(f"task not found: {task_id}")
        save_tasks(self._tasks_path, tasks)

    def run_task(self, task_id: str) -> dict[str, Any]:
        task = self.get_task(task_id)
        if not task:
            raise KeyError(f"task not found: {task_id}")

        self.update_task(task_id=task_id, status="running")

        def _work() -> str:
            return execute(task["type"], task.get("payload"))

        results = run([Task(name=task_id, fn=_work)], max_concurrent=1)
        outcome = results.get(task_id, "error: unknown")

        if not outcome.startswith("error:"):
            status = "completed"
        else:
            status = "failed: " + outcome

        return self.update_task(task_id=task_id, status=status)
