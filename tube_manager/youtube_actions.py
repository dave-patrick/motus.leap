"""Playlist handler map for YouTube actions."""

from __future__ import annotations

from typing import Any


def handle_sync(payload: dict[str, Any] | None) -> dict[str, Any]:
    return {"action": "sync", "detail": "stub"}


def handle_playlist(payload: dict[str, Any] | None) -> dict[str, Any]:
    return {"action": "playlist", "detail": "stub"}


def handle_watchlater(payload: dict[str, Any] | None) -> dict[str, Any]:
    return {"action": "watchlater", "detail": "stub"}


HANDLERS = {
    "sync": handle_sync,
    "playlist": handle_playlist,
    "watchlater": handle_watchlater,
}


def execute(action: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    handler = HANDLERS[action]
    return handler(payload)
