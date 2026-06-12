"""Single FastAPI app for the Tube Manager UI and API."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from tube_manager.service import TubeManager
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent / "web"
INDEX_HTML = (WEB_DIR / "index.html").read_text(encoding="utf-8")
PLAYLISTS_HTML = (WEB_DIR / "playlists.html").read_text(encoding="utf-8")
SUBSCRIPTIONS_HTML = (WEB_DIR / "subscriptions.html").read_text(encoding="utf-8")
MAINTENANCE_HTML = (WEB_DIR / "maintenance.html").read_text(encoding="utf-8")
RULES_HTML = (WEB_DIR / "rules.html").read_text(encoding="utf-8")
AI_HTML = (WEB_DIR / "ai.html").read_text(encoding="utf-8")
SETTINGS_HTML = (WEB_DIR / "settings.html").read_text(encoding="utf-8")
app = FastAPI(title="Tube Manager")
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

_service: TubeManager | None = None


def get_service() -> TubeManager:
    global _service
    if _service is None:
        _service = TubeManager()
    return _service


# Pages ----------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return INDEX_HTML

@app.get("/playlists", response_class=HTMLResponse)
async def playlists() -> str:
    return PLAYLISTS_HTML

@app.get("/subscriptions", response_class=HTMLResponse)
async def subscriptions() -> str:
    return SUBSCRIPTIONS_HTML

@app.get("/maintenance", response_class=HTMLResponse)
async def maintenance() -> str:
    return MAINTENANCE_HTML

@app.get("/rules", response_class=HTMLResponse)
async def rules() -> str:
    return RULES_HTML

@app.get("/ai", response_class=HTMLResponse)
async def ai() -> str:
    return AI_HTML

@app.get("/settings", response_class=HTMLResponse)
async def settings() -> str:
    return SETTINGS_HTML


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/stats")
async def stats() -> dict[str, Any]:
    """Dashboard statistics endpoint for real-time UI updates."""
    service = get_service()
    tasks = service.list_tasks()
    pending = [t for t in tasks if t.get("status") == "pending"]
    running = [t for t in tasks if t.get("status") == "running"]
    completed = [t for t in tasks if t.get("status") == "completed"]
    failed = [t for t in tasks if t.get("status") == "failed"]
    return {
        "total_playlists": 60,
        "total_videos": 1331,
        "pending_actions": len(pending) + len(running),
        "still_items": len(running),
        "ai_learning": len(completed),
        "learning_rate": "2.225%",
        "learning_rates": "1922",
        "last_scan": "just now",
    }


@app.get("/api/playlists")
async def api_playlists() -> dict[str, Any]:
    """Playlists page data."""
    return {
        "playlists": [
            {"id": "PL_tech", "title": "Programming & Tech", "video_count": 347, "channel": "Multiple", "privacy": "private", "thumbnail": "https://picsum.photos/160/90?tech"},
            {"id": "PL_learning", "title": "Tutorials & Learning", "video_count": 289, "channel": "Multiple", "privacy": "private", "thumbnail": "https://picsum.photos/160/90?learn"},
            {"id": "PL_reviews", "title": "Reviews & Unboxings", "video_count": 156, "channel": "Multiple", "privacy": "private", "thumbnail": "https://picsum.photos/160/90?review"},
            {"id": "PL_live", "title": "Live Streams & Premieres", "video_count": 98, "channel": "Multiple", "privacy": "unlisted", "thumbnail": "https://picsum.photos/160/90?live"},
            {"id": "PL_music", "title": "Music & Audio", "video_count": 234, "channel": "Multiple", "privacy": "private", "thumbnail": "https://picsum.photos/160/90?music"},
            {"id": "PL_gaming", "title": "Gaming Content", "video_count": 187, "channel": "Multiple", "privacy": "private", "thumbnail": "https://picsum.photos/160/90?game"},
        ]
    }


@app.get("/api/subscriptions")
async def api_subscriptions() -> dict[str, Any]:
    """Subscriptions page data."""
    return {
        "channels": [
            {"id": "UC_x5XG1OV2P6uZZ5FSM9Ttw", "title": "Google Developers", "video_count": 1247, "subscribers": "2.1M", "thumbnail": "https://picsum.photos/32?gd"},
            {"id": "UC_latest", "title": "Fireship", "video_count": 342, "subscribers": "2.8M", "thumbnail": "https://picsum.photos/32?fs"},
            {"id": "UC_tech", "title": "TechLead", "video_count": 567, "subscribers": "1.2M", "thumbnail": "https://picsum.photos/32?tl"},
            {"id": "UC_code", "title": "Traversy Media", "video_count": 892, "subscribers": "2.0M", "thumbnail": "https://picsum.photos/32?tm"},
            {"id": "UC_ai", "title": "Two Minute Papers", "video_count": 456, "subscribers": "1.5M", "thumbnail": "https://picsum.photos/32?tmp"},
        ]
    }


@app.get("/api/maintenance")
async def api_maintenance() -> dict[str, Any]:
    """Maintenance queue page data."""
    return {
        "move_from_x_to_y": [
            {"id": "v1", "title": "Python Async Tutorial", "from_playlist": "PL_uncategorized", "to_playlist": "PL_learning", "suggested": "PL_learning", "thumbnail": "https://picsum.photos/32/24?1"},
            {"id": "v2", "title": "React 18 Features", "from_playlist": "PL_uncategorized", "to_playlist": "PL_tech", "suggested": "PL_tech", "thumbnail": "https://picsum.photos/32/24?2"},
        ],
        "duplicated_videos": [
            {"id": "v3", "title": "Docker Basics", "playlist_a": "PL_tech", "playlist_b": "PL_learning", "thumbnail": "https://picsum.photos/32/25?3"},
        ],
        "misplaced_videos": [
            {"id": "v4", "title": "Music Mix 2024", "current_playlist": "PL_tech", "suggested": "PL_music", "thumbnail": "https://picsum.photos/32/26?4"},
        ]
    }


@app.get("/api/mappings")
async def api_mappings() -> dict[str, Any]:
    """Rules & Mappings page data."""
    return {
        "mappings": [
            {"channel": "Google Developers", "channel_id": "UC_x5XG1OV2P6uZZ5FSM9Ttw", "playlist": "PL_tech", "thumbnail": "https://picsum.photos/24?gd"},
            {"channel": "Fireship", "channel_id": "UC_latest", "playlist": "PL_learning", "thumbnail": "https://picsum.photos/24?fs"},
            {"channel": "TechLead", "channel_id": "UC_tech", "playlist": "PL_tech", "thumbnail": "https://picsum.photos/24?tl"},
            {"channel": "Traversy Media", "channel_id": "UC_code", "playlist": "PL_learning", "thumbnail": "https://picsum.photos/24?tm"},
        ]
    }


# Tasks ------------------------------------------------------------------

class TaskIn(BaseModel):
    title: str
    task_type: str
    priority: str | None = None
    payload: dict[str, Any] | None = None


class TaskUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    payload: dict[str, Any] | None = None


@app.get("/tasks")
async def list_tasks(status: str | None = None) -> dict[str, Any]:
    service = get_service()
    return {"tasks": service.list_tasks(status=status)}


@app.post("/tasks", status_code=201)
async def add_task(body: TaskIn) -> dict[str, Any]:
    service = get_service()
    return service.add_task(
        title=body.title,
        task_type=body.task_type,
        priority=body.priority,
        payload=body.payload,
    )


@app.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict[str, Any]:
    service = get_service()
    task = service.get_task(task_id=task_id)
    if not task:
        return {"detail": "task not found"}
    return task


@app.post("/tasks/{task_id}")
async def update_task(task_id: str, body: TaskUpdate) -> dict[str, Any]:
    service = get_service()
    changes = {k: v for k, v in body.model_dump(exclude_none=True).items() if v is not None}
    try:
        return service.update_task(task_id=task_id, **changes)
    except KeyError as exc:
        return {"detail": str(exc)}


@app.delete("/tasks/{task_id}", status_code=204)
async def delete_task(task_id: str) -> None:
    service = get_service()
    try:
        service.remove_task(task_id=task_id)
    except KeyError as exc:
        return PlainTextResponse(str(exc), status_code=404)


@app.post("/tasks/{task_id}/run")
async def run_task(task_id: str) -> dict[str, Any]:
    service = get_service()
    try:
        return service.run_task(task_id=task_id)
    except KeyError as exc:
        return {"detail": str(exc)}


# Actions ----------------------------------------------------------------

class ActIn(BaseModel):
    action: str


@app.post("/youtube/run")
async def yt_run(body: ActIn) -> dict[str, Any]:
    return {"status": "queued", "action": body.action}


# YouTube wrappers (API-first) -------------------------------------------

@app.get("/youtube/channels")
async def yt_channels(mine: str = "false") -> dict[str, Any]:
    try:
        client = _get_youtube_client()
        if mine.lower() == "true":
            return client.list_mine_channels()
        return {"detail": "unsupported"}
    except Exception as exc:  # noqa: BLE001
        return {"detail": str(exc)}


@app.get("/youtube/playlists")
async def yt_playlists(mine: str = "false", max_results: int = 25, page_token: str | None = None) -> dict[str, Any]:
    try:
        client = _get_youtube_client()
        if mine.lower() == "true":
            return client.list_mine_playlists(max_results=max_results, page_token=page_token)
        return {"detail": "unsupported"}
    except Exception as exc:  # noqa: BLE001
        return {"detail": str(exc)}


@app.post("/youtube/actions/add")
async def yt_add(body: dict[str, Any]) -> dict[str, Any]:
    client = _get_youtube_client()
    return client.add_to_playlist(
        playlist_id=str(body.get("playlist_id", "")),
        video_id=str(body.get("video_id", "")),
        title=body.get("title"),
        description=str(body.get("description", "")),
    )


@app.post("/youtube/actions/remove")
async def yt_remove(body: dict[str, Any]) -> dict[str, Any]:
    client = _get_youtube_client()
    return client.remove_from_playlist(playlist_item_id=str(body.get("playlist_item_id", "")))


@app.post("/youtube/actions/create-playlist")
async def yt_create_playlist(body: dict[str, Any]) -> dict[str, Any]:
    client = _get_youtube_client()
    return client.create_playlist(
        title=str(body.get("title", "")),
        description=str(body.get("description", "")),
        privacy_status=str(body.get("privacy_status", "private")),
    )


def _get_youtube_client() -> Any:
    from tube_manager.google import YouTubeClient

    return YouTubeClient()
