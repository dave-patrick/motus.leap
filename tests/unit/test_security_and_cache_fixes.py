import os
import tempfile
import secrets
from datetime import datetime

import pytest
from unittest.mock import Mock, AsyncMock, patch
from pydantic import SecretStr

os.environ.setdefault(
    "TUBE_MANAGER_DATA_DIR", tempfile.mkdtemp(prefix="motus_sec_test_")
)
os.environ["TUBE_MANAGER_SECRET_KEY"] = os.environ.get(
    "TUBE_MANAGER_SECRET_KEY", "test_secret_key_for_security_unit_tests"
)

from api.auth import create_access_token, _cached_users_db
from fastapi.testclient import TestClient
from models.config import TubeManagerConfig, YouTubeOAuthConfig
from services.youtube_service import YouTubeService


@pytest.mark.unit
class TestCacheInvalidationOnWrite:
    """Sheldon #2 — write ops must invalidate the real playlist cache."""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        import app as app_module
        from api import auth as auth_module

        users_db = {
            "cinv": {
                "id": secrets.token_hex(8),
                "username": "cinv",
                "email": "cinv@example.com",
                "hashed_password": "x",
                "role": "admin",
                "is_active": True,
                "created_at": datetime.now(),
                "last_login": None,
            }
        }
        monkeypatch.setattr(auth_module, "_cached_users_db", users_db)
        auth_module._cached_users_db = users_db

        token = create_access_token({"sub": "cinv"})
        self.auth_headers = {"Authorization": f"Bearer {token}"}

        app_module.app.router.lifespan_context = __import__(
            "contextlib"
        ).asynccontextmanager(lambda a: (yield))
        self.client = TestClient(
            app_module.app,
            base_url="http://localhost:8000",
            headers={"Origin": "http://localhost:8000"},
        )

        # Build a fake youtube_service whose client remove works and whose
        # cache-invalidation method we can observe.
        self.fake_client = Mock()
        self.fake_client.remove_video_from_playlist = Mock()
        fake_service = Mock(spec=YouTubeService)
        fake_service.get_client.return_value = self.fake_client
        fake_service._cache_invalidate_playlist = AsyncMock()
        monkeypatch.setattr(app_module, "youtube_service", fake_service)
        self.fake_service = fake_service

    def test_remove_action_invalidates_cache(self, monkeypatch):
        r = self.client.post(
            "/api/maintenance/action",
            json={
                "action": "remove",
                "type": "dup",
                "video_id": "abc123XYZ_9",
                "playlist_id": "PL1aaaaaaaaaaa",
                "playlist_item_id": "item_abc123XYZ_9",
            },
            headers=self.auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "success"
        assert body["action"] == "remove"
        # The real invalidation must have been called with the playlist id.
        self.fake_service._cache_invalidate_playlist.assert_awaited_once_with(
            "PL1aaaaaaaaaaa"
        )
