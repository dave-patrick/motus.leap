"""P2 AI Management tests — rules CRUD + chat tool-calling.

Pattern: seed user + Bearer token (self-registration disabled), drive
ai_chat.run_chat via its simulate_provider seam, and spy on
bulk_operations_impl so we assert destructive actions are NOT executed
until /confirm.
"""
import os
import contextlib
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from services import ai_chat as chat_mod
from api import auth as auth_module
from api.auth import create_access_token
import app as appmod

# Auth + client are built in a session-scoped fixture (not at import) so this
# module cannot corrupt shared module state when collected alongside other
# test modules (P1, etc.) that also seed the user db / secret key.
@pytest.fixture(scope="session", autouse=True)
def _session():
    os.environ["TUBE_MANAGER_SECRET_KEY"] = "test_secret_key_stable_for_this_process"
    os.environ.setdefault("TUBE_MANAGER_DATA_DIR", "/tmp/_p2_x")
    CFG = "/tmp/_p2_test_config.json"
    if os.path.exists(CFG):
        os.remove(CFG)
    os.environ["CONFIG_PATH"] = CFG
    users_db = {"mtest": {"id": "abc", "username": "mtest", "email": "mtest@example.com",
                          "hashed_password": "x", "role": "admin", "is_active": True,
                          "created_at": datetime.now(), "last_login": None}}
    auth_module._cached_users_db = users_db
    token = create_access_token({"sub": "mtest"})
    appmod.app.router.lifespan_context = contextlib.asynccontextmanager(lambda a: (yield))
    g = globals()
    g["client"] = TestClient(appmod.app, base_url="http://localhost:8000",
                              headers={"Origin": "http://localhost:8000"})
    g["H"] = {"Authorization": f"Bearer {token}", "Origin": "http://localhost:8000"}
    yield


@pytest.fixture(autouse=True)
def _reset():
    chat_mod.clear_pending_actions()
    chat_mod.clear_conversations()
    appmod._chat_buckets.clear()
    yield


def _make_sim(tool_name, tool_args, label="openai/gpt-4o-mini"):
    """simulate_provider: issues `tool_name` on call #1, final reply on #2."""
    state = {"n": 0}
    def _fn(messages, tools):
        state["n"] += 1
        if state["n"] == 1:
            return {
                "choices": [{"message": {
                    "role": "assistant", "content": None,
                    "tool_calls": [{"id": "call_1", "type": "function",
                        "function": {"name": tool_name, "arguments": tool_args}}],
                }}]
            }, label
        return {"choices": [{"message": {"role": "assistant",
            "content": "Queued for your review."}}]}, label
    return _fn


def _sim_remove():
    return _make_sim("remove_duplicates", '{"playlist_id": "PL123"}')


def _sim_unknown():
    return _make_sim("evil_exec", '{"cmd": "rm -rf"}')


def _sim_badjson():
    return _make_sim("remove_duplicates", "not-json")


# ── Rules CRUD ───────────────────────────────────────────────────
def test_list_rules_empty():
    r = client.get("/api/ai/rules", headers=H)
    assert r.status_code == 200 and r.json()["rules"] == []

def test_create_rule():
    r = client.post("/api/ai/rules", headers=H, json={
        "name": "Aviation", "description": "planes", "target_playlist": "PL_A"})
    assert r.status_code == 200 and r.json()["status"] == "created"
    lst = client.get("/api/ai/rules", headers=H).json()["rules"]
    assert len(lst) == 1 and lst[0]["target_playlist"] == "PL_A"

def test_409_duplicate_target():
    b = {"name": "A", "target_playlist": "PL_DUP"}
    assert client.post("/api/ai/rules", headers=H, json=b).status_code == 200
    r = client.post("/api/ai/rules", headers=H, json={"name": "B", "target_playlist": "PL_DUP"})
    assert r.status_code == 409

def test_update_rejects_occupied_target():
    a = client.post("/api/ai/rules", headers=H, json={"name": "A", "target_playlist": "PL_1"}).json()["id"]
    b = client.post("/api/ai/rules", headers=H, json={"name": "B", "target_playlist": "PL_2"}).json()["id"]
    r = client.put(f"/api/ai/rules/{a}", headers=H, json={"target_playlist": "PL_2"})
    assert r.status_code == 409
    r2 = client.put(f"/api/ai/rules/{b}", headers=H, json={"name": "B2"})
    assert r2.status_code == 200 and r2.json()["status"] == "updated"

def test_delete_rule():
    rid = client.post("/api/ai/rules", headers=H, json={"name": "A", "target_playlist": "PL_X"}).json()["id"]
    r = client.delete(f"/api/ai/rules/{rid}", headers=H)
    assert r.status_code == 200 and r.json()["ok"] is True
    assert client.delete(f"/api/ai/rules/{rid}", headers=H).status_code == 404

def test_rules_no_auth_401():
    assert client.get("/api/ai/rules").status_code == 401


# ── Chat: pending, not executed ─────────────────────────────────
def test_chat_destructive_held_pending(monkeypatch):
    import api.bulk_operations_impl as bo
    called = {}
    async def fake_delete(self, vid, pid):
        called.setdefault("delete", []).append((vid, pid))
        return True
    monkeypatch.setattr(bo.BulkOperationsService, "delete_video", fake_delete)
    orig = chat_mod.run_chat
    def wrapped(*a, **k):
        k["simulate_provider"] = _sim_remove()
        return orig(*a, **k)
    monkeypatch.setattr(chat_mod, "run_chat", wrapped)
    r = client.post("/api/ai/chat", headers=H, json={"message": "clean dupes"})
    assert r.status_code == 200
    body = r.json()
    assert body["needs_confirm"] is True
    assert len(body["pending_actions"]) >= 1
    assert body["pending_actions"][0]["action"] == "remove_duplicates"
    assert called == {}, f"bulk op executed without confirm: {called}"


def test_chat_confirm_executes(monkeypatch):
    """After confirm, the bulk op IS invoked (dupe ids captured at request)."""
    import api.bulk_operations_impl as bo
    called = {}
    async def fake_delete(self, vid, pid):
        called.setdefault("delete", []).append((vid, pid))
        return True
    monkeypatch.setattr(bo.BulkOperationsService, "delete_video", fake_delete)
    # Make the dupe scan return known ids so run_chat captures them.
    def fake_find(youtube_service, playlist_id):
        return {"duplicate_groups": [{"video_ids": ["VID1", "VID2"]}],
                "playlist_id": playlist_id}
    monkeypatch.setattr(chat_mod, "_tool_find_duplicates", fake_find)
    orig = chat_mod.run_chat
    def wrapped(*a, **k):
        k["simulate_provider"] = _sim_remove()
        return orig(*a, **k)
    monkeypatch.setattr(chat_mod, "run_chat", wrapped)
    r = client.post("/api/ai/chat", headers=H, json={"message": "clean dupes"})
    assert r.status_code == 200
    aid = r.json()["pending_actions"][0]["id"]
    assert called == {}  # not yet
    rc = client.post("/api/ai/chat/confirm", headers=H, json={"action_id": aid})
    assert rc.status_code == 200 and rc.json().get("ok") is True
    assert called != {}, "bulk op should run on confirm"


def test_chat_unknown_tool_rejected(monkeypatch):
    orig = chat_mod.run_chat
    def wrapped(*a, **k):
        k["simulate_provider"] = _sim_unknown()
        return orig(*a, **k)
    monkeypatch.setattr(chat_mod, "run_chat", wrapped)
    r = client.post("/api/ai/chat", headers=H, json={"message": "x"})
    assert r.status_code == 200
    body = r.json()
    assert body["pending_actions"] == []
    assert body["error"] is not None


def test_chat_bad_json_rejected(monkeypatch):
    orig = chat_mod.run_chat
    def wrapped(*a, **k):
        k["simulate_provider"] = _sim_badjson()
        return orig(*a, **k)
    monkeypatch.setattr(chat_mod, "run_chat", wrapped)
    r = client.post("/api/ai/chat", headers=H, json={"message": "x"})
    assert r.status_code == 200
    assert r.json()["pending_actions"] == []


def test_chat_model_used(monkeypatch):
    orig = chat_mod.run_chat
    def wrapped(*a, **k):
        k["simulate_provider"] = _make_sim("remove_duplicates", '{"playlist_id":"PL1"}', "groq/llama-3.3-70b")
        return orig(*a, **k)
    monkeypatch.setattr(chat_mod, "run_chat", wrapped)
    r = client.post("/api/ai/chat", headers=H, json={"message": "hi"})
    assert r.status_code == 200
    assert r.json()["model_used"] == "groq/llama-3.3-70b"


def test_chat_rate_limit():
    for _ in range(20):
        r = client.post("/api/ai/chat", headers=H, json={"message": "x"})
        if r.status_code == 429:
            break
    r = client.post("/api/ai/chat", headers=H, json={"message": "x"})
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_confirm_unknown_404():
    r = client.post("/api/ai/chat/confirm", headers=H, json={"action_id": "nope"})
    assert r.status_code == 404


def test_chat_target_provider_and_model():
    from models.config import ProviderConnection
    from pydantic import SecretStr
    from services.ai_chat import _iter_enabled_providers
    from core.config_manager import TubeManagerConfig

    provider1 = ProviderConnection(
        id="prov1",
        name="Provider 1",
        type="openai",
        api_key=SecretStr("key1"),
        enabled=True,
        selected_models=["model1a", "model1b"]
    )
    provider2 = ProviderConnection(
        id="prov2",
        name="Provider 2",
        type="openai",
        api_key=SecretStr("key2"),
        enabled=True,
        selected_models=["model2a", "model2b"]
    )

    cfg = TubeManagerConfig()
    cfg.ai_providers = [provider1, provider2]
    cfg.ai_active_provider_id = "prov1"

    # With no target, active provider is first
    ordered = _iter_enabled_providers(cfg)
    assert ordered[0].id == "prov1"

    # With target prov2, target provider is first
    ordered_target = _iter_enabled_providers(cfg, target_provider_id="prov2")
    assert ordered_target[0].id == "prov2"
    assert ordered_target[1].id == "prov1"


def test_chat_no_fallback_when_targeted():
    from services.ai_chat import run_chat
    from core.config_manager import TubeManagerConfig
    from models.config import ProviderConnection
    from pydantic import SecretStr

    provider1 = ProviderConnection(
        id="prov1",
        name="Provider 1",
        type="openai",
        api_key=SecretStr("key1"),
        enabled=True,
        selected_models=["model1"]
    )
    provider2 = ProviderConnection(
        id="prov2",
        name="Provider 2",
        type="openai",
        api_key=SecretStr("key2"),
        enabled=True,
        selected_models=["model2"]
    )

    cfg = TubeManagerConfig()
    cfg.ai_providers = [provider1, provider2]
    cfg.ai_active_provider_id = "prov1"

    from unittest.mock import patch
    with patch("services.ai_chat._chat_completion", side_effect=Exception("Failed connection")):
        res = run_chat("hello", cfg, provider_id="prov2", model="model2")
        assert "Failed connection" in res["error"]
        assert res["fallback"] is False


def test_resolve_chat_endpoint_custom_urls():
    from services.ai_chat import _resolve_chat_endpoint
    from models.config import ProviderConnection

    conn1 = ProviderConnection(
        id="c1", name="C1", type="custom", base_url="https://openrouter.ai/api", enabled=True
    )
    url1 = _resolve_chat_endpoint(conn1, "m1")
    assert url1 == "https://openrouter.ai/api/v1/chat/completions"

    conn2 = ProviderConnection(
        id="c2", name="C2", type="custom", base_url="http://localhost:11434/v1", enabled=True
    )
    url2 = _resolve_chat_endpoint(conn2, "m1")
    assert url2 == "http://localhost:11434/v1/chat/completions"
