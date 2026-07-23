"""Unit tests for api.auth.resolve_oauth_credentials.

The resolver is pure (env dict + optional config dir), so we load it via
importlib without dragging in fastapi/PyJWT — only its credential logic is
under test.
"""
import importlib.util
import json
import sys
import textwrap
from pathlib import Path

import pytest


def _load_resolver(tmp_path: Path):
    """Import resolve_oauth_credentials from api/auth.py in isolation."""
    auth_path = Path(__file__).resolve().parents[2] / "api" / "auth.py"
    spec = importlib.util.spec_from_file_location("motus_leap_auth_iso", auth_path)
    assert spec is not None and spec.loader is not None, "failed to load api/auth.py"
    mod = importlib.util.module_from_spec(spec)
    # Stub the heavy module-level deps the file imports at top level.
    sys.modules.setdefault("core.limiter", type(sys)("core.limiter"))
    # PyJWT / httpx / fastapi / pydantic are real deps in .venv; let them load.
    spec.loader.exec_module(mod)
    return mod.resolve_oauth_credentials


def _write_config(tmp_path: Path, oauth: dict) -> Path:
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"oauth": oauth}))
    return cfg


def test_youtube_alias_resolves(tmp_path):
    """Render injects YOUTUBE_*; resolver must honour the alias."""
    r = _load_resolver(tmp_path)
    cid, sec = r(
        {"YOUTUBE_CLIENT_ID": "cid-Y", "YOUTUBE_CLIENT_SECRET": "csec-Y"},
        config_dir=tmp_path,
    )
    assert (cid, sec) == ("cid-Y", "csec-Y")


def test_google_name_takes_precedence_over_youtube_alias(tmp_path):
    r = _load_resolver(tmp_path)
    cid, sec = r(
        {
            "GOOGLE_OAUTH_CLIENT_ID": "cid-G",
            "GOOGLE_OAUTH_CLIENT_SECRET": "csec-G",
            "YOUTUBE_CLIENT_ID": "cid-Y",
            "YOUTUBE_CLIENT_SECRET": "csec-Y",
        },
        config_dir=tmp_path,
    )
    assert (cid, sec) == ("cid-G", "csec-G")


def test_config_fallback_used_when_env_absent(tmp_path):
    r = _load_resolver(tmp_path)
    _write_config(tmp_path, {"client_id": "cid-C", "client_secret": "  csec-C  "})
    # No env vars -> config.json, with surrounding whitespace stripped.
    cid, sec = r({}, config_dir=tmp_path)
    assert cid == "cid-C"
    assert sec == "csec-C"


def test_env_overrides_config(tmp_path):
    r = _load_resolver(tmp_path)
    _write_config(tmp_path, {"client_id": "cid-C", "client_secret": "csec-C"})
    cid, sec = r(
        {"GOOGLE_OAUTH_CLIENT_ID": "cid-E", "GOOGLE_OAUTH_CLIENT_SECRET": "csec-E"},
        config_dir=tmp_path,
    )
    assert (cid, sec) == ("cid-E", "csec-E")


def test_missing_config_and_env_returns_empty(tmp_path):
    r = _load_resolver(tmp_path)
    # No config.json written, no env -> empty strings, no exception.
    cid, sec = r({}, config_dir=tmp_path)
    assert cid == ""
    assert sec == ""
