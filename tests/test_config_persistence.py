"""Regression: config persistence must round-trip OAuth tokens and mappings.

Previously to_dict_for_storage() stripped oauth.access_token/refresh_token,
so every config save (incl. the background worker's periodic save) wrote a
tokenless config to /app/data/config.json. On reload the app came back
disconnected from YouTube, and dependent state (e.g. channel_mappings reads)
could read empty. Tokens must persist to disk; they are redacted in API
responses separately.
"""
import pytest
from models.config import TubeManagerConfig, YouTubeOAuthConfig


def test_oauth_tokens_persist_through_storage_roundtrip():
    cfg = TubeManagerConfig(
        oauth=YouTubeOAuthConfig(
            client_id="cid",
            client_secret="csecret",
            access_token="ACCESS",
            refresh_token="REFRESH",
            token_expiry=12345,
        ),
        channel_mappings={"UCx": "PLy"},
    )
    d = cfg.to_dict_for_storage()
    assert d["oauth"]["access_token"] == "ACCESS"
    assert d["oauth"]["refresh_token"] == "REFRESH"
    assert d["oauth"]["client_secret"] == "csecret"
    assert d["oauth"]["token_expiry"] == 12345
    assert d["channel_mappings"] == {"UCx": "PLy"}


def test_from_dict_restores_oauth_tokens():
    raw = {
        "oauth": {
            "client_id": "cid",
            "client_secret": "csecret",
            "access_token": "ACCESS",
            "refresh_token": "REFRESH",
            "token_expiry": 12345,
        },
        "channel_mappings": {"UCx": "PLy"},
    }
    cfg = TubeManagerConfig.from_dict(raw)
    assert cfg.oauth.access_token == "ACCESS"
    assert cfg.oauth.refresh_token == "REFRESH"
    assert cfg.channel_mappings == {"UCx": "PLy"}
