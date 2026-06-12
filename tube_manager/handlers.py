"""Task handlers mapped by task type for Tube Manager."""

from typing import Any


def run_generic(payload: Any) -> str:
    return "generic ok"


def run_research(payload: Any) -> str:
    return "research ok"


def run_code(payload: Any) -> str:
    return "code ok"


def run_home(payload: Any) -> str:
    return "home ok"


HANDLERS = {
    "generic": run_generic,
    "research": run_research,
    "code": run_code,
    "home": run_home,
}


def execute(task_type: str, payload: Any) -> str:
    handler = HANDLERS[task_type]
    return handler(payload)
