"""Integration regression test for live OAuth credential resolution.

Bug: api.auth OAuth endpoints read GOOGLE_OAUTH_CLIENT_ID/SECRET module-level
constants that are captured at *import time*. A secret saved via the Settings
UI updates config_manager.config.oauth (and config.json on disk) but never the
frozen constant, so Google kept rejecting the secret. These tests assert the
/google and /youtube init endpoints resolve credentials from the LIVE config.
"""
import pytest
from pydantic import SecretStr

from tests.conftest import assert_response_success


@pytest.mark.integration
class TestOAuthCredentialResolution:
    def test_google_init_uses_live_config_not_frozen_constant(self, test_client):
        """Saving creds in config_manager must surface in the OAuth start URL."""
        from app import config_manager

        # Simulate a Settings UI save: only the live config has creds;
        # no env vars, no disk config.json oauth block.
        config_manager.config.oauth.client_id = "live_cid_abc.apps.googleusercontent.com"
        config_manager.config.oauth.client_secret = SecretStr("live_secret_xyz")

        resp = test_client.get("/api/auth/google?format=json")
        assert_response_success(resp, 200)
        data = resp.json()
        assert "auth_url" in data
        assert "live_cid_abc.apps.googleusercontent.com" in data["auth_url"]

    def test_youtube_init_uses_live_config(self, test_client):
        from app import config_manager

        config_manager.config.oauth.client_id = "yt_cid_def.apps.googleusercontent.com"
        config_manager.config.oauth.client_secret = SecretStr("yt_secret_uvw")

        resp = test_client.get("/api/auth/youtube")
        assert_response_success(resp, 200)
        data = resp.json()
        assert "auth_url" in data
        assert "yt_cid_def.apps.googleusercontent.com" in data["auth_url"]
        # YouTube scope must be requested
        assert "youtube" in data["auth_url"]

