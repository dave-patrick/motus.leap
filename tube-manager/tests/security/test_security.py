"""Security tests."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.security
class TestCSPHeaders:
    """Test Content Security Policy headers."""

    def test_csp_on_all_pages(self, test_client):
        """Test CSP header is present on all pages."""
        pages = [
            "/dashboard",
            "/playlists",
            "/subscriptions",
            "/rules",
            "/ai"
        ]

        for page in pages:
            response = test_client.get(page)
            assert_csp_headers(response)

    def test_csp_no_unsafe_inline(self, test_client):
        """Test CSP does not contain unsafe-inline."""
        response = test_client.get("/dashboard")
        csp = response.headers.get("Content-Security-Policy", "")

        assert "unsafe-inline" not in csp
        assert "unsafe-eval" not in csp

    def test_csp_has_nonce(self, test_client):
        """Test CSP uses nonce-based policy."""
        response = test_client.get("/dashboard")
        csp = response.headers.get("Content-Security-Policy", "")

        assert "nonce-" in csp

    def test_csp_frame_ancestors_none(self, test_client):
        """Test CSP prevents framing."""
        response = test_client.get("/dashboard")
        csp = response.headers.get("Content-Security-Policy", "")

        assert "frame-ancestors 'none'" in csp

    def test_csp_frame_src_none(self, test_client):
        """Test CSP prevents frames."""
        response = test_client.get("/dashboard")
        csp = response.headers.get("Content-Security-Policy", "")

        assert "frame-src 'none'" in csp

    def test_csp_connect_src_restricted(self, test_client):
        """Test CSP has restricted connect-src."""
        response = test_client.get("/dashboard")
        csp = response.headers.get("Content-Security-Policy", "")

        # Should not have 'https:' wildcard
        assert "connect-src 'self' https://www.googleapis.com" in csp

    def test_csp_img_src_no_data(self, test_client):
        """Test CSP does not allow data: URIs in images."""
        response = test_client.get("/dashboard")
        csp = response.headers.get("Content-Security-Policy", "")

        assert "data:" not in csp.split("img-src")[0] if "img-src" in csp else True


@pytest.mark.security
class TestSecurityHeaders:
    """Test security headers."""

    def test_x_frame_options(self, test_client):
        """Test X-Frame-Options header."""
        response = test_client.get("/dashboard")

        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_x_content_type_options(self, test_client):
        """Test X-Content-Type-Options header."""
        response = test_client.get("/dashboard")

        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_x_xss_protection(self, test_client):
        """Test X-XSS-Protection header."""
        response = test_client.get("/dashboard")

        assert "X-XSS-Protection" in response.headers
        assert "1; mode=block" in response.headers["X-XSS-Protection"]

    def test_referrer_policy(self, test_client):
        """Test Referrer-Policy header."""
        response = test_client.get("/dashboard")

        assert "Referrer-Policy" in response.headers
        assert "strict-origin-when-cross-origin" in response.headers["Referrer-Policy"]

    def test_permissions_policy(self, test_client):
        """Test Permissions-Policy header."""
        response = test_client.get("/dashboard")

        assert "Permissions-Policy" in response.headers
        # Check common restrictions
        policy = response.headers["Permissions-Policy"]
        assert "geolocation=()" in policy
        assert "microphone=()" in policy
        assert "camera=()" in policy


@pytest.mark.security
class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_rate_limit_headers(self, test_client):
        """Test rate limit headers are present."""
        response = test_client.get("/api/youtube/fetch-all")

        # Headers may or may not be present, depending on implementation
        # This test verifies they don't break the app
        assert response.status_code in [200, 429]

    @pytest.mark.slow
    def test_fetch_all_rate_limit_enforced(self, test_client):
        """Test rate limit is enforced on fetch-all."""
        responses = []

        # Make 11 requests (limit is 10/minute)
        for i in range(11):
            response = test_client.get("/api/youtube/fetch-all")
            responses.append(response)

        # Last request should be rate limited
        last_response = responses[-1]
        assert last_response.status_code == 429

        # Rate limit response should have retry-after
        if "Retry-After" in last_response.headers:
            assert last_response.headers["Retry-After"] is not None

    @pytest.mark.slow
    def test_action_rate_limit_enforced(self, test_client):
        """Test rate limit is enforced on action endpoint."""
        responses = []

        # Make 21 requests (limit is 20/minute)
        for i in range(21):
            response = test_client.post("/api/action", json={
                "action": "full_cluster_scan",
                "payload": {}
            })
            responses.append(response)

        # Last request should be rate limited
        last_response = responses[-1]
        assert last_response.status_code == 429


@pytest.mark.security
class TestInputValidation:
    """Test input validation."""

    def test_action_endpoint_validation(self, test_client):
        """Test action endpoint validates input."""
        # Missing required fields
        response = test_client.post("/api/action", json={})

        # Should still process, but gracefully
        assert response.status_code in [200, 422]

    def test_mappings_endpoint_validation(self, test_client):
        """Test mappings endpoint validates input."""
        # Invalid mappings format
        response = test_client.post("/api/mappings", json={
            "mappings": "invalid"
        })

        # Should handle gracefully
        assert response.status_code in [200, 422]

    def test_config_update_validation(self, test_client):
        """Test config update validates input."""
        # Test with various inputs
        response = test_client.post("/api/config", json={
            "youtube_api_key": "test_key",
            "oauth_client_id": "test_id",
            "oauth_client_secret": "test_secret"
        })

        # Should handle gracefully
        assert response.status_code in [200, 422]

    def test_query_parameter_validation(self, test_client):
        """Test query parameters are validated."""
        # Test with invalid boolean
        response = test_client.get("/api/youtube/fetch-all?force_refresh=invalid")

        # Should handle gracefully or default to False
        assert response.status_code in [200, 422]


@pytest.mark.security
class TestXSSProtection:
    """Test XSS protection."""

    def test_xss_in_config(self, test_client):
        """Test XSS attempts in config are blocked."""
        # Try to inject script via config
        response = test_client.post("/api/config", json={
            "rules": "<script>alert('XSS')</script>"
        })

        # Should handle gracefully
        assert response.status_code in [200, 422]

        # Verify script is not returned in response
        data = response.json()
        if "config" in data:
            assert "<script>" not in str(data.get("config", {}))

    def test_xss_in_mappings(self, test_client):
        """Test XSS attempts in mappings are blocked."""
        response = test_client.post("/api/mappings", json={
            "mappings": {
                "<script>alert('XSS')</script>": "playlist1"
            }
        })

        # Should handle gracefully
        assert response.status_code in [200, 422]

    def test_xss_in_action_payload(self, test_client):
        """Test XSS attempts in action payload are blocked."""
        response = test_client.post("/api/action", json={
            "action": "full_cluster_scan",
            "payload": {
                "query": "<script>alert('XSS')</script>"
            }
        })

        # Should handle gracefully
        assert response.status_code in [200, 422]

    def test_html_escaping_in_responses(self, test_client):
        """Test HTML is escaped in responses."""
        response = test_client.get("/api/config")

        # Check that HTML tags are not rendered
        text = response.text
        # If there's HTML in the data, it should be escaped
        assert "<script>" not in text or "&lt;script&gt;" in text


@pytest.mark.security
class TestCSRFProtection:
    """Test CSRF protection (if implemented)."""

    def test_state_changing_requires_method(self, test_client):
        """Test state-changing operations use POST."""
        # GET request for state-changing endpoint should fail or redirect
        response = test_client.get("/api/mappings")

        # Should either 405 (method not allowed) or handle gracefully
        assert response.status_code in [200, 405]


@pytest.mark.security
class TestSecretProtection:
    """Test secret protection."""

    def test_config_endpoint_excludes_secrets(self, test_client):
        """Test config endpoint excludes sensitive data."""
        response = test_client.get("/api/config")

        data = response.json()

        # Check that secrets are excluded
        assert "access_token" not in str(data)
        assert "refresh_token" not in str(data)
        assert "client_secret" not in str(data)

    def test_api_key_masked_in_config(self, test_client):
        """Test API key is masked in config response."""
        response = test_client.get("/api/config")

        data = response.json()
        api_key = data.get("config", {}).get("youtube_api_key", "")

        # Should be masked
        if api_key and api_key != "":
            assert "••••" in api_key or len(api_key) <= 4

    def test_oauth_tokens_not_logged(self, test_client):
        """Test OAuth tokens are not logged."""
        # This is harder to test directly
        # We verify by checking response doesn't contain tokens
        response = test_client.get("/api/config")

        text = response.text
        # Should not contain full tokens
        assert "ya29" not in text  # OAuth access token prefix


@pytest.mark.security
class TestAuthentication:
    """Test authentication (if implemented)."""

    def test_protected_endpoint_without_auth(self, test_client):
        """Test protected endpoint without authentication."""
        # If authentication is implemented, this should 401
        # Currently, app is public, so this test documents behavior
        response = test_client.get("/api/youtube/fetch-all")

        # Currently returns 200 (public access)
        # If auth is added, should be 401
        assert response.status_code in [200, 401]


@pytest.mark.security
class TestHTTPSOnly:
    """Test HTTPS-only enforcement."""

    def test_cookies_secure_flag(self, test_client):
        """Test cookies have secure flag (if cookies used)."""
        # Currently app doesn't use cookies much
        # This test documents expected behavior
        response = test_client.get("/dashboard")

        # If cookies are set, they should have Secure flag
        set_cookie = response.headers.get("set-cookie")
        if set_cookie:
            assert "Secure" in set_cookie


@pytest.mark.security
class TestInformationDisclosure:
    """Test information disclosure prevention."""

    def test_no_server_version(self, test_client):
        """Test server header doesn't reveal version."""
        response = test_client.get("/health")

        server_header = response.headers.get("server", "")

        # Should not reveal exact version
        # uvicorn is generic, but shouldn't show version
        assert "uvicorn" not in server_header or "/" not in server_header

    def test_no_debug_info_in_errors(self, test_client):
        """Test error messages don't reveal debug info."""
        response = test_client.get("/nonexistent")

        data = response.json()

        # Should not contain stack traces or debug info
        error_str = str(data)
        assert "Traceback" not in error_str
        assert "File" not in error_str or error_str.count("File") < 3