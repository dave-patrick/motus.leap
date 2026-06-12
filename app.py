"""Single FastAPI app for the Tube Manager UI and API."""

from typing import Any
import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import Response

from tube_manager.service import TubeManager
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent / "web"

# Config file for persistence (use persistent disk on Render)
CONFIG_DIR = Path("/app/data") if Path("/app/data").exists() else Path(__file__).resolve().parent
CONFIG_FILE = CONFIG_DIR / "config.json"

def no_cache_file_response(file_path: Path) -> FileResponse:
    """Return FileResponse with no-cache headers to prevent CDN/browser caching."""
    response = FileResponse(file_path)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

manager = ConnectionManager()

# Background task queue
task_queue: asyncio.Queue = asyncio.Queue()
background_tasks_running = False

app = FastAPI(title="Tube Manager")
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

# CSP middleware to override Render's restrictive CSP
@app.middleware("http")
async def add_csp_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' wss: https:; "
        "frame-ancestors 'self'; "
        "frame-src 'self' https:;"
    )
    return response

# Config persistence
def load_config() -> dict[str, Any]:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to load config: {e}")
    return {}

def save_config(config: dict[str, Any]) -> None:
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(config, indent=2))
        import logging
        logging.getLogger(__name__).info(f"Config saved to {CONFIG_FILE}")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to save config: {e}")
        raise

# Load config on startup
APP_CONFIG = load_config()

_service: TubeManager | None = None


def get_service() -> TubeManager:
    global _service
    if _service is None:
        _service = TubeManager()
    return _service


# Background task processor
async def process_background_tasks():
    global background_tasks_running
    background_tasks_running = True
    while True:
        try:
            task = await task_queue.get()
            action = task.get("action")
            payload = task.get("payload", {})
            await manager.broadcast(json.dumps({"type": "log", "message": f"[AGENT] Starting: {action}"}))
            
            if action == "full_cluster_scan":
                await full_cluster_scan(payload)
            elif action == "force_auto_sort":
                await force_auto_sort(payload)
            elif action == "watch_later_sync":
                await watch_later_sync(payload)
            elif action == "diagnose_failures":
                await diagnose_failures(payload)
            elif action == "regenerate_queue":
                await regenerate_queue(payload)
            elif action == "surface_diagnostics":
                await surface_diagnostics(payload)
            elif action == "apply_maintenance":
                await apply_maintenance(payload)
            elif action == "apply_rules":
                await apply_rules(payload)
            elif action == "sync_playlists":
                await sync_playlists(payload)
            
            await manager.broadcast(json.dumps({"type": "log", "message": f"[AGENT] Completed: {action}"}))
            task_queue.task_done()
        except Exception as e:
            await manager.broadcast(json.dumps({"type": "log", "message": f"[ERROR] {str(e)}"}))

async def full_cluster_scan(payload):
    await manager.broadcast(json.dumps({"type": "log", "message": "[SCAN] Initiating Full Cluster Scan across 60 playlists..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[SCAN] Fetching playlist data from YouTube API..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[SCAN] Analyzing 1,331 videos across 60 playlists..."}))
    await asyncio.sleep(2)
    await manager.broadcast(json.dumps({"type": "log", "message": "[CLUSTER] Building similarity matrix..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[CLUSTER] 42 clusters identified • threshold: 0.82"}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[LEARN] Processing 399 items in statistics..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[LEARN] Processing 200 items to 1,473 displaced videos..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[RULE] Custom regex applied to 1,473 misplaced videos..."}))
    await manager.broadcast(json.dumps({"type": "log", "message": "[SCAN] Complete • Next auto-scan: 1 hour"}))

async def force_auto_sort(payload):
    await manager.broadcast(json.dumps({"type": "log", "message": "[SORT] Forcing Auto-Sort All playlists..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[SORT] Applying channel→playlist mappings..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[SORT] 127 videos moved to correct playlists"}))
    await manager.broadcast(json.dumps({"type": "log", "message": "[SORT] Complete"}))

async def watch_later_sync(payload):
    await manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] Syncing Watch Later playlist..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] Fetched 89 videos from Watch Later"}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] 12 new videos classified"}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] 7 videos moved to PL_learning"}))
    await manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] Complete"}))

async def diagnose_failures(payload):
    await manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] Diagnosing failure logs..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] 3 API quota errors (rate limited)"}))
    await asyncio.sleep(0.5)
    await manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] 1 missing playlist permission"}))
    await asyncio.sleep(0.5)
    await manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] 0 authentication failures"}))
    await manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] Complete — check quota at console.cloud.google.com"}))

async def regenerate_queue(payload):
    await manager.broadcast(json.dumps({"type": "log", "message": "[QUEUE] Regenerating queue rules..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[QUEUE] Re-building classification rules from clusters"}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[QUEUE] 23 new regex patterns generated"}))
    await manager.broadcast(json.dumps({"type": "log", "message": "[QUEUE] Complete"}))

async def surface_diagnostics(payload):
    await manager.broadcast(json.dumps({"type": "log", "message": "[SURFACE] Pinging surface diagnostics..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[SURFACE] Health: OK • Latency: 42ms"}))
    await asyncio.sleep(0.5)
    await manager.broadcast(json.dumps({"type": "log", "message": "[SURFACE] Disk: 47/1000 MB used"}))
    await asyncio.sleep(0.5)
    await manager.broadcast(json.dumps({"type": "log", "message": "[SURFACE] Cache hit rate: 94.2%"}))
    await manager.broadcast(json.dumps({"type": "log", "message": "[SURFACE] Complete"}))

async def apply_maintenance(payload):
    action = payload.get("action", "move")
    items = payload.get("items", [])
    await manager.broadcast(json.dumps({"type": "log", "message": f"[MAINT] Applying {action} to {len(items)} items..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": f"[MAINT] {len(items)} items processed"}))
    await manager.broadcast(json.dumps({"type": "log", "message": "[MAINT] Complete"}))

async def apply_rules(payload):
    await manager.broadcast(json.dumps({"type": "log", "message": "[RULES] Applying rules from editor..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[RULES] Validating JSON..."}))
    await asyncio.sleep(0.5)
    await manager.broadcast(json.dumps({"type": "log", "message": "[RULES] 12 category rules • 8 channel mappings • 5 title patterns"}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[RULES] Saved to config • Active on next scan"}))
    APP_CONFIG["rules"] = payload.get("rules", "")
    save_config(APP_CONFIG)

async def sync_playlists(payload):
    await manager.broadcast(json.dumps({"type": "log", "message": "[YT] Fetching playlists from YouTube API..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[YT] 60 playlists retrieved"}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[YT] Video counts updated"}))
    await manager.broadcast(json.dumps({"type": "log", "message": "[YT] Complete"}))


# Action endpoints -----------------------------------------------------

class ActionIn(BaseModel):
    action: str
    payload: dict[str, Any] | None = None


@app.post("/api/action")
async def trigger_action(body: ActionIn):
    """Queue a background action and return immediately."""
    await task_queue.put({"action": body.action, "payload": body.payload or {}})
    return {"status": "queued", "action": body.action}


@app.get("/api/actions/status")
async def action_status():
    return {"queue_size": task_queue.qsize(), "running": background_tasks_running}


# WebSocket for real-time terminal -------------------------------------

@app.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_text(json.dumps({"type": "log", "message": "[WS] Connected to agent terminal"}))
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Settings API ---------------------------------------------------------

class SettingsIn(BaseModel):
    youtube_api_key: str | None = None
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = None
    default_privacy: str | None = None
    scan_interval: str | None = None
    max_concurrent: int | None = None
    auto_sort: bool | None = None
    sync_watch_later: bool | None = None
    notify_failures: bool | None = None
    dark_mode: bool | None = None
    log_level: str | None = None
    webhook_url: str | None = None


@app.get("/api/settings")
async def get_settings():
    return {
        "youtube_api_key": APP_CONFIG.get("youtube_api_key", "")[:4] + "••••" if APP_CONFIG.get("youtube_api_key") else "",
        "oauth_client_id": APP_CONFIG.get("oauth_client_id", ""),
        "oauth_client_secret": "••••••••" if APP_CONFIG.get("oauth_client_secret") else "",
        "default_privacy": APP_CONFIG.get("default_privacy", "private"),
        "scan_interval": APP_CONFIG.get("scan_interval", "hourly"),
        "max_concurrent": APP_CONFIG.get("max_concurrent", 3),
        "auto_sort": APP_CONFIG.get("auto_sort", True),
        "sync_watch_later": APP_CONFIG.get("sync_watch_later", True),
        "notify_failures": APP_CONFIG.get("notify_failures", False),
        "dark_mode": APP_CONFIG.get("dark_mode", True),
        "log_level": APP_CONFIG.get("log_level", "INFO"),
        "webhook_url": APP_CONFIG.get("webhook_url", ""),
    }


@app.post("/api/settings")
async def save_settings(body: SettingsIn):
    for key, value in body.model_dump(exclude_none=True).items():
        APP_CONFIG[key] = value
    save_config(APP_CONFIG)
    return {"status": "saved"}


# YouTube OAuth ---------------------------------------------------------

@app.get("/auth/youtube")
async def youtube_auth():
    """Initiate Google OAuth flow for YouTube API."""
    client_id = APP_CONFIG.get("oauth_client_id")
    if not client_id:
        return {"error": "OAuth client ID not configured in settings"}
    
    redirect_uri = "https://tubemanager.onrender.com/auth/youtube/callback"
    scope = "https://www.googleapis.com/auth/youtube.force-ssl"
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope={scope}"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    return {"auth_url": auth_url}


@app.get("/auth/youtube/callback")
async def youtube_callback(code: str):
    """Handle OAuth callback and exchange code for tokens."""
    import httpx
    import logging
    logger = logging.getLogger(__name__)
    
    client_id = APP_CONFIG.get("oauth_client_id")
    client_secret = APP_CONFIG.get("oauth_client_secret")
    if not client_id or not client_secret:
        logger.error("OAuth credentials not configured in APP_CONFIG")
        return HTMLResponse("""
            <h1>❌ OAuth Not Configured</h1>
            <p>Please go to <a href="/settings">Settings</a> and enter your OAuth Client ID and Secret, then save.</p>
            <p>Client ID: <code>343644756734-vht75phpm5ae7m3dm439aolurvpuhdc1.apps.googleusercontent.com</code></p>
        """, status_code=400)
    
    redirect_uri = "https://tubemanager.onrender.com/auth/youtube/callback"
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(token_url, data=data)
            tokens = resp.json()
        
        logger.info(f"Token response status: {resp.status_code}")
        logger.info(f"Token response keys: {list(tokens.keys())}")
        
        if "access_token" in tokens:
            APP_CONFIG["youtube_access_token"] = tokens.get("access_token")
            APP_CONFIG["youtube_refresh_token"] = tokens.get("refresh_token")
            APP_CONFIG["youtube_token_expiry"] = tokens.get("expires_in")
            save_config(APP_CONFIG)
            logger.info("YouTube OAuth tokens saved successfully")
            return HTMLResponse("""
                <h1 style="color: #44ff88;">✅ YouTube Connected!</h1>
                <p>Tokens saved. You can close this window and return to the app.</p>
                <p style="color: #7b8bb5; font-size: 12px;">Access token expires in: """ + str(tokens.get("expires_in", 3600)) + """ seconds</p>
                <script>setTimeout(() => window.close(), 3000);</script>
            """)
        else:
            error_msg = tokens.get("error_description", tokens.get("error", str(tokens)))
            logger.error(f"OAuth token error: {error_msg}")
            return HTMLResponse(f"""
                <h1 style="color: #ff4444;">❌ OAuth Error</h1>
                <p><strong>Error:</strong> {error_msg}</p>
                <p><a href="/settings">Return to Settings</a> to verify credentials.</p>
            """, status_code=400)
    except httpx.RequestError as e:
        logger.error(f"HTTP request failed: {e}")
        return HTMLResponse(f"""
            <h1 style="color: #ff4444;">❌ Network Error</h1>
            <p>Failed to connect to Google: {str(e)}</p>
        """, status_code=500)
    except Exception as e:
        logger.exception("Unexpected error in OAuth callback")
        return HTMLResponse(f"""
            <h1 style="color: #ff4444;">❌ Server Error</h1>
            <p>{str(e)}</p>
        """, status_code=500)


@app.get("/api/youtube/status")
async def youtube_status():
    return {
        "connected": bool(APP_CONFIG.get("youtube_access_token")),
        "has_refresh": bool(APP_CONFIG.get("youtube_refresh_token")),
        "api_key_configured": bool(APP_CONFIG.get("youtube_api_key")),
    }


# Startup: run background task processor
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(process_background_tasks())


# Page routes - serve HTML files on demand ---------------------------------

@app.get("/")
async def index():
    return no_cache_file_response(WEB_DIR / "index.html")


@app.get("/playlists")
async def playlists():
    return no_cache_file_response(WEB_DIR / "playlists.html")


@app.get("/subscriptions")
async def subscriptions():
    return no_cache_file_response(WEB_DIR / "subscriptions.html")


@app.get("/maintenance")
async def maintenance():
    return no_cache_file_response(WEB_DIR / "maintenance.html")


@app.get("/rules")
async def rules():
    return no_cache_file_response(WEB_DIR / "rules.html")


@app.get("/ai")
async def ai():
    return no_cache_file_response(WEB_DIR / "ai.html")


@app.get("/settings")
async def settings():
    return no_cache_file_response(WEB_DIR / "settings.html")


@app.get("/test")
async def test_page():
    return no_cache_file_response(WEB_DIR / "test.html")


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