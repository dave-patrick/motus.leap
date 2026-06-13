1|"""YouTube client integration stubs with playlist/video helpers."""
2|from __future__ import annotations
3|
4|import os
5|from typing import Any
6|
7|
8|class YouTubeClient:
9|    def __init__(self, api_key: Optional[str ] = None):
10|        self.api_key = api_key or os.getenv("YOUTUBE_API_KEY", "")
11|
12|    def get_playlist(self, playlist_id: str) -> dict[str, Any]:
13|        raise NotImplementedError("youtube client not implemented")
14|
15|    def list_videos(self, playlist_id: str) -> list[dict[str, Any]]:
16|        raise NotImplementedError("youtube client not implemented")
17|
18|    def get_video(self, video_id: str) -> dict[str, Any]:
19|        raise NotImplementedError("youtube client not implemented")
20|
21|    def watch_later(self) -> dict[str, Any]:
22|        raise NotImplementedError("youtube watch-later not implemented")
23|