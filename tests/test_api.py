"""Tests for tube_manager.service and FastAPI app."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tube_manager.api import api
from tube_manager.service import TubeManager


@pytest.fixture()
def client(tmp_path: Path):
    tasks_path = tmp_path / "tasks.json"
    tasks_path.write_text("[]")
    api.dependency_overrides.clear()
    store = TubeManager()
    store._tasks_path = tasks_path
    api.dependency_overrides[api.get_store] = lambda: store
    yield TestClient(api)
    api.dependency_overrides.clear()


def test_list_tasks_empty(client: TestClient):
    resp = client.get("/tasks")
    assert resp.status_code == 200
    assert resp.json() == {"tasks": []}


def test_add_and_get_task(client: TestClient):
    created = client.post("/tasks", json={"title": "Demo", "task_type": "generic", "priority": "low"}).json()
    assert "id" in created

    fetched = client.get(f"/tasks/{created['id']}").json()
    assert fetched["title"] == "Demo"
    assert fetched["status"] == "pending"


def test_run_task_transitions_to_completed(client: TestClient):
    created = client.post("/tasks", json={"title": "Run me", "task_type": "generic"}).json()
    task_id = created["id"]

    ran = client.post(f"/tasks/{task_id}/run").json()
    assert ran["status"] == "completed"


def test_delete_task(client: TestClient):
    created = client.post("/tasks", json={"title": "Delete me", "task_type": "generic"}).json()
    task_id = created["id"]

    resp = client.delete(f"/tasks/{task_id}")
    assert resp.status_code == 204

    assert client.get(f"/tasks/{task_id}").status_code == 404
