"""Todo-style runner for local tasks."""


from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class Task:
    name: str
    fn: Callable[[], None]


def run(tasks: Iterable[Task], max_concurrent: int = 4):
    items = list(tasks)
    results = {}
    with ThreadPoolExecutor(max_workers=max_concurrent) as pool:
        futures = {pool.submit(task.fn): task.name for task in items}
        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result()
                results[name] = "ok"
            except Exception as exc:  # noqa: BLE001
                results[name] = f"error: {exc}"
    return results
