"""Unit tests for P1 AI Management endpoints (motus.leap).

Covers the multi-provider config + dynamic model discovery contract from
DESIGN_SPEC §7 / Gwen §A.2 + §B. Uses the seeded-user + Bearer-token pattern
from motus-leap-ops/references/authed_endpoint_test_pattern.md (self-registration
is disabled, so we mint a JWT with the app's own create_access_token and stash a
user in the auth cache). Discovery probes are mocked at the httpx.Client layer.

Run with:  python -m pytest tests/unit/ -q
"""

import os
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

# Stable secret key MUST be set before importing app / api.auth so that
# create_access_token and get_current_user share the same key (see pattern doc).
os.environ.setdefault("TUBE_MANAGER_DATA_DIR", tempfile.mkdtemp(prefix="motus_p1_test_"))
os.environ["TUBE_MANAGER_SECRET_KEY"] = os.environ.get(
    "TUBE_MANAGER_SECRET_KEY", "test_secret_key_stable_for_this_process"
)

from contextlib import asynccontextmanager  # noqa: E402

import app as app_module  # noqa: E402
from api import auth as auth_module  # noqa: E402
from api.auth import create_access_token  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pydantic import SecretStr  # noqa: E402
import httpx  # noqa: E402

from models.config import (  # noqa: E402
    TubeManagerConfig,
    ProviderConnection,
    PROVIDER_TYPES,
)
from core.config_manager import ConfigManager  # noqa: E402

# Skip real startup (config load / bg tasks).
app_module.app.router.lifespan_context = asynccontextmanager(lambda a: (yield))

# Seed a user directly into the auth cache and mint a JWT (self-registration is
# disabled in this deployment).
_SEED_USER = {
    "id": uuid.uuid4().hex,
    "username": "p1test",
    "email": "p1test@example.com",
    "hashed_password": "x",
    "role": "admin",
    "is_active": True,
    "created_at": datetime.now(timezone.utc),
    "last_login": None,
}
auth_module._cached_users_db = {"p1test": _SEED_USER}
_TOKEN = create_access_token({"sub": "p1test"})
AUTH = {"Authorization": f"Bearer {_TOKEN}"}

CLIENT = TestClient(
    app_module.app,
    base_url="http://localhost:8000",
    headers={"Origin": "http://localhost:8000"},  # verify_origin needs an Origin
)


@pytest.fixture(autouse=True)
def _reset_providers():
    """Start each test from a clean in-memory config (no providers)."""
    app_module.config_manager._config = TubeManagerConfig()
    yield
    app_module.config_manager._config = TubeManagerConfig()


def _make_httpx_client(status=200, payload=None, side_effect=None):
    """Build a fake httpx.Client usable as `with httpx.Client(...) as c:`."""
    resp = Mock()
    resp.status_code = status
    resp.headers = {}
    resp.text = ""
    if payload is not None:
        resp.json = Mock(return_value=payload)
    else:
        resp.json = Mock(side_effect=ValueError("no json"))
    client = Mock()
    client.get = Mock(return_value=resp)
    ctx = Mock()
    ctx.__enter__ = Mock(return_value=client)
    ctx.__exit__ = Mock(return_value=False)
    fake = Mock(return_value=ctx)
    return fake, resp


# ─── 401 on missing auth ────────────────────────────────────────────

@pytest.mark.unit
class TestAuthRequired:
    def test_list_providers_requires_auth(self):
        resp = CLIENT.get("/api/ai/providers")  # no AUTH header
        assert resp.status_code in (401, 403), resp.text

    def test_connect_provider_requires_auth(self):
        resp = CLIENT.post("/api/ai/providers", json={
            "name": "x", "type": "openai", "api_key": "k"})
        assert resp.status_code in (401, 403), resp.text

    def test_discover_requires_auth(self):
        # unknown id; auth must fail before 404
        resp = CLIENT.get("/api/ai/providers/nope/models")
        assert resp.status_code in (401, 403), resp.text


# ─── list providers (keys redacted) ─────────────────────────────────

@pytest.mark.unit
class TestListProviders:
    def test_empty_list(self):
        resp = CLIENT.get("/api/ai/providers", headers=AUTH)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "providers" in data
        assert data["providers"] == []

    def test_keys_redacted_in_list(self):
        # Connect a provider, then assert the key is never returned.
        conn = CLIENT.post("/api/ai/providers", headers=AUTH, json={
            "name": "My OpenAI", "type": "openai", "api_key": "sk-secret-123"})
        assert conn.status_code == 200, conn.text
        pid = conn.json()["id"]
        listing = CLIENT.get("/api/ai/providers", headers=AUTH)
        assert listing.status_code == 200, listing.text
        body = listing.json()
        assert len(body["providers"]) == 1
        p = body["providers"][0]
        assert p["id"] == pid
        assert "api_key" not in p
        assert p["type"] == "openai"
        # shape fields per DESIGN_SPEC §7
        for f in ("name", "base_url", "status", "active_model_count",
                  "discovered_model_count", "enabled"):
            assert f in p, f"missing field {f}"

    def test_status_reflects_active(self):
        CLIENT.post("/api/ai/providers", headers=AUTH, json={
            "name": "A", "type": "groq", "api_key": "k"})
        listing = CLIENT.get("/api/ai/providers", headers=AUTH).json()
        assert listing["providers"][0]["status"] == "active"
        assert listing["providers"][0]["is_active"] is True


# ─── connect a custom provider ──────────────────────────────────────

@pytest.mark.unit
class TestConnectProvider:
    def test_connect_openai(self):
        resp = CLIENT.post("/api/ai/providers", headers=AUTH, json={
            "name": "OA", "type": "openai", "api_key": "sk-x"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "connected"
        assert "id" in resp.json()

    def test_connect_custom_requires_base_url(self):
        resp = CLIENT.post("/api/ai/providers", headers=AUTH, json={
            "name": "C", "type": "custom", "api_key": "k"})
        assert resp.status_code == 400, resp.text

    def test_connect_custom_ok(self):
        resp = CLIENT.post("/api/ai/providers", headers=AUTH, json={
            "name": "Local", "type": "custom", "api_key": "k",
            "base_url": "http://localhost:1234/v1"})
        assert resp.status_code == 200, resp.text
        pid = resp.json()["id"]
        listing = CLIENT.get("/api/ai/providers", headers=AUTH).json()
        p = listing["providers"][0]
        assert p["base_url"] == "http://localhost:1234/v1"
        assert p["id"] == pid

    def test_invalid_type_rejected(self):
        resp = CLIENT.post("/api/ai/providers", headers=AUTH, json={
            "name": "X", "type": "bogus", "api_key": "k"})
        assert resp.status_code == 400, resp.text

    def test_first_connect_becomes_active(self):
        CLIENT.post("/api/ai/providers", headers=AUTH, json={
            "name": "A", "type": "openai", "api_key": "k"})
        models = CLIENT.get("/api/ai/models", headers=AUTH).json()
        # No models selected yet -> none active.
        assert models["providers"] == []


# ─── discover models (mocked httpx) ─────────────────────────────────

@pytest.mark.unit
class TestDiscoverModels:
    def test_discover_openai_probe(self, monkeypatch):
        fake, resp = _make_httpx_client(payload={
            "object": "list",
            "data": [
                {"id": "gpt-4o-mini", "object": "model", "owned_by": "openai"},
                {"id": "gpt-4o", "object": "model", "owned_by": "openai"},
            ],
        })
        monkeypatch.setattr(httpx, "Client", fake)

        conn = CLIENT.post("/api/ai/providers", headers=AUTH, json={
            "name": "OA", "type": "openai", "api_key": "sk-x"})
        pid = conn.json()["id"]
        disc = CLIENT.get(f"/api/ai/providers/{pid}/models", headers=AUTH)
        assert disc.status_code == 200, disc.text
        body = disc.json()
        assert body["manual_entry"] is False
        ids = [m["id"] for m in body["models"]]
        assert ids == ["gpt-4o-mini", "gpt-4o"]
        # discovered models cached onto the connection
        listing = CLIENT.get("/api/ai/providers", headers=AUTH).json()
        assert listing["providers"][0]["discovered_model_count"] == 2

    def test_discover_auth_error_401(self, monkeypatch):
        fake, resp = _make_httpx_client(status=401)
        monkeypatch.setattr(httpx, "Client", fake)
        conn = CLIENT.post("/api/ai/providers", headers=AUTH, json={
            "name": "OA", "type": "openai", "api_key": "bad"})
        pid = conn.json()["id"]
        disc = CLIENT.get(f"/api/ai/providers/{pid}/models", headers=AUTH)
        assert disc.status_code == 200, disc.text
        body = disc.json()
        # B.4: 401 -> not cached, manual entry fallback with error surfaced.
        assert body["manual_entry"] is True
        assert body["error"]
        assert "401" in body["error"]

    def test_discover_404_falls_back_to_manual(self, monkeypatch):
        fake, resp = _make_httpx_client(status=404)
        monkeypatch.setattr(httpx, "Client", fake)
        conn = CLIENT.post("/api/ai/providers", headers=AUTH, json={
            "name": "OA", "type": "openai", "api_key": "k"})
        pid = conn.json()["id"]
        disc = CLIENT.get(f"/api/ai/providers/{pid}/models", headers=AUTH)
        body = disc.json()
        assert body["manual_entry"] is True
        assert body["models"] == []

    def test_discover_non_json_falls_back(self, monkeypatch):
        fake, resp = _make_httpx_client(status=200, payload=None)
        monkeypatch.setattr(httpx, "Client", fake)
        conn = CLIENT.post("/api/ai/providers", headers=AUTH, json={
            "name": "OA", "type": "openai", "api_key": "k"})
        pid = conn.json()["id"]
        disc = CLIENT.get(f"/api/ai/providers/{pid}/models", headers=AUTH)
        assert disc.json()["manual_entry"] is True

    def test_anthropic_skips_probe_returns_manual(self, monkeypatch):
        # anthropic must NOT hit the network -> monkeypatched Client must be
        # unused (we assert it is never called).
        fake, resp = _make_httpx_client(payload={"object": "list", "data": []})
        monkeypatch.setattr(httpx, "Client", fake)
        conn = CLIENT.post("/api/ai/providers", headers=AUTH, json={
            "name": "AN", "type": "anthropic", "api_key": "k"})
        pid = conn.json()["id"]
        disc = CLIENT.get(f"/api/ai/providers/{pid}/models", headers=AUTH)
        assert disc.status_code == 200, disc.text
        body = disc.json()
        assert body["manual_entry"] is True
        assert body["type"] == "anthropic"
        # Probe skipped: Client never constructed.
        fake.assert_not_called()

    def test_google_skips_probe_returns_manual(self, monkeypatch):
        fake, resp = _make_httpx_client(payload={"object": "list", "data": []})
        monkeypatch.setattr(httpx, "Client", fake)
        conn = CLIENT.post("/api/ai/providers", headers=AUTH, json={
            "name": "GG", "type": "google", "api_key": "k"})
        pid = conn.json()["id"]
        disc = CLIENT.get(f"/api/ai/providers/{pid}/models", headers=AUTH)
        body = disc.json()
        assert body["manual_entry"] is True
        assert body["type"] == "google"
        fake.assert_not_called()

    def test_discover_unknown_provider_404(self):
        disc = CLIENT.get("/api/ai/providers/nope/models", headers=AUTH)
        assert disc.status_code == 404, disc.text


# ─── select models activates provider ──────────────────────────────

@pytest.mark.unit
class TestSelectModels:
    def test_select_activates_and_lists(self, monkeypatch):
        fake, resp = _make_httpx_client(payload={
            "object": "list",
            "data": [{"id": "gpt-4o-mini", "object": "model", "owned_by": "openai"}],
        })
        monkeypatch.setattr(httpx, "Client", fake)
        conn = CLIENT.post("/api/ai/providers", headers=AUTH, json={
            "name": "OA", "type": "openai", "api_key": "sk-x"})
        pid = conn.json()["id"]
        # discover first (populates discovered_models)
        CLIENT.get(f"/api/ai/providers/{pid}/models", headers=AUTH)
        # select
        sel = CLIENT.put(f"/api/ai/providers/{pid}/models", headers=AUTH, json={
            "active": ["gpt-4o-mini"], "default": "gpt-4o-mini"})
        assert sel.status_code == 200, sel.text
        assert sel.json()["ok"] is True
        # /api/ai/models now groups the active model
        models = CLIENT.get("/api/ai/models", headers=AUTH).json()
        assert len(models["providers"]) == 1
        mp = models["providers"][0]
        assert mp["is_active"] is True
        assert mp["models"][0]["id"] == "gpt-4o-mini"
        assert mp["models"][0]["default"] is True
        # provider list reflects active status
        listing = CLIENT.get("/api/ai/providers", headers=AUTH).json()
        assert listing["providers"][0]["active_model_count"] == 1

    def test_select_unknown_model_rejected(self, monkeypatch):
        fake, resp = _make_httpx_client(payload={
            "object": "list",
            "data": [{"id": "gpt-4o-mini", "object": "model", "owned_by": "openai"}],
        })
        monkeypatch.setattr(httpx, "Client", fake)
        conn = CLIENT.post("/api/ai/providers", headers=AUTH, json={
            "name": "OA", "type": "openai", "api_key": "sk-x"})
        pid = conn.json()["id"]
        CLIENT.get(f"/api/ai/providers/{pid}/models", headers=AUTH)
        sel = CLIENT.put(f"/api/ai/providers/{pid}/models", headers=AUTH, json={
            "active": ["does-not-exist"]})
        assert sel.status_code == 400, sel.text

    def test_select_unknown_provider_404(self):
        sel = CLIENT.put("/api/ai/providers/nope/models", headers=AUTH, json={
            "active": ["x"]})
        assert sel.status_code == 404, sel.text


# ─── delete provider ───────────────────────────────────────────────

@pytest.mark.unit
class TestDeleteProvider:
    def test_delete_works_and_404_twice(self):
        conn = CLIENT.post("/api/ai/providers", headers=AUTH, json={
            "name": "OA", "type": "openai", "api_key": "k"})
        pid = conn.json()["id"]
        resp = CLIENT.delete(f"/api/ai/providers/{pid}", headers=AUTH)
        assert resp.status_code == 200, resp.text
        assert resp.json()["ok"] is True
        again = CLIENT.delete(f"/api/ai/providers/{pid}", headers=AUTH)
        assert again.status_code == 404, again.text

    def test_delete_clears_active_pointer(self, monkeypatch):
        fake, resp = _make_httpx_client(payload={
            "object": "list",
            "data": [{"id": "gpt-4o-mini", "object": "model", "owned_by": "openai"}],
        })
        monkeypatch.setattr(httpx, "Client", fake)
        conn = CLIENT.post("/api/ai/providers", headers=AUTH, json={
            "name": "OA", "type": "openai", "api_key": "sk-x"})
        pid = conn.json()["id"]
        CLIENT.get(f"/api/ai/providers/{pid}/models", headers=AUTH)
        CLIENT.put(f"/api/ai/providers/{pid}/models", headers=AUTH,
                   json={"active": ["gpt-4o-mini"]})
        # now delete the active provider
        CLIENT.delete(f"/api/ai/providers/{pid}", headers=AUTH)
        cfg = app_module.config_manager.config
        assert cfg.ai_active_provider_id is None or cfg.ai_active_provider_id != pid


# ─── legacy scalar migration ───────────────────────────────────────

@pytest.mark.unit
class TestLegacyMigration:
    def test_migration_synthesizes_provider_from_legacy_scalars(self):
        cfg = TubeManagerConfig(
            ai_provider="groq",
            ai_api_key=SecretStr("gsk-legacy"),
            ai_custom_endpoint="",
            ai_custom_model="",
        )
        cm = ConfigManager()
        # Run the migration against the in-memory config.
        import asyncio
        asyncio.run(cm._migrate_legacy_provider(cfg))
        assert len(cfg.ai_providers) == 1
        p = cfg.ai_providers[0]
        assert p.type == "groq"
        assert p.base_url == "https://api.groq.com"
        assert _secret(cfg.ai_providers[0].api_key) == "gsk-legacy"
        assert cfg.ai_active_provider_id == p.id
        # groq legacy default model pre-seeded
        assert "llama-3.3-70b-versatile" in p.selected_models

    def test_migration_custom_uses_endpoint(self):
        cfg = TubeManagerConfig(
            ai_provider="custom",
            ai_api_key=SecretStr("k"),
            ai_custom_endpoint="http://localhost:9999/v1",
            ai_custom_model="local-model",
        )
        import asyncio
        cm = ConfigManager()
        asyncio.run(cm._migrate_legacy_provider(cfg))
        assert cfg.ai_providers[0].base_url == "http://localhost:9999"
        assert cfg.ai_providers[0].selected_models == ["local-model"]

    def test_migration_idempotent_when_providers_present(self):
        cfg = TubeManagerConfig(
            ai_providers=[ProviderConnection(
                id="fixed", name="P", type="openai",
                api_key=SecretStr("k"), created_at="t")],
            ai_provider="groq",
            ai_api_key=SecretStr("gsk"),
        )
        import asyncio
        cm = ConfigManager()
        asyncio.run(cm._migrate_legacy_provider(cfg))
        # Must NOT append a second provider.
        assert len(cfg.ai_providers) == 1
        assert cfg.ai_providers[0].id == "fixed"

    def test_migration_noop_when_no_legacy(self):
        cfg = TubeManagerConfig()
        import asyncio
        cm = ConfigManager()
        asyncio.run(cm._migrate_legacy_provider(cfg))
        assert cfg.ai_providers == []


def _secret(val):
    return val.get_secret_value() if hasattr(val, "get_secret_value") else str(val)


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
