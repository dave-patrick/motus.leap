"""Tube Manager API."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from tube_manager.service import TubeManager
from tube_manager.google import YouTubeClient

api = FastAPI(title="Tube Manager API")

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "web" / "index.html"
_TEMPLATE_HTML = TEMPLATE_PATH.read_text(encoding="utf-8")

WEB_DIR = str(Path(__file__).resolve().parent.parent / "web")
api.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

_store: Optional[TubeManager] = None
_youtube: Optional[YouTubeClient] = None


def get_store() -> TubeManager:
    global _store
    if _store is None:
        _store = TubeManager()
    return _store


def get_youtube() -> YouTubeClient:
    global _youtube
    if _youtube is None:
        _youtube = YouTubeClient()
    return _youtube


class TaskIn(BaseModel):
    title: str
    task_type: str
    priority: Optional[str] = None
    payload: Optional[dict[str, Any]] = None


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    payload: Optional[dict[str, Any]] = None


class RunActionIn(BaseModel):
    action: str
    payload: Optional[dict[str, Any]] = None


@api.get("/")
async def root():
    return {"status": "ok"}

@api.get("/health")
async def health():
    return {"status": "ok"}


# Tasks (generic workflow)
@api.get("/tasks")
def list_tasks(status: Optional[str] = None):
    store = get_store()
    return {"tasks": store.list_tasks(status=status)}


@api.post("/tasks", status_code=201)
def add_task(body: TaskIn):
    store = get_store()
    return store.add_task(
        title=body.title,
        task_type=body.task_type,
        priority=body.priority,
        payload=body.payload,
    )


@api.get("/tasks/{task_id}")
def get_task(task_id: str):
    store = get_store()
    task = store.get_task(task_id=task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@api.post("/tasks/{task_id}")
def update_task(task_id: str, body: TaskUpdate):
    store = get_store()
    changes = {k: v for k, v in body.model_dump(exclude_none=True).items() if v is not None}
    try:
        return store.update_task(task_id=task_id, **changes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@api.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: str):
    store = get_store()
    try:
        store.remove_task(task_id=task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return None


@api.post("/tasks/{task_id}/run")
async def run_task(task_id: str):
    store = get_store()
    try:
        return store.run_task(task_id=task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# YouTube feature routes
@api.get("/youtube/playlists")
def yt_playlists(mine: bool = True, max_results: int = 25):
    yt = get_youtube()
    try:
        if mine:
            resp = yt.list_mine_playlists(max_results=max_results)
            return {"items": resp.get("items", [])}
        return {"items": []}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@api.get("/youtube/playlists/{playlist_id}/items")
def yt_playlist_items(playlist_id: str, max_results: int = 50, page_token: Optional[str] = None):
    yt = get_youtube()
    try:
        data = yt.list_videos(playlist_id=playlist_id, max_results=max_results, page_token=page_token)
        return {
            "items": data.get("items", []),
            "next_page_token": data.get("nextPageToken"),
            "prev_page_token": data.get("prevPageToken"),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@api.get("/youtube/channels")
def yt_channels(mine: bool = True):
    yt = get_youtube()
    try:
        if mine:
            resp = yt.list_mine_channels()
            return {"items": resp.get("items", [])}
        return {"items": []}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@api.post("/youtube/actions/add")
def yt_add(body: dict[str, Any]):
    yt = get_youtube()
    try:
        return yt.add_to_playlist(
            playlist_id=str(body.get("playlist_id", "")),
            video_id=str(body.get("video_id", "")),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@api.post("/youtube/actions/remove")
def yt_remove(body: dict[str, Any]):
    yt = get_youtube()
    try:
        return yt.remove_from_playlist(
            playlist_item_id=str(body.get("playlist_item_id", "")),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@api.post("/youtube/actions/create-playlist")
def yt_create(body: dict[str, Any]):
    yt = get_youtube()
    try:
        return yt.create_playlist(
            title=str(body.get("title", "")),
            description=str(body.get("description", "")),
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@api.post("/youtube/run")
def yt_run_action(body: RunActionIn):
    yt = get_youtube()
    try:
        if body.action == "scan":
            return {"status": "queued", "action": body.action}
        if body.action == "sort":
            return {"status": "queued", "action": body.action}
        if body.action == "apply":
            return {"status": "queued", "action": body.action}
        if body.action == "force":
            return {"status": "queued", "action": body.action}
        if body.action == "regenerate":
            return {"status": "queued", "action": body.action}
        raise ValueError("unknown action")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
