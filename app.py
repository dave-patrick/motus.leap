"""Render entrypoint — re-exports the real Tube Manager app.

Render's Dashboard RootDir is set to the repo root, so uvicorn loads THIS file.
It loads the maintained application from tube-manager/app.py via importlib
(to avoid a circular import since this file is also named app.py).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Locate the maintained app module
_APP_DIR = Path(__file__).resolve().parent / "tube-manager"
_APP_FILE = _APP_DIR / "app.py"

if not _APP_FILE.is_file():
    raise FileNotFoundError(f"Maintained app not found at {_APP_FILE}")

# Inject the app directory so internal relative imports resolve
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

# Load the module under a unique name to avoid shadowing this file
_spec = importlib.util.spec_from_file_location("_tube_manager_app", _APP_FILE)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Cannot load module from {_APP_FILE}")

_mod = importlib.util.module_from_spec(_spec)
sys.modules["_tube_manager_app"] = _mod
_spec.loader.exec_module(_mod)

# Expose the FastAPI instance
app = _mod.app

__all__ = ["app"]
