"""motus.leap Main Application."""
# Deploy v2.1

import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env

import asyncio
from datetime import datetime
import json
import logging
import hashlib
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends, Cookie
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aiofiles

# Auth dependency
from api.auth import get_current_user, verify_origin, create_default_admin # Import create_default_admin

# Auth dependency for page routes (redirects to /auth if not authenticated)
async def require_auth(request: Request, response: Response, token: str = Cookie(default=None)) -> dict[str, Any]:
    """Require authentication for page routes. Redirects to /auth if not authenticated."""
    from api.auth import decode_access_token, get_user_by_username

    if not token:
        log.warning("Auth: No token found. Redirecting to /auth.")
        return RedirectResponse(url="/auth?reason=unauthenticated", status_code=302)

    try:
        payload = decode_access_token(token)
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Could not validate credentials")
        from api.auth import get_users_db
        users_db = await get_users_db()
        user = users_db.get(username)
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        request.state.user = user
        log.debug(f"Auth: User {user['username']} authenticated.")
        return user
    except HTTPException as e:
        log.warning(f"Auth: Token validation failed: {e.detail}. Clearing token and redirecting to /auth.")
        response.delete_cookie(key="token", path="/")
        return RedirectResponse(url=f"/auth?reason={e.detail.lower().replace(' ', '')}", status_code=302)
    except Exception as e:
        log.error(f"Auth: Unexpected error during authentication: {e}. Clearing token and redirecting to /auth.")
        response.delete_cookie(key="token", path="/") # Clear invalid token
        return RedirectResponse(url="/auth?reason=error", status_code=302)

# Rate limiting


# Import external limiter
from core.limiter import limiter
from slowapi.errors import RateLimitExceeded # Add RateLimitExceeded import

# Import routers
from api.bulk_operations import router as bulk_router
from api.auth import router as auth_router



# Core imports
from core.http_client import shutdown_http_client
from core.logger import setup_logging
from core.config_manager import ConfigManager
from models.config import TubeManagerConfig
from models.task import Task, TaskStatus, TaskPriority

# Service imports
from services.youtube_service import YouTubeService

# Setup logging
log = logging.getLogger(__name__)

# Paths
WEB_DIR = Path(__file__).resolve().parent / "web"
CONFIG_DIR = Path("/app/data") if Path("/app/data").exists() else Path(__file__).resolve().parent

# Initialize managers
config_manager = ConfigManager(CONFIG_DIR / "config.json")
youtube_service: Optional[YouTubeService] = None

# Initialize app
app = FastAPI(
    title="motus.leap",
    description="YouTube Playlist Management System",
    version="2.0.0"
)

# Add CORS middleware
# Get allowed origins from environment or use defaults
_render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://tubemanager.onrender.com")
_extra_origins = os.environ.get("EXTRA_ALLOWED_ORIGINS", "").split(",") if os.environ.get("EXTRA_ALLOWED_ORIGINS") else []

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        _render_url,
        "https://motus-leap.onrender.com",
        "http://localhost:8000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:3000",
        "http://localhost",
    ] + [o.strip() for o in _extra_origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store in app state for routers


# Register routers
app.include_router(bulk_router, tags=["bulk"])
app.include_router(auth_router, tags=["auth"])


async def no_cache_file_response(file_path: Path) -> Response:
    """Return HTML response with strong no-cache headers to prevent CDN/browser caching."""
    try:
        async with aiofiles.open(file_path, mode='r', encoding="utf-8") as f:
            content = await f.read()

        # Hard-bust cache by inserting a fresh deploy query on all static assets
        deploy_tag = str(int(__import__('time').time()))
        content = content.replace(
            '<title>motus.leap</title>',
            f'<title>motus.leap</title>\n    <meta name="deploy-time" content="{deploy_tag}">'
        )
        content = content.replace('?v=7', f'?v={deploy_tag}')
        return Response(
            content=content,
            media_type="text/html; charset=utf-8",
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
                "Surrogate-Control": "no-store",
            }
        )
    except Exception as e:
        log.error(f"Failed to read file {file_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load page: {str(e)}")


# WebSocket connection manager
class ConnectionManager:
    """Manages WebSocket connections with user scoping."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._user_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str = None):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        if user_id:
            self._user_connections.setdefault(user_id, []).append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str = None):
        """Remove a WebSocket connection."""
        try:
            self.active_connections.remove(websocket)
        except ValueError:
            pass
        if user_id and user_id in self._user_connections:
            try:
                self._user_connections[user_id].remove(websocket)
            except ValueError:
                pass
            if not self._user_connections[user_id]:
                self._user_connections.pop(user_id, None)

    async def send_to_user(self, user_id: str, message: str):
        """Send message to all connections for a specific user."""
        connections = self._user_connections.get(user_id, [])
        for connection in connections:
            try:
                await connection.send_text(message)
            except Exception:
                pass

    async def broadcast(self, message: str, user_id: str = None):
        """Broadcast a message, optionally only to a specific user."""
        if user_id:
            await self.send_to_user(user_id, message)
        else:
            failed = []
            for connection in self.active_connections:
                try:
                    await connection.send_text(message)
                except Exception:
                    failed.append(connection)
            for connection in failed:
                self.disconnect(connection)


manager = ConnectionManager()


# Background task queue
task_queue: asyncio.Queue = asyncio.Queue()
background_tasks_running = False
current_task_name: Optional[str] = None
worker: Optional[Any] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global youtube_service, worker

    # Set up file logging
    log_dir = Path("/app/data")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "tube_manager.log"
    setup_logging(log_file=log_file)

    config = await config_manager.load()
    youtube_service = YouTubeService(config)
    await create_default_admin()
    
    # Store in app state for routers
    app.state.config = config_manager.config
    app.state.config_manager = config_manager

    # Start background task processor
    from services.background_worker import BackgroundWorker
    worker = BackgroundWorker(youtube_service, manager, config_manager, task_queue)
    asyncio.create_task(worker.process_background_tasks())
    
    # Start nightly auto-apply mappings job if enabled
    async def nightly_auto_apply_mappings():
        """Nightly job to auto-apply AI mapping suggestions."""
        while True:
            try:
                await asyncio.sleep(86400)  # 24 hours
                config = config_manager.config
                if getattr(config, "ai_auto_apply_mappings", False):
                    log.info("[NIGHTLY] Running auto-apply mappings job...")
                    from services.ai_classifier import get_channel_mapping_suggestions
                    suggestions = get_channel_mapping_suggestions()
                    for s in suggestions:
                        if s["move_count"] >= 3:
                            config.channel_mappings[s["channel_id"]] = s["playlist_id"]
                            log.info(f"[NIGHTLY] Auto-applied mapping: {s['channel_title']} -> {s['playlist_name']}")
                    await config_manager.save(config)
                    log.info("[NIGHTLY] Auto-apply mappings complete")
            except Exception as e:
                log.error(f"[NIGHTLY] Auto-apply mappings failed: {e}")
    
    asyncio.create_task(nightly_auto_apply_mappings())
    
    log.info("motus.leap started successfully")
    
    yield
    
    # Shutdown
    log.info("motus.leap shutting down")
    await shutdown_http_client()





# Initialize rate limiter

# Rate limit exceeded handler
async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Handle rate limit exceeded errors."""
    return PlainTextResponse(f"Rate limit exceeded: {exc.detail}", status_code=429)

# Configure existing FastAPI app
app.router.lifespan_context = lifespan
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Mount static files
if not any(getattr(route, "path", "") == "/static" for route in app.routes):
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


# Security middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers including strict CSP."""
    response = await call_next(request)

    # Strict Content Security Policy — explicitly list all allowed script sources
    response.headers["Content-Security-Policy"] = (
        f"default-src 'self'; "
        f"script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com /static/dashboard.js /static/subscriptions.js /static/auth-check.js /static/ux-enhancements.js /static/auth.js /static/global_scripts.js /static/playlists.js /static/playlist.js; "
        f"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        f"font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        f"img-src 'self' data: https://i.ytimg.com https://yt3.ggpht.com; "
        f"connect-src 'self' https://www.googleapis.com https://www.youtube.com wss://tubemanager.onrender.com ws: wss:; "
        f"frame-ancestors 'none'; "
        f"frame-src 'none';"
    )

    # Additional security headers
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

    return response



# Background task runners have been moved to services/background_worker.py


# API Models
class ActionIn(BaseModel):
    """Action request model."""
    action: str
    payload: dict[str, Any] | None = None


class MappingIn(BaseModel):
    """Channel mapping model."""
    channel: str
    playlist: str


class MappingsIn(BaseModel):
    """Bulk mappings model."""
    mappings: list[MappingIn] | dict[str, str] = []


class ConfigUpdateIn(BaseModel):
    """Config update model."""
    youtube_api_key: str | None = None
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = None
    rules: str | None = None


# =============================================================================
# Page routes
# =============================================================================


@app.get("/", dependencies=[Depends(require_auth)])
async def index():
    """Serve root page - dark theme dashboard."""
    return await no_cache_file_response(WEB_DIR / "dashboard.html")


@app.get("/auth")
async def auth():
    """Auth page."""
    return await no_cache_file_response(WEB_DIR / "auth.html")



@app.get("/playlists", dependencies=[Depends(require_auth)])
async def playlists():
    """Playlists page."""
    return await no_cache_file_response(WEB_DIR / "playlists.html")


@app.get("/subscriptions", dependencies=[Depends(require_auth)])
async def subscriptions():
    """Subscriptions page."""
    return await no_cache_file_response(WEB_DIR / "subscriptions.html")


@app.get("/maintenance", dependencies=[Depends(require_auth)])
async def maintenance():
    """Maintenance page."""
    return await no_cache_file_response(WEB_DIR / "maintenance.html")


@app.get("/rules", dependencies=[Depends(require_auth)])
async def rules():
    """Rules & Mappings page."""
    return await no_cache_file_response(WEB_DIR / "settings.html")


@app.get("/ai", dependencies=[Depends(require_auth)])
async def ai():
    """AI Integration page."""
    return await no_cache_file_response(WEB_DIR / "settings.html")


@app.get("/bulk", dependencies=[Depends(require_auth)])
async def bulk():
    """Bulk operations page."""
    return await no_cache_file_response(WEB_DIR / "bulk.html")


@app.get("/settings", dependencies=[Depends(require_auth)])
async def settings():
    """Settings page."""
    return await no_cache_file_response(WEB_DIR / "settings.html")


@app.get("/roadmap", dependencies=[Depends(require_auth)])
async def roadmap_page() -> Response:
    return await no_cache_file_response(WEB_DIR / "roadmap.html")


@app.get("/test", dependencies=[Depends(require_auth)])
async def test_page():
    """Test page."""
    return await no_cache_file_response(WEB_DIR / "test.html")
# Health check
@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


# Single-request endpoint - QUOTA OPTIMIZED
@app.get("/api/youtube/fetch-all")
@limiter.limit("10/minute")  # Rate limit: 10 requests per minute
async def fetch_all_youtube_data(request: Request, force_refresh: bool = False):
    """Fetch ALL YouTube data in one optimized request (subscriptions, playlists, videos with duration).

    This is the QUOTA-OPTIMIZED endpoint. Use this to get everything in one call.
    Data is cached for 10 minutes to minimize API quota usage.

    Query params:
        force_refresh: If True, bypass cache and fetch fresh data
    """
    if not youtube_service:
        return {"error": "YouTube service not initialized"}
    
    result = await youtube_service.fetch_all_data(force_refresh=force_refresh)
    return result


@app.get("/api/playlists/names")
async def api_playlist_names():
    """Return lightweight playlist ID+name pairs for dropdowns (fast, cached)."""
    if not youtube_service:
        return {"playlists": []}
    try:
        data = await youtube_service.list_playlists()
        playlists = data.get("playlists", [])
        return {"playlists": [{"id": p["id"], "title": p["title"], "video_count": p.get("video_count", 0)} for p in playlists]}
    except Exception as e:
        log.warning(f"Failed to load playlist names: {e}")
        return {"playlists": []}


@app.get("/api/watch-later")
async def get_watch_later(force_refresh: bool = False):
    """Fetch Watch Later playlist contents using browser scraper (bypasses API restriction)."""
    try:
        if not youtube_service:
            return {"items": [], "source": "none", "error": "YouTube service not initialized"}

        configured_id = config_manager.config.watch_later_playlist_id if hasattr(config_manager.config, 'watch_later_playlist_id') else ""

        # Use the cached method
        watch_later_data = await youtube_service.list_watch_later_items_cached(
            playlist_id=configured_id if configured_id else None,
            force_refresh=force_refresh
        )
        
        if watch_later_data.get("error"):
            return {"items": [], "source": "error", "error": watch_later_data["error"]}

        items = watch_later_data.get("items", [])
        source = "api-cached" # Default to API cached for now, browser scrape will override

        # If it was a browser scrape, the log from youtube_service will indicate it, no need to re-scrape here
        if not configured_id and items and watch_later_data.get("source") == "browser": # Check if source was browser scrape from the cached data
             source = "browser"

        # Try to get the playlist title for the display badge if configured_id is used
        pl_name = configured_id
        if configured_id and items:
            try:
                pl_data = await youtube_service.list_playlists()
                for p in pl_data.get("playlists", []):
                    if p.get("id") == configured_id:
                        pl_name = p.get("title", configured_id)
                        break
            except Exception:
                pass
            source = f"configured: {pl_name}"
            
        return {"items": items, "source": source}
    except Exception as e:
        log.error(f"Watch Later fetch failed: {e}")
        return {"items": [], "error": str(e), "source": "error"}


class WatchLaterMoveIn(BaseModel):
    video_ids: list[str]
    target_playlist_id: str


@app.post("/api/watch-later/move", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def move_watch_later_videos(body: WatchLaterMoveIn):
    """Move selected videos from Watch Later to a target playlist."""
    if not youtube_service:
        return {"error": "YouTube service not initialized"}
    
    yt_client = youtube_service.get_client(require_oauth=True)
    if not yt_client:
        return {"error": "OAuth required"}
    
    results = {"moved": [], "failed": []}
    for video_id in body.video_ids:
        try:
            yt_client.move_video_to_playlist(video_id, body.target_playlist_id)
            results["moved"].append(video_id)
        except Exception as e:
            log.error(f"Failed to move video {video_id}: {e}")
            results["failed"].append({"video_id": video_id, "error": str(e)})
    
    return results


@app.get("/api/youtube/videos")
async def get_youtube_videos(playlist_id: Optional[str] = None, force_refresh: bool = False):
    """Get videos with duration (cached).

    Query params:
        playlist_id: If provided, filter by specific playlist
        force_refresh: If True, bypass cache
    """
    if not youtube_service:
        return {"videos": [], "error": "YouTube service not initialized"}
    
    result = await youtube_service.get_videos(playlist_id=playlist_id, force_refresh=force_refresh)
    return result


@app.get("/api/youtube/duplicates")
async def scan_duplicates_endpoint(playlist_id: Optional[str] = None):
    """Scan for duplicate videos in a playlist or all playlists."""
    if not youtube_service:
        return {"duplicates": 0, "error": "YouTube service not initialized"}
    
    videos = await youtube_service.get_videos(playlist_id=playlist_id)
    video_ids = [v.get("video_id") for v in videos.get("videos", [])]
    duplicates = len(video_ids) - len(set(video_ids))
    
    return {"duplicates": duplicates, "total_videos": len(video_ids), "playlist_id": playlist_id}


@app.get("/api/youtube/misplaced")
async def scan_misplaced_endpoint(playlist_id: Optional[str] = None):
    """Scan for misplaced videos based on channel mappings."""
    if not youtube_service:
        return {"misplaced": [], "error": "YouTube service not initialized"}
    
    config = config_manager.config
    mappings = config.channel_mappings if hasattr(config, 'channel_mappings') else {}
    
    videos = await youtube_service.get_videos(playlist_id=playlist_id)
    misplaced = []
    for v in videos.get("videos", []):
        video_playlist_id = v.get("playlist_id")
        if video_playlist_id and video_playlist_id in mappings:
            expected_channel = mappings[video_playlist_id]
            video_channel = v.get("channel_title", "")
            if expected_channel and video_channel and expected_channel not in video_channel:
                misplaced.append({"video_id": v.get("video_id"), "title": v.get("title"), "reason": f"Expected channel: {expected_channel}"})
    
    return {"misplaced": misplaced, "count": len(misplaced)}


# Stats endpoint
@app.get("/api/stats")
async def stats() -> dict[str, Any]:
    """Dashboard statistics endpoint."""
    if youtube_service:
        yt_stats = await youtube_service.get_basic_stats()
    else:
        yt_stats = {"total_playlists": 0, "total_videos": 0}

    total_playlists = yt_stats.get("total_playlists", 0)
    total_videos = yt_stats.get("total_videos", 0)

    config = config_manager.config
    # Calculate real stats from config
    ai_learning_active = getattr(config, 'ai_learning_enabled', False)
    channel_mappings_count = len(config.channel_mappings) if hasattr(config, 'channel_mappings') else 0
    total_subscriptions = yt_stats.get("total_subscriptions", 0)

    # Get real cache stats
    cache_hit_rate = "N/A"
    if youtube_service and hasattr(youtube_service, '_cache'):
        cache_stats = youtube_service._cache.get_stats()
        cache_hit_rate = cache_stats['hit_rate']

    return {
        **yt_stats,
        "total_playlists": total_playlists,
        "total_videos": total_videos,
        "playlists_count": total_playlists,
        "tracked_videos": total_videos,
        "items_data": 0,
        "still_items": 0,
        "pending_actions": task_queue.qsize(),
        "running_tasks": 1 if worker and worker.current_task_name else 0,
        "current_task": worker.current_task_name if worker else None,
        "ai_learning": ai_learning_active,
        "learning_rate": f"{(channel_mappings_count / max(total_subscriptions, 1) * 100):.1f}%" if total_subscriptions > 0 else "0%",
        "learning_rates": str(channel_mappings_count),
        "cache_hit_rate": cache_hit_rate,
        "last_scan": config.last_scan_time if hasattr(config, 'last_scan_time') else "Never",
    }


# Playlists endpoint
@app.get("/api/playlists")
async def api_playlists() -> dict[str, Any]:
    """Get playlists data."""
    if youtube_service:
        return await youtube_service.list_playlists()
    return {"playlists": [], "error": "YouTube service not available"}


@app.post("/api/youtube/playlists/rename", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def rename_playlist_endpoint(payload: dict):
    playlist_id = payload.get("playlist_id")
    new_title = payload.get("new_title")
    if not playlist_id or not new_title:
        raise HTTPException(status_code=400, detail="Missing playlist_id or new_title")
    if not youtube_service:
        raise HTTPException(status_code=500, detail="YouTube service not initialized")
    
    yt_client = youtube_service.get_client(require_oauth=True)
    if not yt_client:
        raise HTTPException(status_code=401, detail="OAuth client not available")
    
    try:
        google_client = yt_client._get_client(require_oauth=True)
        google_client.playlists().update(
            part="snippet",
            body={
                "id": playlist_id,
                "snippet": {
                    "title": new_title
                }
            }
        ).execute()
        # In-place cache update: update the renamed playlist in caches
        config = config_manager.config
        user_id = hashlib.sha256((config.oauth.access_token or "").encode()).hexdigest()[:16]
        all_key = f"all_data_{user_id}"
        if youtube_service._cache:
            cached_all = await youtube_service._get_cached(all_key)
            if cached_all and "playlists" in cached_all:
                for p in cached_all["playlists"]:
                    if p.get("id") == playlist_id:
                        p["title"] = new_title
                        break
                await youtube_service._set_cached(all_key, cached_all)
            cached_pl = await youtube_service._get_cached("playlists")
            if cached_pl and "playlists" in cached_pl:
                for p in cached_pl["playlists"]:
                    if p.get("id") == playlist_id:
                        p["title"] = new_title
                        break
                cached_pl["playlists"].sort(key=lambda x: x["title"].lower())
                await youtube_service._set_cached("playlists", cached_pl)
        return {"status": "success", "message": f"Playlist renamed to {new_title}"}
    except Exception as e:
        log.error(f"Error renaming playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/youtube/playlists/delete", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def delete_playlist_endpoint(payload: dict):
    playlist_id = payload.get("playlist_id")
    if not playlist_id:
        raise HTTPException(status_code=400, detail="Missing playlist_id")
    if not youtube_service:
        raise HTTPException(status_code=500, detail="YouTube service not initialized")
    
    yt_client = youtube_service.get_client(require_oauth=True)
    if not yt_client:
        raise HTTPException(status_code=401, detail="OAuth client not available")
    
    try:
        google_client = yt_client._get_client(require_oauth=True)
        google_client.playlists().delete(id=playlist_id).execute()
        
        # In-place cache update: remove the deleted playlist from caches
        config = config_manager.config
        user_id = hashlib.sha256((config.oauth.access_token or "").encode()).hexdigest()[:16]
        all_key = f"all_data_{user_id}"
        # Remove from memory cache
        if youtube_service._cache:
            cached_all = await youtube_service._get_cached(all_key)
            if cached_all and "playlists" in cached_all:
                cached_all["playlists"] = [p for p in cached_all["playlists"] if p.get("id") != playlist_id]
                cached_all["stats"]["total_playlists"] = len(cached_all["playlists"])
                await youtube_service._set_cached(all_key, cached_all)
            # Also update playlists cache
            cached_pl = await youtube_service._get_cached("playlists")
            if cached_pl and "playlists" in cached_pl:
                cached_pl["playlists"] = [p for p in cached_pl["playlists"] if p.get("id") != playlist_id]
                cached_pl["stats"]["total_playlists"] = len(cached_pl["playlists"])
                await youtube_service._set_cached("playlists", cached_pl)
        
        return {"status": "success", "message": "Playlist deleted successfully"}
    except Exception as e:
        log.error(f"Error deleting playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/youtube/playlists/duplicate", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def duplicate_playlist_endpoint(payload: dict):
    playlist_id = payload.get("playlist_id")
    new_title = payload.get("new_title")
    if not playlist_id or not new_title:
        raise HTTPException(status_code=400, detail="Missing playlist_id or new_title")
    if not youtube_service:
        raise HTTPException(status_code=500, detail="YouTube service not initialized")
    
    yt_client = youtube_service.get_client(require_oauth=True)
    if not yt_client:
        raise HTTPException(status_code=401, detail="OAuth client not available")
    
    try:
        google_client = yt_client._get_client(require_oauth=True)
        
        # 1. Create a new playlist
        new_pl = google_client.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {
                    "title": new_title,
                    "description": "Duplicated from original"
                },
                "status": {
                    "privacyStatus": "private"
                }
            }
        ).execute()
        new_playlist_id = new_pl["id"]
        
        # 2. Get videos from original playlist and copy them (in background task)
        async def copy_videos_task():
            try:
                # Retrieve all videos of original playlist
                orig_videos = await youtube_service.get_videos(playlist_id=playlist_id)
                videos_list = orig_videos.get("videos", [])
                
                # Insert each video into the new playlist
                for v in videos_list:
                    try:
                        google_client.playlistItems().insert(
                            part="snippet",
                            body={
                                "snippet": {
                                    "playlistId": new_playlist_id,
                                    "resourceId": {
                                        "kind": "youtube#video",
                                        "videoId": v.get("video_id")
                                    }
                                }
                            }
                        ).execute()
                    except Exception as ve:
                        log.error(f"Error copying video {v.get('video_id')}: {ve}")
                
                # Force refresh cache
                await youtube_service.fetch_all_data(force_refresh=True)
            except Exception as te:
                log.error(f"Error in background copy task: {te}")
                
        # Run copy task in background
        asyncio.create_task(copy_videos_task())
        
        return {"status": "success", "message": f"Duplication started. Playlist '{new_title}' is being populated."}
    except Exception as e:
        log.error(f"Error duplicating playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/youtube/playlistitems/delete", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def delete_playlist_item_endpoint(payload: dict):
    playlist_item_id = payload.get("playlist_item_id")
    playlist_id = payload.get("playlist_id")
    if not playlist_item_id:
        raise HTTPException(status_code=400, detail="Missing playlist_item_id")
    if not youtube_service:
        raise HTTPException(status_code=500, detail="YouTube service not initialized")
    
    yt_client = youtube_service.get_client(require_oauth=True)
    if not yt_client:
        raise HTTPException(status_code=401, detail="OAuth client not available")
    
    try:
        yt_client.remove_video_from_playlist(playlist_item_id)
        if playlist_id:
            # Invalidate the specific playlist's cache key so the change is shown immediately
            await youtube_service._set_cached(f"playlist_videos_{playlist_id}", None)
            
        return {"status": "success", "message": "Video removed from playlist"}
    except Exception as e:
        log.error(f"Error removing video from playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Subscriptions endpoint
@app.get("/api/subscriptions")
async def api_subscriptions() -> dict[str, Any]:
    """Get subscriptions data."""
    if youtube_service:
        result = await youtube_service.list_subscriptions()
        # The list_subscriptions method returns {"channels": [], "total_subscriptions": N}
        # Ensure we return only the "channels" list or an empty list if an error occurred
        return {"channels": result.get("channels", []), "error": result.get("error")}
    return {"channels": [], "error": "YouTube service not available"}


# Maintenance endpoint
@app.get("/api/maintenance")
async def api_maintenance() -> dict[str, Any]:
    """Get maintenance data."""
    maintenance_file = Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data")) / "maintenance.json"
    if maintenance_file.exists():
        try:
            return json.loads(maintenance_file.read_text())
        except Exception:
            pass
    return {
        "move_from_x_to_y": [],
        "duplicated_videos": [],
        "misplaced_videos": [],
        "info": "Maintenance analysis requires full video scan. Run Full Playlist Sync first."
    }


# Mappings endpoints
def _normalize_mappings(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize mappings to standard format."""
    seen: dict[str, dict[str, Any]] = {}
    for item in items or []:
        channel_id = (item.get("channel_id") or item.get("channel") or "").strip()
        playlist_id = (item.get("playlist") or item.get("playlist_id") or "").strip()
        if not channel_id:
            continue
        seen[channel_id] = {
            "channel": channel_id,
            "channel_id": channel_id,
            "playlist": playlist_id,
        }
    return list(seen.values())


def _serialize_mappings(items: list[dict[str, Any]]) -> dict[str, str]:
    """Serialize mappings to dictionary."""
    result: dict[str, str] = {}
    for item in items or []:
        channel_id = (item.get("channel_id") or item.get("channel") or "").strip()
        playlist_id = (item.get("playlist") or item.get("playlist_id") or "").strip()
        if channel_id:
            result[channel_id] = playlist_id
    return result


def _extract_mapping_items(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract mappings from request body."""
    mappings = body.get("mappings", {})
    if isinstance(mappings, list):
        return mappings
    if isinstance(mappings, dict):
        return [
            {"channel_id": channel_id, "playlist": playlist_id}
            for channel_id, playlist_id in mappings.items()
        ]
    return []


@app.get("/api/mappings")
async def api_mappings() -> dict[str, Any]:
    """Get channel mappings."""
    config = config_manager.config
    raw = config.channel_mappings
    formatted: list[dict[str, Any]] = []
    
    if isinstance(raw, dict):
        formatted.extend(
            {
                "channel": channel_id,
                "channel_id": channel_id,
                "playlist": playlist_id,
            }
            for channel_id, playlist_id in raw.items()
        )
    elif isinstance(raw, list):
        formatted.extend(
            {
                "channel": item.get("channel_id") or item.get("channel") or "",
                "channel_id": item.get("channel_id") or item.get("channel") or "",
                "playlist": item.get("playlist") or item.get("playlist_id") or "",
            }
            for item in raw
        )
    
    return {"mappings": _normalize_mappings(formatted)}


@app.post("/api/mappings", dependencies=[Depends(get_current_user), Depends(verify_origin)])
@limiter.limit("30/minute")  # Rate limit: 30 save operations per minute
async def save_mappings(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    """Save channel mappings."""
    mappings = _normalize_mappings(_extract_mapping_items(body))
    config = config_manager.config
    config.channel_mappings = _serialize_mappings(mappings)
    await config_manager.save(config)
    return {"message": "Mappings saved", "mappings": mappings}

# Action endpoint
@app.post("/api/action", dependencies=[Depends(get_current_user), Depends(verify_origin)])
@limiter.limit("20/minute")  # Rate limit: 20 actions per minute
async def trigger_action(request: Request, body: ActionIn):
    """Queue a background action."""
    await task_queue.put({"action": body.action, "payload": body.payload or {}})
    return {"status": "queued", "action": body.action}


# Watch Later page with AI scan
@app.get("/watch-later")
async def watch_later_page():
    """Serve the Watch Later full page with AI scan and correction UI."""
    return await no_cache_file_response(WEB_DIR / "watch-later.html")


# Playlist detail page
@app.get("/playlist/{playlist_id}")
async def playlist_detail(playlist_id: str):
    """Serve playlist detail page."""
    return await no_cache_file_response(WEB_DIR / "playlist.html")


@app.get("/api/actions/status")
async def action_status():
    """Get action status."""
    return {"queue_size": task_queue.qsize(), "running": worker.background_tasks_running if worker else False}


@app.post("/api/action/cancel", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def cancel_action():
    """Cancel the currently running background task."""
    if worker:
        worker.cancel_current_task()
        await manager.broadcast(json.dumps({"type": "log", "message": "[CANCEL] Current task cancelled by user."}))
        return {"status": "cancelled"}
    return {"error": "No worker available"}


# YouTube OAuth
from secrets import token_urlsafe

# In-memory state store (in production, use Redis or similar)
_oauth_states = {}

def _generate_state() -> str:
    return token_urlsafe(32)

def _store_state(state: str, data: dict = None):
    _oauth_states[state] = {"data": data or {}, "created": time.time()}

def _validate_and_consume_state(state: str) -> dict:
    """Validate and remove state. Returns stored data or empty dict if invalid."""
    if state not in _oauth_states:
        return {}
    stored = _oauth_states.pop(state)
    # Check if state is older than 10 minutes
    if time.time() - stored["created"] > 600:
        return {}
    return stored["data"]


@app.get("/auth/youtube")
async def youtube_auth():
    """Initiate Google OAuth flow for YouTube API."""
    config = config_manager.config
    client_id = config.oauth.client_id
    if not client_id:
        return {"error": "OAuth client ID not configured in settings"}
    
    redirect_uri = "https://tubemanager.onrender.com/auth/youtube/callback"
    scope = "https://www.googleapis.com/auth/youtube.force-ssl https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile openid"
    
    # Generate and store state for CSRF protection
    state = _generate_state()
    _store_state(state)
    
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent select_account",
        "state": state,
    }
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return {"auth_url": auth_url}


def _secret_val(val):
    """Safely extract secret value from SecretStr or plain string."""
    if hasattr(val, 'get_secret_value'):
        return val.get_secret_value()
    return str(val) if val else ""


@app.get("/auth/youtube/callback")
async def youtube_callback(code: str, state: str = None):
    """Handle OAuth callback and exchange code for tokens."""
    import httpx
    
    # Validate OAuth state parameter (CSRF protection)
    if not state or not _validate_and_consume_state(state):
        log.error("Invalid or missing OAuth state parameter")
        return HTMLResponse("""
            <h1>❌ Invalid OAuth State</h1>
            <p>The OAuth state parameter is missing or invalid. This may be a CSRF attack attempt.</p>
            <p>Please <a href="/auth/youtube">try again</a>.</p>
        """, status_code=400)
    
    config = config_manager.config

    if not config.oauth.client_id or not _secret_val(config.oauth.client_secret):
        log.error("OAuth credentials not configured")
        return HTMLResponse("""
            <h1>❌ OAuth Not Configured</h1>
            <p>Please go to <a href="/settings">Settings</a> and enter your OAuth Client ID and Secret, then save.</p>
            <p>Client ID: <code>343644756734-vht75phpm5ae7m3dm439aolurvpuhdc1.apps.googleusercontent.com</code></p>
        """, status_code=400)
    
    redirect_uri = "https://tubemanager.onrender.com/auth/youtube/callback"
    token_url = "https://oauth2.googleapis.com/token"  # nosec
    data = {
        "code": code,
        "client_id": config.oauth.client_id,
        "client_secret": _secret_val(config.oauth.client_secret),
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(token_url, data=data)
            tokens = resp.json()
        
        log.info(f"Token response status: {resp.status_code}")
        log.info("OAuth token exchange completed successfully")
        
        if "access_token" in tokens:
            config.oauth.access_token = tokens.get("access_token")
            config.oauth.refresh_token = tokens.get("refresh_token")
            expires_in = int(tokens.get("expires_in", 3600))
            config.oauth.token_expiry = int(time.time()) + expires_in
            await config_manager.save(config)
            
            log.info("YouTube OAuth tokens saved successfully")
            
            # Update YouTube service
            global youtube_service
            youtube_service = YouTubeService(config)
            
            return HTMLResponse("""
                <h1 style="color: #44ff88;">✅ YouTube Connected!</h1>
                <p>Tokens saved. Redirecting to Settings...</p>
                <p style="color: #7b8bb5; font-size: 12px;">Access token expires in: """ + str(tokens.get("expires_in", 3600)) + """ seconds</p>
                <script>
                    if (window.opener) {
                        window.opener.postMessage({type: 'youtube-oauth-success'}, '*');
                        setTimeout(() => window.close(), 1500);
                    } else {
                        setTimeout(() => { window.location.href = '/settings'; }, 2000);
                    }
                </script>
            """)
        else:
            error_msg = tokens.get("error_description", tokens.get("error", str(tokens)))
            log.error(f"OAuth token error: {error_msg}")
            safe_error = error_msg.replace("'", "\\'")
            err_html = f"""
                <h1 style="color: #ff4444;">❌ OAuth Error</h1>
                <p><strong>Error:</strong> {error_msg}</p>
                <p><a href="/settings">Return to Settings</a> to verify credentials.</p>
                <script>
                    if (window.opener) {{
                        window.opener.postMessage({{type: 'youtube-oauth-error', error: '{safe_error}'}}, '*');
                        setTimeout(() => window.close(), 1500);
                    }} else {{
                        setTimeout(() => {{ window.location.href = '/settings'; }}, 3000);
                    }}
                </script>
            """
            return HTMLResponse(err_html, status_code=400)
    except httpx.RequestError as e:
        log.error(f"HTTP request failed: {e}")
        return HTMLResponse(f"""
            <h1 style="color: #ff4444;">❌ Network Error</h1>
            <p>Failed to connect to Google: {str(e)}</p>
        """, status_code=500)
    except Exception as e:
        log.exception("Unexpected error in OAuth callback")
        return HTMLResponse(f"""
            <h1 style="color: #ff4444;">❌ Server Error</h1>
            <p>{str(e)}</p>
        """, status_code=500)


@app.get("/api/youtube/status")
async def youtube_status():
    """Check YouTube OAuth connection status."""
    config = config_manager.config
    return {
        "connected": bool(config.oauth.access_token and config.oauth.refresh_token),
        "has_refresh": bool(config.oauth.refresh_token),
        "api_key_configured": bool(config.youtube_api_key),
    }


@app.post("/api/youtube/disconnect", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def youtube_disconnect():
    """Clear stored YouTube OAuth tokens."""
    global youtube_service
    config = config_manager.config
    config.oauth.access_token = ""
    config.oauth.refresh_token = ""
    config.oauth.token_expiry = 0
    await config_manager.save(config)
    # Recreate YouTubeService without OAuth tokens
    youtube_service = YouTubeService(config)
    return {"message": "YouTube OAuth disconnected. Re-authorize in Settings to reconnect."}


class SettingsIn(BaseModel):
    """Settings input model."""
    youtube_api_key: str | None = None
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = None
    default_privacy: str | None = None
    scan_interval: str | None = None
    max_concurrent: int | None = None
    auto_sort: bool | None = None
    sync_watch_later: bool | None = None
    watch_later_playlist_id: str | None = None
    notify_failures: bool | None = None
    dark_mode: bool | None = None
    log_level: str | None = None
    ai_provider: str | None = None
    ai_api_key: str | None = None
    ai_mode: str | None = None
    ai_classification_prompt: str | None = None
    ai_custom_endpoint: str | None = None
    ai_custom_model: str | None = None
    ai_auto_apply_mappings: bool | None = None


@app.get("/api/settings")
async def get_settings():
    """Get current settings."""
    config = config_manager.config
    return {
        "youtube_api_key": (_secret_val(config.youtube_api_key) or "")[:4] + "••••" if _secret_val(config.youtube_api_key) else "",
        "oauth_client_id": config.oauth.client_id,
        "oauth_client_secret": "••••••••" if _secret_val(config.oauth.client_secret) else "",
        "default_privacy": config.default_privacy,
        "scan_interval": config.scan_interval,
        "max_concurrent": config.max_concurrent,
        "auto_sort": config.auto_sort,
        "sync_watch_later": config.sync_watch_later,
        "watch_later_playlist_id": getattr(config, "watch_later_playlist_id", ""),
        "notify_failures": config.notify_failures,
        "dark_mode": config.dark_mode,
        "log_level": config.log_level,
        "ai_provider": config.ai_provider,
        "ai_api_key": "••••••••" if _secret_val(config.ai_api_key) else "",
        "ai_mode": config.ai_mode,
        "ai_classification_prompt": config.ai_classification_prompt,
        "ai_custom_endpoint": config.ai_custom_endpoint,
        "ai_custom_model": config.ai_custom_model,
        "ai_auto_apply_mappings": config.ai_auto_apply_mappings,
    }


@app.post("/api/settings", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def save_settings(body: SettingsIn):
    """Save settings."""
    config = config_manager.config
    
    for key, value in body.model_dump(exclude_none=True).items():
        if hasattr(config, key):
            setattr(config, key, value)
        elif key == "oauth_client_id":
            config.oauth.client_id = value
        elif key == "oauth_client_secret":
            config.oauth.client_secret = value
    
    await config_manager.save(config)
    
    # Update YouTube service if credentials changed
    global youtube_service
    youtube_service = YouTubeService(config)
    
    return {
        "status": "saved",
        "youtube_api_key": (_secret_val(config.youtube_api_key) or "")[:4] + "••••" if _secret_val(config.youtube_api_key) else "",
        "oauth_client_id": config.oauth.client_id,
        "oauth_client_secret": "••••••••" if _secret_val(config.oauth.client_secret) else "",
    }


class AIClassifyIn(BaseModel):
    video_ids: list[str]
    playlist_names: list[dict] | None = None  # optional override
    metadata: list[dict] | None = None  # [{video_id, title, channel, description}]


@app.post("/api/ai/classify", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_classify_videos(body: AIClassifyIn):
    """Classify videos using the configured AI provider.
    
    Accepts optional metadata to avoid extra YouTube API calls.
    If metadata is provided, it is used directly instead of fetching from YouTube.
    """
    config = config_manager.config
    provider = config.ai_provider
    api_key = _secret_val(config.ai_api_key)
    prompt = config.ai_classification_prompt
    custom_endpoint = config.ai_custom_endpoint
    custom_model = config.ai_custom_model
    
    if not provider or not api_key:
        return {"error": "AI provider not configured"}
    
    # Get playlists for classification targets
    playlists = []
    if body.playlist_names:
        playlists = body.playlist_names
    else:
        from services.youtube_service import YouTubeService
        ys = YouTubeService(config)
        pl_data = await ys.list_playlists()
        playlists = [{"id": p["id"], "title": p["title"]} for p in pl_data.get("playlists", [])]
    
    if not playlists:
        return {"error": "No playlists available"}
    
    from services.ai_classifier import classify_video
    
    results = []
    for i, vid in enumerate(body.video_ids):
        try:
            # Use provided metadata if available (avoids YouTube API call)
            if body.metadata and i < len(body.metadata):
                meta = body.metadata[i]
                title = meta.get("title", "")
                channel = meta.get("channel", "")
                description = meta.get("description", "")
            else:
                title = ""
                channel = ""
                description = ""
            
            matched_playlist, error = classify_video(
                title=title, channel=channel, description=description,
                playlists=playlists, provider=provider, api_key=api_key,
                prompt_template=prompt,
                custom_endpoint=custom_endpoint, custom_model=custom_model,
            )
            
            result = {
                "video_id": vid,
                "title": title,
                "channel": channel,
                "matched_playlist": matched_playlist,
            }
            if error:
                result["error"] = error
            results.append(result)
        except Exception as e:
            results.append({"video_id": vid, "error": str(e)})
    
    return {"results": results}


class RecordMoveIn(BaseModel):
    video_id: str
    title: str = ""
    channel_id: str = ""
    channel_title: str = ""
    from_playlist_name: str = ""
    from_playlist_id: str = ""
    to_playlist_name: str = ""
    to_playlist_id: str = ""
    source: str = "manual"


@app.post("/api/ai/record-move", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_record_move(body: RecordMoveIn):
    """Record a video move for AI training memory."""
    from services.ai_classifier import record_move
    record_move(
        video_id=body.video_id,
        title=body.title,
        channel_id=body.channel_id,
        channel_title=body.channel_title,
        from_playlist_name=body.from_playlist_name,
        from_playlist_id=body.from_playlist_id,
        to_playlist_name=body.to_playlist_name,
        to_playlist_id=body.to_playlist_id,
        source=body.source,
    )
    return {"status": "recorded"}


@app.get("/api/ai/suggestions")
async def ai_get_suggestions():
    """Get channel mapping suggestions from training memory."""
    from services.ai_classifier import get_channel_mapping_suggestions
    suggestions = get_channel_mapping_suggestions()
    return {"suggestions": suggestions}


@app.get("/api/ai/memory")
async def ai_get_memory():
    """Get raw training memory entries."""
    from services.ai_classifier import _load_memory
    memory = _load_memory()
    return {"moves": memory[-100:]}


# Reset settings
@app.post("/api/settings/reset", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def reset_settings():
    """Reset all settings to defaults."""
    config = TubeManagerConfig()
    await config_manager.save(config)
    
    global youtube_service
    youtube_service = YouTubeService(config)
    
    return {"message": "Settings reset to defaults"}


# Diagnostics endpoint
@app.get("/api/diagnostics/youtube")
async def diagnostics_youtube() -> dict[str, Any]:
    """Check YouTube OAuth status and test API connectivity."""
    if not youtube_service:
        return {"status": "error", "message": "YouTube service not initialized"}
    
    config = config_manager.config
    result = {
        "status": "ok",
        "oauth_configured": bool(config.oauth.access_token and config.oauth.refresh_token),
        "client_id_configured": bool(config.oauth.client_id),
        "client_secret_configured": bool(config.oauth.client_secret),
        "token_expiry": config.oauth.token_expiry,
        "playlist_count": 0,
        "error": None,
    }
    
    client = youtube_service.get_client(require_oauth=True)
    if not client:
        result["status"] = "error"
        result["error"] = "OAuth client could not be built (missing/invalid credentials)"
        return result
    
    try:
        resp = client.list_mine_playlists(max_results=10)
        result["playlist_count"] = len(resp.get("items", []))
        result["googleapi_items"] = len(resp.get("items", []))
        if resp.get("items"):
            first = resp["items"][0]
            result["googleapi_first_item_id"] = first.get("id")
            result["googleapi_first_item_title"] = first.get("snippet", {}).get("title")
        result["raw_response_keys"] = list(resp.keys())
        
        # Also fetch channel info to verify which account is connected
        channel_resp = client.list_mine_channels()
        channel_items = channel_resp.get("items", [])
        if channel_items:
            snippet = channel_items[0].get("snippet", {})
            result["channel_title"] = snippet.get("title", "Unknown")
            result["channel_id"] = channel_items[0].get("id", "")

        # Raw HTTP check bypassing googleapiclient to confirm API response
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            raw_playlists = await http_client.get(
                "https://www.googleapis.com/youtube/v3/playlists",
                headers={"Authorization": f"Bearer {config.oauth.access_token}"},
                params={"part": "snippet,contentDetails", "mine": "true", "maxResults": 10},
            )
            result["raw_api_status"] = raw_playlists.status_code
            try:
                result["raw_api_response"] = raw_playlists.json()
            except Exception:
                result["raw_api_body"] = raw_playlists.text[:500]
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"{type(e).__name__}: {str(e)}"
    
    return result


@app.get("/api/diagnostics/oauth-user")
async def diagnostics_oauth_user() -> dict[str, Any]:
    """Return the Google account and YouTube channel linked to the stored OAuth token."""
    config = config_manager.config
    result: dict[str, Any] = {
        "oauth_configured": bool(config.oauth.access_token and config.oauth.refresh_token),
        "token_expiry": config.oauth.token_expiry,
    }
    if not config.oauth.access_token:
        result["error"] = "No OAuth access token stored"
        return result

    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            userinfo_resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {config.oauth.access_token}"},
            )
            result["userinfo_status"] = userinfo_resp.status_code
            if userinfo_resp.status_code == 200:
                userinfo = userinfo_resp.json()
                result["google_email"] = userinfo.get("email")
                result["google_name"] = userinfo.get("name")
                result["google_id"] = userinfo.get("id")
            else:
                # YouTube-only tokens don't have userinfo scope; this is normal.
                result["userinfo_note"] = "Token lacks OpenID/email scope (expected for YouTube-only OAuth)"

        yt_client = youtube_service.get_client(require_oauth=True) if youtube_service else None
        if yt_client:
            channel_resp = yt_client.list_mine_channels()
            channel_items = channel_resp.get("items", [])
            result["youtube_channel_count"] = len(channel_items)
            if channel_items:
                snippet = channel_items[0].get("snippet", {})
                result["youtube_channel_title"] = snippet.get("title")
                result["youtube_channel_id"] = channel_items[0].get("id")
        else:
            result["youtube_client_error"] = "Could not build YouTube OAuth client"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)}"

    

@app.get("/api/user")
async def api_user() -> dict[str, Any]:
    """Return logged-in user info for header display."""
    config = config_manager.config
    if not (config.oauth.access_token and config.oauth.refresh_token):
        return {"logged_in": False}
    
    result = {"logged_in": True, "channel_title": "Unknown Channel"}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            channel_resp = await client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "snippet", "mine": "true"},
                headers={"Authorization": f"Bearer {config.oauth.access_token}"}
            )
            if channel_resp.status_code == 200:
                data = channel_resp.json()
                if data.get("items"):
                    item = data["items"][0]
                    result["channel_title"] = item.get("snippet", {}).get("title", "Unknown")
                    result["channel_thumbnail"] = item.get("snippet", {}).get("thumbnails", {}).get("default", {}).get("url")
    except Exception as e:
        result["error"] = str(e)
    return result

# System endpoints

@app.post("/api/cookies/save", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def save_cookies(request: Request):
    """Save YouTube cookies for browser scraper."""
    try:
        body = await request.json()
        cookies = body.get("cookies", [])
        if not isinstance(cookies, list):
            return JSONResponse(status_code=400, content={"error": "Invalid cookie format: expected array"})

        cookies_file = Path(__file__).resolve().parent / "data" / "youtube_cookies.json"
        cookies_file.parent.mkdir(parents=True, exist_ok=True)

        with open(cookies_file, 'w') as f:
            json.dump(cookies, f, indent=2)

        log.info(f"Saved {len(cookies)} YouTube cookies to {cookies_file}")
        return {"status": "success", "count": len(cookies), "path": str(cookies_file)}
    except Exception as e:
        log.error(f"Failed to save cookies: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/user")
async def api_user() -> dict[str, Any]:
    """Return logged-in user info for header display."""
    config = config_manager.config
    if not (config.oauth.access_token and config.oauth.refresh_token):
        return {"logged_in": False}
    
    result = {"logged_in": True, "channel_title": "Unknown Channel"}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            channel_resp = await client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "snippet", "mine": "true"},
                headers={"Authorization": f"Bearer {config.oauth.access_token}"}
            )
            if channel_resp.status_code == 200:
                data = channel_resp.json()
                if data.get("items"):
                    item = data["items"][0]
                    result["channel_title"] = item.get("snippet", {}).get("title", "Unknown")
                    result["channel_thumbnail"] = item.get("snippet", {}).get("thumbnails", {}).get("default", {}).get("url")
    except Exception as e:
        result["error"] = str(e)
    return result

@app.get("/api/system/logs")
async def get_system_logs():
    """Get recent system logs."""
    return {
        "logs": [],
        "info": "System log aggregation not yet implemented. Use application stdout for logs."
    }


@app.get("/system/logs")
async def system_logs_page():
    """System logs viewer page."""
    log_file = Path("/app/data/tube_manager.log")
    logs_html = ""
    if log_file.exists():
        try:
            lines = log_file.read_text().strip().split("\n")
            last_200 = lines[-200:] if len(lines) > 200 else lines
            for line in last_200:
                escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                if "ERROR" in line or "CRITICAL" in line:
                    logs_html += f'<div style="color:#ff6b6b">{escaped}</div>'
                elif "WARNING" in line:
                    logs_html += f'<div style="color:#ffa94d">{escaped}</div>'
                elif "INFO" in line:
                    logs_html += f'<div style="color:#69db7c">{escaped}</div>'
                elif "DEBUG" in line:
                    logs_html += f'<div style="color:#74c0fc">{escaped}</div>'
                else:
                    logs_html += f'<div>{escaped}</div>'
        except Exception as e:
            logs_html = f'<div style="color:#ff6b6b">Error reading logs: {e}</div>'
    else:
        logs_html = '<div style="color:#868e96">No log file found. Logs are written to stdout only. Set a log file path in config to enable file logging.</div>'

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>System Logs - motus.leap</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');
        body {{ font-family: 'JetBrains Mono', monospace; background: #0a0c10; color: #e5e5e5; margin: 0; padding: 0; }}
        .header {{ background: #16191f; border-bottom: 1px solid #2a2f3a; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 10; }}
        .header h1 {{ font-size: 14px; margin: 0; color: #e5e5e5; }}
        .header a {{ color: #60a5fa; text-decoration: none; font-size: 12px; }}
        .header a:hover {{ text-decoration: underline; }}
        .log-container {{ padding: 16px 20px; font-size: 11px; line-height: 1.8; white-space: pre-wrap; word-break: break-all; }}
        .log-container div {{ border-bottom: 1px solid #1a1d24; padding: 2px 0; }}
        .controls {{ padding: 8px 20px; background: #16191f; border-bottom: 1px solid #2a2f3a; display: flex; gap: 8px; }}
        .controls button {{ background: #20242c; border: 1px solid #2a2f3a; color: #9ca3af; font-size: 10px; padding: 4px 12px; border-radius: 4px; cursor: pointer; font-family: 'JetBrains Mono', monospace; }}
        .controls button:hover {{ background: #2a2f3a; color: #e5e5e5; }}
        .filter-active {{ background: #3b82f6 !important; color: white !important; border-color: #3b82f6 !important; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📋 System Logs — motus.leap</h1>
        <a href="/settings">← Back to Settings</a>
    </div>
    <div class="controls">
        <button onclick="location.reload()">🔄 Refresh</button>
        <button onclick="document.getElementById('log-container').scrollTop = document.getElementById('log-container').scrollHeight">⬇ Bottom</button>
        <button onclick="document.getElementById('log-container').scrollTop = 0">⬆ Top</button>
    </div>
    <div class="log-container" id="log-container">{logs_html}</div>
    <script>document.getElementById('log-container').scrollTop = document.getElementById('log-container').scrollHeight;</script>
</body>
</html>""")


# Storage endpoints
@app.post("/api/storage/clear-thumbnails", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def clear_thumbnails():
    """Clear thumbnail cache."""
    import shutil
    try:
        thumb_dir = Path("/app/data/thumbnails")
        if thumb_dir.exists():
            shutil.rmtree(thumb_dir)
        thumb_dir.mkdir(parents=True, exist_ok=True)
        return {"message": "Thumbnail cache cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/storage/export")
async def export_data():
    """Export all data as JSON."""
    from datetime import datetime
    config = config_manager.config
    
    export_data = {
        "exported_at": datetime.utcnow().isoformat(),
        "config": config.model_dump(exclude={'oauth': {'client_secret', 'access_token', 'refresh_token'}}),
        "stats": await stats(),
    }
    return export_data


# Webhook endpoints
@app.post("/api/webhook/test", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def test_webhook(body: dict):
    """Test webhook URL."""
    import httpx
    url = body.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL required")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"test": True, "source": "motus.leap"})
        return {"message": f"Webhook test sent. Status: {resp.status_code}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook test failed: {str(e)}")


# WebSocket terminal
@app.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
    """WebSocket endpoint for terminal interaction."""
    await manager.connect(websocket)
    ping_interval = 30
    pong_timeout = 10
    max_ping_failures = 3
    ping_failures = 0
    
    try:
        await websocket.send_text(json.dumps({"type": "log", "message": "[WS] Connected to agent terminal"}))
        
        async def ping_loop():
            nonlocal ping_failures
            while True:
                await asyncio.sleep(ping_interval)
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                    try:
                        data = await asyncio.wait_for(websocket.receive_text(), timeout=pong_timeout)
                        msg = json.loads(data)
                        if msg.get("type") == "pong":
                            ping_failures = 0
                        else:
                            ping_failures += 1
                    except asyncio.TimeoutError:
                        ping_failures += 1
                    
                    if ping_failures >= max_ping_failures:
                        await manager.broadcast(json.dumps({"type": "log", "message": "[WS] Connection lost - max ping failures reached"}))
                        break
                except Exception as e:
                    log.debug(f"WebSocket handler terminated: {e}")
                    break
        
        ping_task = asyncio.create_task(ping_loop())
        
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif msg.get("type") == "pong":
                ping_failures = 0
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error(f"Broad WebSocket error: {e}")
        await manager.broadcast(json.dumps({"type": "log", "message": f"[WS ERROR] {str(e)}"}))
        # Log error but don't break - let the connection be handled normally
    finally:
        ping_task.cancel()
        manager.disconnect(websocket)


# Entry point
if __name__ == "__main__":
    import uvicorn
    setup_logging()
    uvicorn.run("app:app", host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8000")), reload=True)