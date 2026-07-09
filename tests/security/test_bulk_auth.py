"""Security tests for the bulk operations router (bug C1).

Verifies that every bulk endpoint under /api/bulk is protected by the same
authentication (get_current_user) and CSRF-origin (verify_origin) dependencies
used by the rest of the app. Previously these routes were registered WITHOUT
any auth dependency, making them fully unauthenticated on the live deploy.
"""

import pytest

pytestmark = pytest.mark.security


class TestBulkAuthRequired:
    """Hitting bulk endpoints without credentials must be rejected."""

    @pytest.mark.asyncio
    async def test_unauthenticated_get_operations_returns_401(self, async_test_client):
        resp = await async_test_client.get("/api/bulk/operations")
        assert resp.status_code in (401, 403), resp.text

    @pytest.mark.asyncio
    async def test_unauthenticated_post_move_returns_401(self, async_test_client):
        resp = await async_test_client.post(
            "/api/bulk/move",
            json={"video_ids": ["dQw4w9WgXcQ"], "target_playlist_id": "PLxxxx"},
        )
        assert resp.status_code in (401, 403), resp.text

    @pytest.mark.asyncio
    async def test_unauthenticated_post_delete_returns_401(self, async_test_client):
        resp = await async_test_client.post(
            "/api/bulk/delete",
            json={"video_ids": ["dQw4w9WgXcQ"], "playlist_id": "PLxxxx"},
        )
        assert resp.status_code in (401, 403), resp.text

    @pytest.mark.asyncio
    async def test_unauthenticated_post_tag_returns_401(self, async_test_client):
        resp = await async_test_client.post(
            "/api/bulk/tag",
            json={"video_ids": ["dQw4w9WgXcQ"], "tags": ["t"], "action": "add"},
        )
        assert resp.status_code in (401, 403), resp.text

    @pytest.mark.asyncio
    async def test_unauthenticated_post_import_returns_401(self, async_test_client):
        import base64

        payload = base64.b64encode(b'[]').decode()
        resp = await async_test_client.post(
            "/api/bulk/import",
            json={"resource_type": "playlists", "format": "json", "data": payload},
        )
        assert resp.status_code in (401, 403), resp.text

    @pytest.mark.asyncio
    async def test_unauthenticated_delete_operation_returns_401(self, async_test_client):
        resp = await async_test_client.delete("/api/bulk/operations/nonexistent")
        assert resp.status_code in (401, 403), resp.text


class TestBulkAuthAccepted:
    """With a valid session cookie, bulk endpoints must be reachable."""

    def test_authenticated_get_operations_returns_200(self, test_client):
        resp = test_client.get("/api/bulk/operations")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "total" in data
        assert "operations" in data

    def test_authenticated_delete_operation_returns_200_or_404(self, test_client):
        # With valid creds the route is reached; operation id is fake so the
        # route logic (404) or cancelled (400) is expected -- NOT 401/403.
        resp = test_client.delete("/api/bulk/operations/nonexistent")
        assert resp.status_code in (200, 400, 404), resp.text
        assert resp.status_code not in (401, 403), resp.text
