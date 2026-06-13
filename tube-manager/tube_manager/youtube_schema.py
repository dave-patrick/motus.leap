"""YouTube-specific task schema and validation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class Video(BaseModel):
    video_id: str
    title: str
    channel_id: str
    channel_title: Optional[str] = None
    description: Optional[str] = None
    thumbnails: Optional[dict[str, Any]] = None
    duration_seconds: Optional[int] = None
    published_at: Optional[str] = None


class Playlist(BaseModel):
    playlist_id: str
    title: str
    description: Optional[str] = None
    item_count: Optional[int] = None
    videos: list[Video] = Field(default_factory=list)


class SavedVideo(BaseModel):
    video_id: str
    title: str
    channel_id: str
    added_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "saved"
    notes: Optional[str] = None


class YouTubeTask(BaseModel):
    task_id: str
    kind: str = "youtube"
    action: str = Field(..., description="sync|playlist|watchlater")
    target: Optional[str] = Field(None, description="playlist_id or watch-later token")
    result: Optional[dict[str, Any]] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
