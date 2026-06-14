"""Render compatibility entrypoint.

Render runs ``uvicorn app:app`` from the project root. The maintained FastAPI
application lives at ``tube-manager/app.py``. This module re-exports the
``app`` instance defined there so that the deployment command resolves to the
real application without duplicating code.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent
_APP_DIR = _REPO_ROOT / "tube-manager"
_APP_FILE = _APP_DIR / "app.py"

_APP_DIR_STR = str(_APP_DIR)
if _APP_DIR_STR not in sys.path:
    sys.path.insert(0, _APP_DIR_STR)

if not _APP_FILE.exists():
    raise RuntimeError(f"Tube Manager application not found at {_APP_FILE}")

_spec = importlib.util.spec_from_file_location(
    "tube_manager_app", _APP_FILE
)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Could not load module spec for {_APP_FILE}")

_module = importlib.util.module_from_spec(_spec)
sys.modules["tube_manager_app"] = _module
_spec.loader.exec_module(_module)

app = _module.app

__all__ = ["app"]
