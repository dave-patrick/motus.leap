"""Regression tests for security + data-integrity fixes (Sheldon #1-#10).

These lock in the fixes that previously had NO coverage:
  - #1: /api/storage/export must never leak raw OAuth secrets or API keys.
  - #2: write ops must call _cache_invalidate_playlist (not a no-op
        `_cache.set(..., None)` that never matched the read key).

Harness mirrors test_maintenance_action.py: stable SECRET_KEY, seeded auth
user, authed TestClient, mocked youtube_service (no network).
"""
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
class TestStorageExportSecretRedaction:
    """Sheldon #1 — export must not leak raw secrets."""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        import app as app_module
        from api import auth as auth_module

        users_db = {
            "sec": {
                "id": secrets.token_hex(8),
                "username": "sec",
                "email": "sec@example.com",
                "hashed_password": "x",
                "role": "admin",
                "is_active": True,
                "created_at": datetime.now(),
                "last_login": None,
            }
        }
        monkeypatch.setattr(auth_module, "_cached_users_db", users_db)
        auth_module._cached_users_db = users_db

        token = create_access_token({"sub": "sec"})
        self.auth_headers = {"Authorization": f"Bearer {token}"}

        app_module.app.router.lifespan_context = __import__(
            "contextlib"
        ).asynccontextmanager(lambda a: (yield))
        self.client = TestClient(
            app_module.app,
            base_url="http://localhost:8000",
            headers={"Origin": "http://localhost:8000"},
        )

        # Seed a config that genuinely contains secrets + non-secret data.
        self.real_client_secret = "CS_SUPER_SECRET_12345"
        self.real_access_token = "AT_SUPER_SECRET_67890"
        self.real_refresh_token = "RT_SUPER_SECRET_11111"
        self.real_youtube_key = "YT_SUPER_SECRET_22222"
        self.real_ai_key = "AI_SUPER_SECRET_33333"
        cfg = TubeManagerConfig(
            youtube_api_key=SecretStr(self.real_youtube_key),
            ai_api_key=SecretStr(self.real_ai_key),
            oauth=YouTubeOAuthConfig(
                client_id="cid_visible",
                client_secret=SecretStr(self.real_client_secret),
                access_token=self.real_access_token,
                refresh_token=self.real_refresh_token,
                token_expiry=999,
            ),
            channel_mappings={"UCabc": "Music"},
        )
        # Mock youtube_service so stats() doesn't need the network.
        fake_service = Mock(spec=YouTubeService)
        fake_service.get_basic_stats = AsyncMock(
            return_value={"total_playlists": 1, "total_videos": 2}
        )
        fake_service._cache = Mock()
        fake_service._cache.get_stats.return_value = {"hit_rate": "N/A"}
        monkeypatch.setattr(app_module, "youtube_service", fake_service)
        monkeypatch.setattr(app_module.config_manager, "_config", cfg)

    def _export(self):
        return self.client.get("/api/storage/export", headers=self.auth_headers)

    def test_export_status_ok(self):
        r = self._export()
        assert r.status_code == 200

    def test_export_does_not_leak_raw_client_secret(self):
        body = self._export().json()
        dumped = __import__("json").dumps(body)
        assert self.real_client_secret not in dumped

    def test_export_does_not_leak_raw_oauth_tokens(self):
        body = self._export().json()
        dumped = __import__("json").dumps(body)
        assert self.real_access_token not in dumped
        assert self.real_refresh_token not in dumped

    def test_export_does_not_leak_raw_api_keys(self):
        body = self._export().json()
        dumped = __import__("json").dumps(body)
        assert self.real_youtube_key not in dumped
        assert self.real_ai_key not in dumped

    def test_export_masks_secret_fields(self):
        body = self._export().json()
        oauth = body["config"]["oauth"]
        assert oauth["client_secret"] == "••••••••"
        assert oauth["access_token"] == "••••••••"
        assert oauth["refresh_token"] == "••••••••"

    def test_export_preserves_non_secret_fields(self):
        body = self._export().json()
        oauth = body["config"]["oauth"]
        assert oauth["client_id"] == "cid_visible"
        assert oauth["token_expiry"] == 999
        assert body["config"]["channel_mappings"] == {"UCabc": "Music"}


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
