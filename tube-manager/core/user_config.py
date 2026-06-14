"""Multi-user configuration extensions for Tube Manager."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class UserConfig:
    """Per-user configuration wrapper."""

    def __init__(self, user_id: str, config_path: Optional[Path] = None):
        self.user_id = user_id
        if config_path is None:
            config_path = Path("/app/data") / "users" / user_id / "config.json"
        self.config_path = config_path

    def load(self) -> Dict[str, Any]:
        """Load user configuration."""
        try:
            if self.config_path.exists():
                return json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            logging.getLogger(__name__).warning("Failed to load user config: %s", exc)
        return {}

    def save(self, config: Dict[str, Any]) -> None:
        """Persist user configuration."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(config, indent=2, sort_keys=True), encoding="utf-8"
        )


class UserOperationsManager:
    """Track operations per user."""

    def __init__(self):
        self._operations: Dict[str, List[Dict[str, Any]]] = {}

    def add_operation(self, user_id: str, operation: Dict[str, Any]) -> None:
        self._operations.setdefault(user_id, []).append(operation)

    def get_user_operations(self, user_id: str) -> List[Dict[str, Any]]:
        return list(self._operations.get(user_id, []))

    def get_operation(self, user_id: str, operation_id: str) -> Optional[Dict[str, Any]]:
        for operation in self.get_user_operations(user_id):
            if operation.get("operation_id") == operation_id:
                return operation
        return None


user_operations = UserOperationsManager()


def prepare_user_dirs(user: Dict[str, Any]) -> None:
    """Create any per-user runtime directories on disk."""
    user_id = user.get("id") or user.get("username")
    if not user_id:
        return
    base = Path("/app/data") / "users" / str(user_id)
    base.mkdir(parents=True, exist_ok=True)
    for child in ("exports", "imports", "logs"):
        (base / child).mkdir(exist_ok=True)
