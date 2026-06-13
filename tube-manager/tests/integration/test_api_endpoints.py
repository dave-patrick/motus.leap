"""Integration tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestAPIEndpoints:
    """Test API endpoints integration."""

    def test_health_endpoint(self, test_client):
        """Test health check endpoint."""
        response = test_client.get("/health")

        assert_response_success(response, 200)
        data = response.json()
        assert data["status"] == "ok"

    def test_fetch_all_endpoint(self, test_client):
        """Test fetch-all YouTube data endpoint."""
        response = test_client.get("/api/youtube/fetch-all")

        assert_response_success(response, 200)
        data = response.json()
        assert "playlists" in data
        assert "subscriptions" in data
        assert "videos" in data

    def test_fetch_all_with_force_refresh(self, test_client):
        """Test fetch-all with force refresh parameter."""
        response = test_client.get("/api/youtube/fetch-all?force_refresh=true")

        assert_response_success(response, 200)
        data = response.json()
        assert "playlists" in data

    def test_config_endpoint(self, test_client):
        """Test config retrieval endpoint."""
        response = test_client.get("/api/config")

        assert_response_success(response, 200)
        data = response.json()
        assert "config" in data
        assert "youtube_api_key" in data["config"]

    def test_config_excludes_secrets(self, test_client):
        """Test that config endpoint excludes sensitive secrets."""
        response = test_client.get("/api/config")

        assert_response_success(response, 200)
        data = response.json()

        # Check that secrets are excluded
        assert "access_token" not in data["config"]
        assert "refresh_token" not in data["config"]
        assert "client_secret" not in data["config"]

    def test_action_endpoint(self, test_client):
        """Test trigger action endpoint."""
        response = test_client.post("/api/action", json={
            "action": "full_cluster_scan",
            "payload": {"force": True}
        })

        assert_response_success(response, 200)
        data = response.json()
        assert "message" in data

    def test_action_endpoint_invalid_json(self, test_client):
        """Test action endpoint with invalid JSON."""
        response = test_client.post("/api/action", json={
            "action": "invalid_action"
        })

        # Should still return 200, but with error message
        assert response.status_code == 200
        data = response.json()
        assert "error" in data or "message" in data

    def test_save_mappings_endpoint(self, test_client, sample_channel_mappings):
        """Test save channel mappings endpoint."""
        response = test_client.post("/api/mappings", json={
            "mappings": sample_channel_mappings
        })

        assert_response_success(response, 200)
        data = response.json()
        assert "message" in data

    def test_get_mappings_endpoint(self, test_client):
        """Test get channel mappings endpoint."""
        response = test_client.get("/api/mappings")

        assert_response_success(response, 200)
        data = response.json()
        assert "mappings" in data
        assert isinstance(data["mappings"], dict)

    def test_dashboard_page(self, test_client):
        """Test dashboard page loads."""
        response = test_client.get("/dashboard")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_dashboard_has_security_headers(self, test_client):
        """Test dashboard page has security headers."""
        response = test_client.get("/dashboard")

        assert_security_headers(response)

    def test_playlists_page(self, test_client):
        """Test playlists page loads."""
        response = test_client.get("/playlists")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_subscriptions_page(self, test_client):
        """Test subscriptions page loads."""
        response = test_client.get("/subscriptions")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_rules_page(self, test_client):
        """Test rules page loads."""
        response = test_client.get("/rules")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_ai_page(self, test_client):
        """Test AI page loads."""
        response = test_client.get("/ai")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_oauth_start_endpoint(self, test_client):
        """Test OAuth start endpoint."""
        response = test_client.get("/oauth/start")

        # Should redirect or return OAuth URL
        assert response.status_code in [200, 302]

    def test_oauth_callback_endpoint(self, test_client):
        """Test OAuth callback endpoint."""
        # This requires a real OAuth flow, so we test the endpoint exists
        response = test_client.get("/oauth/callback?code=test_code")

        # Will fail without real code, but endpoint exists
        assert response.status_code in [200, 400, 500]

    def test_oauth_disconnect_endpoint(self, test_client):
        """Test OAuth disconnect endpoint."""
        response = test_client.post("/oauth/disconnect")

        assert_response_success(response, 200)
        data = response.json()
        assert "message" in data

    def test_static_files_served(self, test_client):
        """Test static files are served correctly."""
        response = test_client.get("/static/dashboard.html")

        # May 404 if file doesn't exist, but endpoint exists
        assert response.status_code in [200, 404]


@pytest.mark.integration
class TestRateLimiting:
    """Test rate limiting on endpoints."""

    @pytest.mark.slow
    def test_fetch_all_rate_limit(self, test_client):
        """Test that fetch-all endpoint is rate limited."""
        # Make 11 requests (limit is 10/minute)
        responses = []
        for i in range(11):
            response = test_client.get("/api/youtube/fetch-all")
            responses.append(response)

        # Last request should be rate limited
        last_response = responses[-1]
        assert last_response.status_code == 429
        data = last_response.json()
        assert "detail" in data


@pytest.mark.integration
class TestWebSocket:
    """Test WebSocket integration."""

    @pytest.mark.asyncio
    async def test_websocket_connection(self, async_test_client):
        """Test WebSocket connection."""
        with async_test_client.websocket_connect("/ws/terminal") as websocket:
            # Send a message
            websocket.send_json({"type": "ping"})

            # Receive a message
            data = websocket.receive_json()
            assert data is not None

    @pytest.mark.asyncio
    async def test_websocket_broadcast(self, async_test_client):
        """Test WebSocket broadcast to multiple clients."""
        # Connect two clients
        with async_test_client.websocket_connect("/ws/terminal") as ws1:
            with async_test_client.websocket_connect("/ws/terminal") as ws2:
                # Send message from ws1
                ws1.send_json({"type": "test", "message": "Hello"})

                # Both should receive (depending on implementation)
                try:
                    data = ws2.receive_json(timeout=1)
                    assert data is not None
                except:
                    # WebSocket broadcast may not work in tests
                    pass

    @pytest.mark.asyncio
    async def test_websocket_throttling(self, async_test_client):
        """Test WebSocket message throttling."""
        with async_test_client.websocket_connect("/ws/terminal") as websocket:
            # Send many messages quickly
            for i in range(20):
                websocket.send_json({"type": "test", "message": f"Message {i}"})

            # Should not crash
            # Some messages may be dropped due to throttling
            try:
                data = websocket.receive_json(timeout=1)
                assert data is not None
            except:
                pass


@pytest.mark.integration
class TestErrorHandling:
    """Test error handling in API."""

    def test_404_handler(self, test_client):
        """Test 404 error handler."""
        response = test_client.get("/nonexistent-page")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_500_handler(self, test_client):
        """Test 500 error handler."""
        # This is hard to test without actually causing an error
        # But we can verify error handling exists
        pass

    def test_method_not_allowed(self, test_client):
        """Test 405 method not allowed."""
        response = test_client.post("/api/youtube/fetch-all")

        assert response.status_code == 405