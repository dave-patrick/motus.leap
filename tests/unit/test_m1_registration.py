"""
M1 regression: open self-registration must be blocked by default.

The single-operator tool must NOT expose a public sign-up surface. The
`/api/auth/register` endpoint is gated behind the `allow_self_registration`
config flag (default False). When disabled, register returns 403; login for an
existing user must still work.
"""

import os
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("TUBE_MANAGER_DATA_DIR", tempfile.mkdtemp(prefix="motus_m1_test_"))

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def raw_client(mock_youtube_service):
    """Test client with lifespan disabled and no auto-registered user."""
    from app import app as fastapi_app
    import app
    app.youtube_service = mock_youtube_service

    @asynccontextmanager
    async def _noop_lifespan(a):
        yield
    fastapi_app.router.lifespan_context = _noop_lifespan

    with TestClient(
        fastapi_app,
        base_url="http://localhost:8000",
        headers={"Origin": "http://localhost:8000"},
    ) as client:
        yield client


@pytest.mark.security
class TestM1RegistrationGate:
    def test_register_blocked_by_default(self, raw_client):
        """Open self-registration returns 403 when the flag is off (default)."""
        from app import config_manager
        config_manager.config.allow_self_registration = False

        resp = raw_client.post(
            "/api/auth/register",
            json={
                "username": f"attacker_{uuid.uuid4().hex[:8]}",
                "email": "attacker@example.com",
                "password": "password123",
            },
        )
        assert resp.status_code == 403, resp.text
        assert "registration" in resp.text.lower()

    def test_login_still_works_for_existing_user(self, raw_client):
        """Legitimate login continues to work regardless of the registration gate."""
        from app import config_manager

        unique = f"operator_{uuid.uuid4().hex[:8]}"
        # Temporarily enable registration to seed a legitimate account.
        config_manager.config.allow_self_registration = True
        try:
            reg = raw_client.post(
                "/api/auth/register",
                json={
                    "username": unique,
                    "email": f"{unique}@example.com",
                    "password": "password123",
                },
            )
            assert reg.status_code == 201, reg.text
        finally:
            # Restore the secure default so the gate stays closed.
            config_manager.config.allow_self_registration = False

        # With registration disabled again, login must still succeed.
        login = raw_client.post(
            "/api/auth/login",
            json={"username": unique, "password": "password123"},
        )
        assert login.status_code == 200, login.text
        assert login.json().get("access_token")

        # And a fresh registration is still blocked.
        blocked = raw_client.post(
            "/api/auth/register",
            json={
                "username": f"another_{uuid.uuid4().hex[:8]}",
                "email": "another@example.com",
                "password": "password123",
            },
        )
        assert blocked.status_code == 403, blocked.text
