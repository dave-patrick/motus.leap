"""Task handlers mapped by task type for Tube Manager."""

from __future__ import annotations

from typing import Any


def run_generic(payload: dict[str, Any] | None) -> str:
    return "generic ok"


def run_research(payload: dict[str, Any] | None) -> str:
    return "research ok"


def run_code(payload: dict[str, Any] | None) -> str:
    return "code ok"


def run_home(payload: dict[str, Any] | None) -> str:
    return "home ok"


from tube_manager.youtube_actions import execute as execute_youtube


HANDLERS = {
    "generic": run_generic,
    "research": run_research,
    "code": run_code,
    "home": run_home,
    "youtube": execute_youtube,
}
