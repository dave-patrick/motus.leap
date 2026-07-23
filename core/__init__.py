"""Core package initialization."""

try:
    from .actions import add_video_to_playlist, remove_video_from_playlist, list_videos_in_playlist, move_video, get_browser, get_all_playlists, create_playlist
except Exception:
    pass

try:
    from .task_manager import task_manager
except Exception:
    pass

try:
    from .logger import setup_logging
except Exception:
    pass

try:
    from .config_manager import ConfigManager
except Exception:
    pass

__all__ = [
    "add_video_to_playlist",
    "remove_video_from_playlist",
    "list_videos_in_playlist",
    "move_video",
    "get_browser",
    "get_all_playlists",
    "create_playlist",
    "task_manager",
    "setup_logging",
    "ConfigManager",
]
