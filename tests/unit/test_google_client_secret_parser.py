"""Unit tests for app.parse_google_client_secret_json.

Pure helper: extracts (client_id, client_secret) from a Google OAuth
client_secret.json (web or installed shape). Loaded in isolation to avoid
dragging in the full FastAPI app.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_parser():
    app_path = Path(__file__).resolve().parents[2] / "app.py"
    spec = importlib.util.spec_from_file_location("motus_leap_app_iso", app_path)
    assert spec is not None and spec.loader is not None, "failed to load app.py"
    mod = importlib.util.module_from_spec(spec)
    # app.py has heavy imports; stub only what's strictly top-level & missing.
    for name in ("core.limiter",):
        sys.modules.setdefault(name, type(sys)(name))
    spec.loader.exec_module(mod)
    return mod.parse_google_client_secret_json


def test_web_shape():
    p = _load_parser()
    raw = json.dumps({"web": {"client_id": "cid.apps.googleusercontent.com",
                              "client_secret": "sec123"}})
    assert p(raw) == ("cid.apps.googleusercontent.com", "sec123")


def test_installed_shape():
    p = _load_parser()
    raw = json.dumps({"installed": {"client_id": "cid2", "client_secret": "sec2"}})
    assert p(raw) == ("cid2", "sec2")


def test_strips_whitespace():
    p = _load_parser()
    raw = json.dumps({"web": {"client_id": "  cid  ", "client_secret": "  sec  "}})
    assert p(raw) == ("cid", "sec")


def test_missing_creds_returns_empty():
    p = _load_parser()
    # client_id present but secret absent -> returns id, empty secret (caller
    # treats partial as invalid; the helper surfaces what it found).
    assert p(json.dumps({"web": {"client_id": "cid"}})) == ("cid", "")
    assert p(json.dumps({"foo": "bar"})) == ("", "")
    # fully empty object
    assert p(json.dumps({})) == ("", "")


def test_invalid_json_returns_empty():
    p = _load_parser()
    assert p("{ not json") == ("", "")
    assert p("") == ("", "")
