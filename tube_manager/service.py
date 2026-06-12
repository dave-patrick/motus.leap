1|"""Application service layer for Tube Manager."""
2|from __future__ import annotations
3|
4|from pathlib import Path
5|from typing import Any
6|
7|from tube_manager.config import load as load_config
8|from tube_manager.handlers import execute
9|from tube_manager.runner import Task, run
10|from tube_manager.storage import load_tasks, save_tasks
11|from tube_manager.task import validate
12|from tube_manager.task_factory import new_task
13|
14|
15|class TubeManager:
16|    def __init__(self, config_path: Optional[Path ] = None):
17|        self._config = load_config(config_path)
18|        storage_cfg = self._config.get("storage", {})
19|        self._tasks_path = Path(
20|            storage_cfg.get("path", "./data/tasks.json")
21|        )
22|        self._max_concurrent = int(self._config.get("runner", {}).get("max_concurrent", 4))
23|
24|    @property
25|    def tasks_path(self) -> Path:
26|        return self._tasks_path
27|
28|    def list_tasks(self, status: Optional[str ] = None):
29|        tasks = load_tasks(self._tasks_path)
30|        if status:
31|            tasks = [t for t in tasks if t.get("status") == status]
32|        return tasks
33|
34|    def get_task(self, task_id: str):
35|        for task in self.list_tasks():
36|            if task.get("id") == task_id:
37|                return task
38|        return None
39|
40|    def add_task(
41|        self,
42|        title: str,
43|        task_type: str,
44|        priority: Optional[str ] = None,
45|        payload: Optional[dict[str, Any] ] = None,
46|    ) -> dict[str, Any]:
47|        task = new_task(
48|            title=title,
49|            task_type=task_type,
50|            payload=payload,
51|            priority=priority,
52|        )
53|        task = validate(task)
54|        tasks = self.list_tasks()
55|        tasks.append(task)
56|        save_tasks(self._tasks_path, tasks)
57|        return task
58|
59|    def update_task(self, task_id: str, **changes) -> dict[str, Any]:
60|        tasks = self.list_tasks()
61|        for idx, task in enumerate(tasks):
62|            if task.get("id") == task_id:
63|                task.update(changes)
64|                tasks[idx] = validate(task)
65|                save_tasks(self._tasks_path, tasks)
66|                return tasks[idx]
67|        raise KeyError(f"task not found: {task_id}")
68|
69|    def remove_task(self, task_id: str) -> None:
70|        tasks = [t for t in self.list_tasks() if t.get("id") != task_id]
71|        if len(tasks) == len(self.list_tasks()):
72|            raise KeyError(f"task not found: {task_id}")
73|        save_tasks(self._tasks_path, tasks)
74|
75|    def run_task(self, task_id: str) -> dict[str, Any]:
76|        task = self.get_task(task_id)
77|        if not task:
78|            raise KeyError(f"task not found: {task_id}")
79|
80|        self.update_task(task_id=task_id, status="running")
81|
82|        def _work() -> str:
83|            return execute(task["type"], task.get("payload"))
84|
85|        results = run([Task(name=task_id, fn=_work)], max_concurrent=1)
86|        outcome = results.get(task_id, "error: unknown")
87|
88|        if not outcome.startswith("error:"):
89|            status = "completed"
90|        else:
91|            status = "failed: " + outcome
92|
93|        return self.update_task(task_id=task_id, status=status)