"""Local storage layer for Tube Manager."""


import json
from pathlib import Path


def load_tasks(path: Path):
    if not path.exists():
        return []
    return json.loads(path.read_text())


def save_tasks(path: Path, tasks):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tasks, indent=2))
