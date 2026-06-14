"""Legacy app — DEPRECATED. Replaced by tube-manager/app.py.

This file is kept only because Render Dashboard may reference it.
It delegates to the maintained application via importlib.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_APP_DIR = Path(__file__).resolve().parent / "tube-manager"
_APP_FILE = _APP_DIR / "app.py"

if not _APP_FILE.is_file():
    raise FileNotFoundError(f"Maintained app not found at {_APP_FILE}")

if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

_spec = importlib.util.spec_from_file_location("_tube_manager_app", _APP_FILE)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Cannot load module from {_APP_FILE}")

_mod = importlib.util.module_from_spec(_spec)
sys.modules["_tube_manager_app"] = _mod
_spec.loader.exec_module(_mod)

app = _mod.app

__all__ = ["app"]
