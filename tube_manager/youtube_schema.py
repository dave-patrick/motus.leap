"""YouTube-specific task schema and validation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class Video(BaseModel):
    video_id: str
    title: str
    channel_id: str
    channel_title: str | None = None
    description: str | None = None
    thumbnails: dict[str, Any] | None = None
    duration_seconds: int | None = None
    published_at: str | None = None


class Playlist(BaseModel):
    playlist_id: str
    title: str
    description: str | None = None
    item_count: int | None = None
    videos: list[Video] = Field(default_factory=list)


class SavedVideo(BaseModel):
    video_id: str
    title: str
    channel_id: str
    added_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = "saved"
    notes: str | None = None


class YouTubeTask(BaseModel):
    task_id: str
    kind: str = "youtube"
    action: str = Field(..., description="sync|playlist|watchlater")
    target: str | None = Field(None, description="playlist_id or watch-later token")
    result: dict[str, Any] | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

