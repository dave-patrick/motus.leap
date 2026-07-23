import tempfile
from pathlib import Path

import pytest

from api import auth as auth_module
from api.auth import create_access_token
from services.youtube_service import _extract_quota_reason


def _seed_user(monkeypatch, sub: str = "qg") -> dict:
    # Mirror the proven auth pattern from test_security_and_cache_fixes.py:
    # the JWT 'sub' must exist in the in-memory users db, else get_current_user 401s.
    users_db = {
        sub: {
            "id": "qgid",
            "username": sub,
            "email": f"{sub}@example.com",
            "hashed_password": "x",
            "role": "admin",
            "is_active": True,
            "created_at": "2026-07-13",
            "last_login": None,
        }
    }
    monkeypatch.setattr(auth_module, "_cached_users_db", users_db)
    auth_module._cached_users_db = users_db
    token = create_access_token({"sub": sub})
    return {"Authorization": f"Bearer {token}"}


def test_duplicates_not_ready_no_fallthrough(test_client, mock_youtube_service, monkeypatch):
    # QUOTA GUARD: with no maintenance.json on disk, the duplicates endpoint
    # must NOT fall through to a live get_videos()/fetch_all_data() enumeration.
    d = tempfile.mkdtemp(prefix="motus_test_")
    monkeypatch.setenv("TUBE_MANAGER_DATA_DIR", d)
    Path(d, "maintenance.json").unlink(missing_ok=True)
    headers = _seed_user(monkeypatch)

    r = test_client.get("/api/youtube/duplicates", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "not_ready"
    mock_youtube_service.get_videos.assert_not_called()


def test_misplaced_not_ready_no_fallthrough(test_client, mock_youtube_service, monkeypatch):
    d = tempfile.mkdtemp(prefix="motus_test_")
    monkeypatch.setenv("TUBE_MANAGER_DATA_DIR", d)
    Path(d, "maintenance.json").unlink(missing_ok=True)
    headers = _seed_user(monkeypatch)

    r = test_client.get("/api/youtube/misplaced", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "not_ready"
    mock_youtube_service.get_videos.assert_not_called()


def test_extract_quota_reason():
    class Resp:
        def __init__(self, body):
            self._b = body

        def json(self):
            return self._b

    q = Resp({"error": {"errors": [{"reason": "quotaExceeded"}]}})
    assert _extract_quota_reason(q) == "quotaExceeded"
    nq = Resp({"error": {"errors": [{"reason": "forbidden"}]}})
    assert _extract_quota_reason(nq) == "forbidden"
    assert _extract_quota_reason(Resp({"foo": 1})) is None
