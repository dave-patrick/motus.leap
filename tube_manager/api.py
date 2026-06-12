"""Tube Manager API."""
from __future__ import annotations

from __future__ import annotations
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from tube_manager.service import TubeManager


api = FastAPI(title="Tube Manager API")

_store: TubeManager | None = None


def get_store() -> TubeManager:
    global _store
    if _store is None:
        _store = TubeManager()
    return _store


class TaskIn(BaseModel):
    title: str
    task_type: str
    priority: str | None = None
    payload: dict[str, Any] | None = None


class TaskUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    payload: dict[str, Any] | None = None


@api.get("/tasks")
def list_tasks(status: str | None = None):
    store = get_store()
    items = store.list_tasks(status=status)
    return {"tasks": items}


@api.post("/tasks", status_code=201)
def add_task(body: TaskIn):
    store = get_store()
    task = store.add_task(
        title=body.title,
        task_type=body.task_type,
        priority=body.priority,
        payload=body.payload,
    )
    return task


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
    try:
        task = store.update_task(task_id=task_id, **body.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return task


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
        task = store.run_task(task_id=task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return task


@api.get("/", response_class=HTMLResponse)
async def web_ui(request: Request):
    html = Path("web/index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)
