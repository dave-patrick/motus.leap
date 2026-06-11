"""Task handlers mapped by task type for Tube Manager."""

from __future__ import annotations

from typing import Any


def run_generic(payload: dict[str, Any] | None) -> str:
    if payload and payload.get("should_fail"):
        raise ValueError("generic failure")
    return "generic ok"


def run_research(payload: dict[str, Any] | None) -> str:
    if payload and payload.get("should_fail"):
        raise ValueError("research failure")
    return "research ok"


def run_code(payload: dict[str, Any] | None) -> str:
    if payload and payload.get("should_fail"):
        raise ValueError("code failure")
    return "code ok"


def run_home(payload: dict[str, Any] | None) -> str:
    if payload and payload.get("should_fail"):
        raise ValueError("home failure")
    return "home ok"


HANDLERS = {
    "generic": run_generic,
    "research": run_research,
    "code": run_code,
    "home": run_home,
}


def execute(task_type: str, payload: dict[str, Any] | None) -> str:
    handler = HANDLERS[task_type]
    return handler(payload)
