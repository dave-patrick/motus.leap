"""Tube Manager API."""
"""Tube Manager API."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from tube_manager.service import TubeManager

api = FastAPI(title="Tube Manager API")

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "web" / "index.html"
_TEMPLATE_HTML = TEMPLATE_PATH.read_text(encoding="utf-8")

_store: TubeManager | None = None


def get_store() -> TubeManager:
    global _store
    if _store is None:
        _store = TubeManager()
    return _store


class TaskIn(BaseModel):
    title: str
    task_type: str
    priority: Optional[str] = None
    payload: Optional[dict[str, Any]] = None


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    payload: Optional[dict[str, Any]] = None


@api.get("/", response_class=HTMLResponse)
async def index():
    return _TEMPLATE_HTML


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
