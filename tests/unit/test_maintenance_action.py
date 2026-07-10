"""Unit tests for the POST /api/maintenance/action endpoint.

These tests exercise the input-validation / error paths and the fix_all
aggregation logic with a mocked YouTube client (no network required).

Auth note: self-registration is disabled in the deployment, so we set a
stable TUBE_MANAGER_SECRET_KEY, seed a user into the auth db, and mint a
valid JWT via the app's own create_access_token (same SECRET_KEY), sending
it as a Bearer token — mirroring how the logged-in frontend calls the
endpoint.
"""
import os
import tempfile
import secrets
from datetime import datetime

import pytest
from unittest.mock import Mock, AsyncMock, patch

# Set a STABLE secret key BEFORE importing app modules so create_access_token
# and get_current_user agree on the signing key within this process.
os.environ.setdefault("TUBE_MANAGER_DATA_DIR", tempfile.mkdtemp(prefix="motus_maint_test_"))
os.environ["TUBE_MANAGER_SECRET_KEY"] = os.environ.get(
    "TUBE_MANAGER_SECRET_KEY", "test_secret_key_for_maintenance_unit_tests"
)

from api.auth import create_access_token, _cached_users_db
from fastapi.testclient import TestClient


@pytest.mark.unit
class TestMaintenanceActionEndpoint:
    """Validate the Maintenance Queue action endpoint contract."""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        """Seed a user into the auth db and build an authed TestClient."""
        import app as app_module
        from api import auth as auth_module

        users_db = {
            "mtest": {
                "id": secrets.token_hex(8),
                "username": "mtest",
                "email": "mtest@example.com",
                "hashed_password": "x",
                "role": "admin",
                "is_active": True,
                "created_at": datetime.now(),
                "last_login": None,
            }
        }
        monkeypatch.setattr(auth_module, "_cached_users_db", users_db)
        auth_module._cached_users_db = users_db

        token = create_access_token({"sub": "mtest"})
        self.auth_headers = {"Authorization": f"Bearer {token}"}

        app_module.app.router.lifespan_context = __import__(
            "contextlib"
        ).asynccontextmanager(lambda a: (yield))
        self.client = TestClient(
            app_module.app,
            base_url="http://localhost:8000",
            headers={"Origin": "http://localhost:8000"},
        )

    def _patch_youtube(self, monkeypatch, fake_client):
        """Replace the module-global youtube_service with one returning fake_client."""
        import app as app_module
        from services.youtube_service import YouTubeService
        fake_service = Mock(spec=YouTubeService)
        fake_service.get_client.return_value = fake_client
        fake_service._cache = Mock()
        fake_service._cache.set = AsyncMock()
        monkeypatch.setattr(app_module, "youtube_service", fake_service)
        return fake_service

    # --- input validation -------------------------------------------------

    def test_invalid_action_rejected(self, monkeypatch):
        fake_client = Mock()
        self._patch_youtube(monkeypatch, fake_client)
        r = self.client.post(
            "/api/maintenance/action",
            json={"action": "explode", "type": "dup", "video_id": "abc123XYZ_9"},
            headers=self.auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "error"
        assert "invalid action" in body["error"]

    def test_missing_type_rejected_for_single_action(self, monkeypatch):
        fake_client = Mock()
        self._patch_youtube(monkeypatch, fake_client)
        r = self.client.post(
            "/api/maintenance/action",
            json={"action": "remove", "video_id": "abc123XYZ_9", "playlist_id": "PL1aaaaaaaaaaa"},
            headers=self.auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "error"
        assert "type" in body["error"]

    def test_unauthenticated_rejected(self, monkeypatch):
        fake_client = Mock()
        self._patch_youtube(monkeypatch, fake_client)
        r = self.client.post(
            "/api/maintenance/action",
            json={"action": "keep", "type": "dup", "video_id": "abc123XYZ_9"},
        )
        # No auth cookie/header -> get_current_user should reject.
        assert r.status_code in (401, 403)

    # --- keep is a no-op ---------------------------------------------------

    def test_keep_is_noop(self, monkeypatch):
        fake_client = Mock()
        fake_client.remove_video_from_playlist_item = Mock()
        fake_client.add_video_to_playlist = Mock()
        self._patch_youtube(monkeypatch, fake_client)
        r = self.client.post(
            "/api/maintenance/action",
            json={"action": "keep", "type": "dup", "video_id": "abc123XYZ_9"},
            headers=self.auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "success"
        assert body["action"] == "keep"
        fake_client.remove_video_from_playlist_item.assert_not_called()
        fake_client.add_video_to_playlist.assert_not_called()

    # --- remove uses supplied playlist_item_id directly -------------------

    def test_remove_with_supplied_item_id(self, monkeypatch):
        fake_client = Mock()
        fake_client.remove_video_from_playlist_item = Mock(return_value={})
        fake_client.find_playlist_item_id = Mock(return_value="lookedup_id")
        self._patch_youtube(monkeypatch, fake_client)
        r = self.client.post(
            "/api/maintenance/action",
            json={
                "action": "remove",
                "type": "dup",
                "video_id": "abc123XYZ_9",
                "playlist_id": "PL1aaaaaaaaaaa",
                "playlist_item_id": "item_123aaaaa",
            },
            headers=self.auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "success"
        assert body["action"] == "remove"
        # Supplied id used directly; no list lookup needed.
        fake_client.remove_video_from_playlist_item.assert_called_once_with("item_123aaaaa")
        fake_client.find_playlist_item_id.assert_not_called()

    # --- remove falls back to list lookup when no item id -----------------

    def test_remove_looks_up_item_id(self, monkeypatch):
        fake_client = Mock()
        fake_client.find_playlist_item_id = Mock(return_value="resolved_id")
        fake_client.remove_video_from_playlist_item = Mock(return_value={})
        self._patch_youtube(monkeypatch, fake_client)
        r = self.client.post(
            "/api/maintenance/action",
            json={
                "action": "remove",
                "type": "dup",
                "video_id": "abc123XYZ_9",
                "playlist_id": "PL1aaaaaaaaaaa",
            },
            headers=self.auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "success"
        fake_client.find_playlist_item_id.assert_called_once_with("PL1aaaaaaaaaaa", "abc123XYZ_9")
        fake_client.remove_video_from_playlist_item.assert_called_once_with("resolved_id")

    # --- move deletes from source then inserts to target ------------------

    def test_move_deletes_then_inserts(self, monkeypatch):
        fake_client = Mock()
        fake_client.find_playlist_item_id = Mock(return_value="src_item")
        fake_client.remove_video_from_playlist_item = Mock(return_value={})
        fake_client.add_video_to_playlist = Mock(return_value={"id": "new_item"})
        self._patch_youtube(monkeypatch, fake_client)
        r = self.client.post(
            "/api/maintenance/action",
            json={
                "action": "move",
                "type": "move",
                "video_id": "abc123XYZ_9",
                "playlist_id": "PL_SRCaaaaaaaa",
                "target_playlist_id": "PL_DSTaaaaaaaaa",
            },
            headers=self.auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "success"
        assert body["action"] == "move"
        fake_client.remove_video_from_playlist_item.assert_called_once_with("src_item")
        fake_client.add_video_to_playlist.assert_called_once_with("PL_DSTaaaaaaaaa", "abc123XYZ_9")

    # --- remove with no item id found -> error, no delete -----------------

    def test_remove_item_not_found(self, monkeypatch):
        fake_client = Mock()
        fake_client.find_playlist_item_id = Mock(return_value=None)
        fake_client.remove_video_from_playlist_item = Mock()
        self._patch_youtube(monkeypatch, fake_client)
        r = self.client.post(
            "/api/maintenance/action",
            json={
                "action": "remove",
                "type": "dup",
                "video_id": "abc123XYZ_9",
                "playlist_id": "PL1aaaaaaaaaaa",
            },
            headers=self.auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "error"
        fake_client.remove_video_from_playlist_item.assert_not_called()

    # --- fix_all aggregates per-record results ----------------------------

    def test_fix_all_remove_aggregates(self, monkeypatch, tmp_path):
        # Point maintenance.json at a temp file with two dup records, each in
        # TWO playlists. fix_all+dup must delete only the NON-primary copy
        # (playlists[1]), keeping the primary (playlists[0]).
        import app as app_module
        mfile = tmp_path / "maintenance.json"
        mfile.write_text(
            '{"duplicated_videos": ['
            '{"video_id": "vidAAAA1111", "playlists": [{"id": "PL1aaaaaaaaaaa", "title": "A"}, {"id": "PL1baaaaaaaaaa", "title": "Ab"}]},'
            '{"video_id": "vidBBBB2222", "playlists": [{"id": "PL2aaaaaaaaaaa", "title": "B"}, {"id": "PL2baaaaaaaaaa", "title": "Bb"}]}'
            '], "misplaced_videos": [], "move_from_x_to_y": []}'
        )
        monkeypatch.setenv("TUBE_MANAGER_DATA_DIR", str(tmp_path))

        fake_client = Mock()
        # 2 records x 1 non-primary copy each = 2 lookups, 2 deletes.
        fake_client.find_playlist_item_id = Mock(side_effect=["i1", "i2"])
        fake_client.remove_video_from_playlist_item = Mock(return_value={})
        self._patch_youtube(monkeypatch, fake_client)
        r = self.client.post(
            "/api/maintenance/action",
            json={"action": "fix_all", "type": "dup"},
            headers=self.auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["processed"] == 2
        assert body["succeeded"] == 2
        # Only the non-primary copies deleted (playlists[1]); primary kept.
        assert fake_client.remove_video_from_playlist_item.call_count == 2

    def test_fix_all_misplaced_deletes_each_item(self, monkeypatch, tmp_path):
        import app as app_module
        mfile = tmp_path / "maintenance.json"
        mfile.write_text(
            '{"duplicated_videos": [], '
            '"misplaced_videos": ['
            '{"video_id": "vM1", "current_playlist_id": "PLM1aaaaaaaaaa", "mapped_playlist_id": "PLMXaaaaaaaaaa"},'
            '{"video_id": "vM2", "current_playlist_id": "PLM2aaaaaaaaaa", "mapped_playlist_id": "PLMXaaaaaaaaaa"}'
            '], "move_from_x_to_y": []}'
        )
        monkeypatch.setenv("TUBE_MANAGER_DATA_DIR", str(tmp_path))
        fake_client = Mock()
        fake_client.find_playlist_item_id = Mock(side_effect=["mi1", "mi2"])
        fake_client.remove_video_from_playlist_item = Mock(return_value={})
        self._patch_youtube(monkeypatch, fake_client)
        r = self.client.post(
            "/api/maintenance/action",
            json={"action": "fix_all", "type": "misplaced"},
            headers=self.auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "success"
        assert body["processed"] == 2
        assert body["succeeded"] == 2
        assert fake_client.remove_video_from_playlist_item.call_count == 2

    def test_fix_all_move_deletes_each_item(self, monkeypatch, tmp_path):
        import app as app_module
        mfile = tmp_path / "maintenance.json"
        mfile.write_text(
            '{"duplicated_videos": [], "misplaced_videos": [], '
            '"move_from_x_to_y": ['
            '{"video_id": "vO1", "source_playlist_id": "PLO1aaaaaaaaaa", "target_playlist_id": "PLOXaaaaaaaaaa"},'
            '{"video_id": "vO2", "source_playlist_id": "PLO2aaaaaaaaaa", "target_playlist_id": "PLOXaaaaaaaaaa"}'
            ']}'
        )
        monkeypatch.setenv("TUBE_MANAGER_DATA_DIR", str(tmp_path))
        fake_client = Mock()
        fake_client.find_playlist_item_id = Mock(side_effect=["oi1", "oi2"])
        fake_client.remove_video_from_playlist_item = Mock(return_value={})
        self._patch_youtube(monkeypatch, fake_client)
        r = self.client.post(
            "/api/maintenance/action",
            json={"action": "fix_all", "type": "move"},
            headers=self.auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "success"
        assert body["processed"] == 2
        assert body["succeeded"] == 2
        assert fake_client.remove_video_from_playlist_item.call_count == 2
