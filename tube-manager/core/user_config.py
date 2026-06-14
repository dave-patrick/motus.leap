"""Multi-user configuration extensions for Tube Manager."""

from typing import Dict, List, Optional
from models.config import TubeManagerConfig
import json
from pathlib import Path


class UserConfig:
    """Per-user configuration wrapper."""

    def __init__(self, user_id: str, config_path: Optional[Path] = None):
        self.user_id = user_id
        self.config_path = config_path or Path(f"/app/data/users/{user_id}/config.json")

    def load(self) -> TubeManagerConfig:
        """Load user's configuration."""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                return TubeManagerConfig.from_dict(data)
            return TubeManagerConfig()
        except Exception:
            return TubeManagerConfig()

    def save(self, config: TubeManagerConfig) -> None:
        """Save user's configuration."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(config.to_dict(), f, indent=2)


class UserOperationsManager:
    """Track operations per user."""

    def __init__(self):
        self._operations: Dict[str, List[Dict]] = {}

    def add_operation(self, user_id: str, operation: Dict) -> None:
        """Add operation for user."""
        if user_id not in self._operations:
            self._operations[user_id] = []
        self._operations[user_id].append(operation)

    def get_user_operations(self, user_id: str) -> List[Dict]:
        """Get all operations for user."""
        return self._operations.get(user_id, [])

    def get_operation(self, user_id: str, operation_id: str) -> Optional[Dict]:
        """Get specific operation for user."""
        operations = self._operations.get(user_id, [])
        for op in operations:
            if op.get('operation_id') == operation_id:
                return op
        return None


# Global user operations manager
user_operations = UserOperationsManager()