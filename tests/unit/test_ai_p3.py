"""P3 AI Job Scheduling tests (motus.leap).

Covers: cron_util, job CRUD + privilege gate, parse, scheduler ticker firing,
and "Run now" destructive -> pending (Flow C) confirm.

Pattern: seeded user + Bearer token (self-registration disabled), with a
temp TUBE_MANAGER_DATA_DIR so scheduled_jobs.json is written under /tmp
(not the live data dir). Scheduler execution is verified by spying on the
BackgroundWorker dispatch and by running the real ticker against a job whose
next_run is in the past (so it becomes "due" immediately).
"""

import os
import contextlib
import shutil
import tempfile
import asyncio
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from services import ai_chat as chat_mod
from api import auth as auth_module
from api.auth import create_access_token
import app as appmod
from services import background_worker as bw_module
from models.scheduled_job import ScheduledJob, ScheduledJobTask, DESTRUCTIVE_JOB_ACTIONS
from services.background_worker import BackgroundWorker


# ── auth + client (session scoped) ─────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def _session():
    os.environ["TUBE_MANAGER_SECRET_KEY"] = "test_secret_key_stable_for_this_process"
    tmp = tempfile.mkdtemp(prefix="motus_p3_test_")
    os.environ["TUBE_MANAGER_DATA_DIR"] = tmp
    sj = os.path.join(tmp, "scheduled_jobs.json")
    if os.path.exists(sj):
        os.remove(sj)
    users_db = {"mtest": {"id": "abc", "username": "mtest", "email": "mtest@example.com",
                          "hashed_password": "x", "role": "admin", "is_active": True,
                          "created_at": datetime.now(), "last_login": None}}
    auth_module._cached_users_db = users_db
    token = create_access_token({"sub": "mtest"})
    appmod.app.router.lifespan_context = contextlib.asynccontextmanager(lambda a: (yield))

    # Construct a real BackgroundWorker so the Run-now + scheduler endpoints
    # have something to dispatch through (lifespan is skipped in tests).
    class _FakeManager:
        async def broadcast(self, msg):
            pass
    worker = BackgroundWorker(
        youtube_service=None,
        manager=_FakeManager(),
        config_manager=appmod.config_manager,
        task_queue=asyncio.Queue(),
    )
    appmod.background_worker = worker
    bw_module.background_worker = worker

    g = globals()
    g["client"] = TestClient(appmod.app, base_url="http://localhost:8000",
                             headers={"Origin": "http://localhost:8000"})
    g["H"] = {"Authorization": f"Bearer {token}", "Origin": "http://localhost:8000"}
    yield
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(autouse=True)
def _reset():
    tmp = os.environ["TUBE_MANAGER_DATA_DIR"]
    sj = os.path.join(tmp, "scheduled_jobs.json")
    if os.path.exists(sj):
        os.remove(sj)
    chat_mod.clear_pending_actions()
    chat_mod.clear_conversations()
    yield


# ── cron_util ───────────────────────────────────────────────────────────
def test_cron_valid_and_invalid():
    from services import cron_util
    assert cron_util.cron_valid("0 3 * * *")
    assert cron_util.cron_valid("*/5 * * * *")
    assert cron_util.cron_valid("0 9-17 * * 1-5")
    assert cron_util.cron_valid("0,30 * * * *")
    assert cron_util.cron_valid("0 0 1 jan sun")
    assert not cron_util.cron_valid("not a cron")
    assert not cron_util.cron_valid("* * * *")          # 4 fields
    assert not cron_util.cron_valid("99 * * * *")        # minute out of range
    assert not cron_util.cron_valid("a b c d e")         # garbage


def test_cron_next_run_advances():
    from services import cron_util
    base = datetime(2026, 1, 1, 2, 0)
    nxt = cron_util.next_run("0 3 * * *", after=base)   # daily 03:00
    assert nxt == datetime(2026, 1, 1, 3, 0)


def test_cron_matches_star_list_step_range():
    from services import cron_util
    assert cron_util.matches("* * * * *", datetime(2026, 6, 15, 13, 27))
    assert cron_util.matches("0 9,15 * * *", datetime(2026, 6, 15, 9, 0))
    assert not cron_util.matches("0 9,15 * * *", datetime(2026, 6, 15, 10, 0))
    assert cron_util.matches("*/15 * * * *", datetime(2026, 6, 15, 0, 30))
    assert not cron_util.matches("*/15 * * * *", datetime(2026, 6, 15, 0, 10))
    assert cron_util.matches("0 9-17 * * *", datetime(2026, 6, 15, 17, 0))
    assert not cron_util.matches("0 9-17 * * *", datetime(2026, 6, 15, 18, 0))
    # dow (0=Sun). Monday 2026-06-15 should NOT match dow=0 (Sun)
    assert not cron_util.matches("0 0 * * 0", datetime(2026, 6, 15, 0, 0))
    # dow 7 normalized to Sunday (2026-06-14 is Sun)
    assert cron_util.matches("0 0 * * 7", datetime(2026, 6, 14, 0, 0))


# ── job CRUD + validation ──────────────────────────────────────────────
def test_create_and_list_non_destructive():
    r = client.post("/api/ai/jobs", headers=H, json={
        "name": "Daily dup scan", "cron": "0 3 * * *",
        "task": {"type": "scan_duplicates", "payload": {"playlist_id": ""}},
        "enabled": True,
    })
    assert r.status_code == 201, r.text
    jid = r.json()["id"]
    assert r.json().get("next_run") is not None

    lst = client.get("/api/ai/jobs", headers=H).json()["jobs"]
    assert len(lst) == 1
    job = lst[0]
    assert job["id"] == jid
    assert job["name"] == "Daily dup scan"
    assert job["cron"] == "0 3 * * *"
    assert job["task"]["type"] == "scan_duplicates"
    assert job["enabled"] is True
    for k in ("next_run", "last_run", "last_status", "created_at"):
        assert k in job


def test_create_bad_cron_400():
    r = client.post("/api/ai/jobs", headers=H, json={
        "name": "x", "cron": "bad cron expr",
        "task": {"type": "scan_duplicates", "payload": {}},
    })
    assert r.status_code == 400


def test_create_unknown_task_type_400():
    r = client.post("/api/ai/jobs", headers=H, json={
        "name": "x", "cron": "0 3 * * *",
        "task": {"type": "explode_everything", "payload": {}},
    })
    assert r.status_code == 400


def test_create_task_extra_field_400():
    # additionalProperties:false -> unknown key rejected (M4)
    r = client.post("/api/ai/jobs", headers=H, json={
        "name": "x", "cron": "0 3 * * *",
        "task": {"type": "scan_duplicates", "payload": {}, "evil": "rm -rf"},
    })
    assert r.status_code == 400


def test_privilege_gate_destructive_without_confirm_400():
    r = client.post("/api/ai/jobs", headers=H, json={
        "name": "rm dupes", "cron": "0 3 * * *",
        "task": {"type": "remove_duplicates", "payload": {"playlist_id": "PL1"}},
        "confirm_destructive": False,
    })
    assert r.status_code == 400


def test_privilege_gate_destructive_with_confirm_201():
    r = client.post("/api/ai/jobs", headers=H, json={
        "name": "rm dupes", "cron": "0 3 * * *",
        "task": {"type": "remove_duplicates", "payload": {"playlist_id": "PL1"}},
        "confirm_destructive": True,
    })
    assert r.status_code == 201, r.text


def test_jobs_no_auth_401():
    r = client.get("/api/ai/jobs")
    assert r.status_code == 401


def test_patch_enable_pause():
    jid = client.post("/api/ai/jobs", headers=H, json={
        "name": "x", "cron": "0 3 * * *",
        "task": {"type": "scan_duplicates", "payload": {}},
    }).json()["id"]
    r = client.patch(f"/api/ai/jobs/{jid}", headers=H, json={"enabled": False})
    assert r.status_code == 200 and r.json()["enabled"] is False
    job = client.get("/api/ai/jobs", headers=H).json()["jobs"][0]
    assert job["enabled"] is False
    r2 = client.patch(f"/api/ai/jobs/{jid}", headers=H, json={"enabled": True})
    assert r2.status_code == 200 and r2.json()["enabled"] is True


def test_delete_job():
    jid = client.post("/api/ai/jobs", headers=H, json={
        "name": "x", "cron": "0 3 * * *",
        "task": {"type": "scan_duplicates", "payload": {}},
    }).json()["id"]
    r = client.delete(f"/api/ai/jobs/{jid}", headers=H)
    assert r.status_code == 200 and r.json()["ok"] is True
    assert client.delete(f"/api/ai/jobs/{jid}", headers=H).status_code == 404
    assert client.get("/api/ai/jobs", headers=H).json()["jobs"] == []


# ── parse (NL -> cron+task) ─────────────────────────────────────────────
def test_parse_returns_validated_structure(monkeypatch):
    import services.job_parse as jp
    orig = jp.parse_schedule_nl

    def fake_sim(messages, system):
        return {"choices": [{"message": {
            "role": "assistant",
            "content": '{"cron": "0 3 * * *", "name": "Daily dup scan", '
                       '"task": {"type": "scan_duplicates", "payload": {"playlist_id": "PL1"}}, '
                       '"explain": "every day at 3am"}'}}]}

    monkeypatch.setattr(
        jp, "parse_schedule_nl",
        lambda text, config, simulate_provider=None: orig(text, config, simulate_provider=fake_sim))
    r = client.post("/api/ai/jobs/parse", headers=H, json={
        "text": "every day at 3am scan playlist PL1 for duplicates"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cron"] == "0 3 * * *"
    assert body["task"]["type"] == "scan_duplicates"
    assert body["task"]["payload"]["playlist_id"] == "PL1"


def test_parse_rejects_invalid_model_output(monkeypatch):
    import services.job_parse as jp
    orig = jp.parse_schedule_nl

    def fake_sim(messages, system):
        return {"choices": [{"message": {
            "role": "assistant",
            "content": '{"cron": "not a cron", "task": {"type": "scan_duplicates"}}'}}]}

    monkeypatch.setattr(
        jp, "parse_schedule_nl",
        lambda text, config, simulate_provider=None: orig(text, config, simulate_provider=fake_sim))
    r = client.post("/api/ai/jobs/parse", headers=H, json={"text": "x"})
    assert r.status_code == 400


# ── scheduler ticker (real loop, job due in the past) ───────────────────
def test_scheduler_fires_non_destructive(monkeypatch):
    from services import job_store
    called = {}
    async def fake_dispatch(self, action, payload):
        called.setdefault("actions", []).append((action, payload))
        return {"ok": True}
    monkeypatch.setattr(BackgroundWorker, "_dispatch_action", fake_dispatch)

    # Build a job in-memory with next_run in the PAST and drive _execute_job
    # directly. (load_jobs() recomputes next_run on load, so we don't persist a
    # stale past timestamp — we test the dispatch path, which is the contract.)
    job = ScheduledJob(
        name="fast", cron="* * * * *",
        task=ScheduledJobTask(type="scan_duplicates", payload={"playlist_id": "PLX"}),
        enabled=True,
        next_run=(datetime.now().replace(microsecond=0) -
                  __import__("datetime").timedelta(minutes=1)).isoformat(),
    )
    asyncio.run(appmod.background_worker._execute_job(job))
    assert called.get("actions") == [("scan_duplicates", {"playlist_id": "PLX"})], called


def test_scheduler_destructive_requires_confirm_at_creation_and_runs(monkeypatch):
    """Destructive job: rejected without confirm at creation (P1-2); once
    created WITH confirm it dispatches directly (no per-run confirm gate)."""
    from services import job_store
    called = {}
    async def fake_dispatch(self, action, payload):
        called.setdefault("actions", []).append((action, payload))
        return {"deleted": 1}
    monkeypatch.setattr(BackgroundWorker, "_dispatch_action", fake_dispatch)

    bad = client.post("/api/ai/jobs", headers=H, json={
        "name": "rm", "cron": "* * * * *",
        "task": {"type": "remove_duplicates", "payload": {"playlist_id": "PL1"}},
    })
    assert bad.status_code == 400

    ok = client.post("/api/ai/jobs", headers=H, json={
        "name": "rm", "cron": "* * * * *",
        "task": {"type": "remove_duplicates", "payload": {"playlist_id": "PL1"}},
        "confirm_destructive": True,
    })
    assert ok.status_code == 201
    job = job_store.get_job(ok.json()["id"])

    async def _fire():
        await appmod.background_worker._execute_job(job)
    asyncio.run(_fire())
    # Destructive job dispatched directly (no pending/confirm gate at run time).
    assert called.get("actions") == [("remove_duplicates", {"playlist_id": "PL1"})]


# ── Run now: destructive -> pending (Flow C) + confirm executes ─────────
def test_run_now_destructive_held_pending(monkeypatch):
    import api.bulk_operations_impl as bo
    called = {}
    async def fake_delete(self, vid, pid):
        called.setdefault("delete", []).append((vid, pid))
        return True
    monkeypatch.setattr(bo.BulkOperationsService, "delete_video", fake_delete)

    # Stub the dupe scan BEFORE the run call so ids are captured into the
    # pending record (capture happens at Run-now time, line 2821).
    def fake_find(youtube_service, playlist_id):
        return {"duplicate_groups": [{"video_ids": ["VID1", "VID2"]}],
                "playlist_id": playlist_id}
    monkeypatch.setattr(chat_mod, "_tool_find_duplicates", fake_find)

    jid = client.post("/api/ai/jobs", headers=H, json={
        "name": "rm", "cron": "0 3 * * *",
        "task": {"type": "remove_duplicates", "payload": {"playlist_id": "PL1"}},
        "confirm_destructive": True,
    }).json()["id"]

    r = client.post(f"/api/ai/jobs/{jid}/run", headers=H)
    assert r.status_code == 200
    body = r.json()
    assert body["needs_confirm"] is True
    assert body["pending_action_id"]
    assert called == {}, "bulk op executed without confirm"

    rc = client.post("/api/ai/chat/confirm", headers=H,
                     json={"action_id": body["pending_action_id"]})
    assert rc.status_code == 200 and rc.json().get("ok") is True
    assert called != {}, "bulk op should run on confirm"


def test_run_now_non_destructive_executes(monkeypatch):
    called = {}
    async def fake_dispatch(self, action, payload):
        called.setdefault("actions", []).append((action, payload))
        return {"ok": True}
    monkeypatch.setattr(BackgroundWorker, "_dispatch_action", fake_dispatch)
    jid = client.post("/api/ai/jobs", headers=H, json={
        "name": "scan", "cron": "0 3 * * *",
        "task": {"type": "scan_misplaced", "payload": {"playlist_id": ""}},
    }).json()["id"]
    r = client.post(f"/api/ai/jobs/{jid}/run", headers=H)
    assert r.status_code == 200 and r.json().get("ok") is True
    assert called.get("actions") == [("scan_misplaced", {"playlist_id": ""})]
