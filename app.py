"""motus.leap Main Application."""
# Deploy v2.2

import os
import uuid
from dotenv import load_dotenv

try:
    load_dotenv() # Load environment variables from .env
except Exception as e:
    import sys
    print(f"[WARN] load_dotenv failed: {e}", file=sys.stderr)
import logging
from core.logger import setup_logging
log = logging.getLogger(__name__)

import asyncio
from datetime import datetime, timezone
import json
import hashlib
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlencode

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from starlette.responses import Response
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator, SecretStr
import aiofiles

# Video ID validation
YOUTUBE_VIDEO_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{11}$')

def validate_video_id(vid: str) -> bool:
    """Validate that a string matches YouTube's video ID format (11 chars, alphanumeric + _-)."""
    return bool(YOUTUBE_VIDEO_ID_RE.match(vid))


# YouTube playlist IDs: 13+ chars, alphanumeric + _-
YOUTUBE_PLAYLIST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{13,}$")


def validate_playlist_id(pid: str) -> bool:
    """Validate that a string matches YouTube's playlist ID format."""
    return bool(YOUTUBE_PLAYLIST_ID_RE.match(pid))

# Auth dependency for page routes (raises 401 if not authenticated)
from api.auth import get_current_user, verify_origin, create_default_admin, check_role, RoleEnum

# Rate limiting


# Import external limiter
from core.limiter import limiter
from slowapi.errors import RateLimitExceeded # Add RateLimitExceeded import

# Import routers
from api.bulk_operations import router as bulk_router
from api.auth import router as auth_router



# Core imports
from core.http_client import shutdown_http_client
from core.config_manager import ConfigManager
from models.config import TubeManagerConfig, ProviderConnection, PROVIDER_TYPES, PROVIDER_BUILTIN_BASE_URLS
from models.task import Task, TaskStatus, TaskPriority

# Service imports
from services.youtube_service import YouTubeService, _best_thumbnail
# Setup logging

# Paths
WEB_DIR = Path(__file__).resolve().parent / "web"
CONFIG_DIR = Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data")) if Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data")).exists() else Path(__file__).resolve().parent

# Initialize managers
config_manager = ConfigManager(CONFIG_DIR / "config.json")
youtube_service: Optional[YouTubeService] = None
background_worker: Optional["BackgroundWorker"] = None
worker = None  # backward compat alias


def _secret_val(val):
    """Safely extract the raw value from a SecretStr or return the string."""
    if hasattr(val, 'get_secret_value'):
        return val.get_secret_value()
    return str(val) if val else ""


def _redact_secrets(obj):
    """Recursively redact token/secret fields from a dict or list."""
    sensitive_keys = {"access_token", "refresh_token", "token", "secret", "client_secret", "api_key", "key", "authorization", "bearer"}
    if isinstance(obj, dict):
        return {
            k: "***REDACTED***" if k.lower() in sensitive_keys else _redact_secrets(v)
            for k, v in obj.items()
        }
    elif isinstance(obj, list):
        return [_redact_secrets(item) for item in obj]
    return obj


# =============================================================================
# Application lifespan
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global youtube_service, worker

    # Set up file logging
    log_dir = Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "tube_manager.log"
    setup_logging(log_file=log_file)

    config = await config_manager.load()
    youtube_service = YouTubeService(config)
    await create_default_admin()

    # Clean up stale disk cache files on startup
    try:
        removed = await youtube_service.disk_cache_cleanup(max_age_days=7)
        if removed:
            log.info(f"Startup cache cleanup: removed {removed} stale files")
    except Exception as e:
        log.warning(f"Startup disk cache cleanup failed (non-fatal): {e}")

    # Clean up stale LRU cache entries on startup (H11)
    try:
        if hasattr(youtube_service, '_cache'):
            stale_removed = await youtube_service._cache.cleanup_stale()
            if stale_removed:
                log.info(f"Startup LRU cleanup: removed {stale_removed} stale entries")
    except Exception as e:
        log.warning(f"Startup LRU cleanup failed (non-fatal): {e}")

    # Clean up idle sessions on startup
    try:
        from api.auth import cleanup_idle_sessions
        await cleanup_idle_sessions()
    except Exception as e:
        log.warning(f"Idle session cleanup failed (non-fatal): {e}")

    # Store in app state for routers
    app.state.config = config_manager.config
    app.state.config_manager = config_manager

    # Start background task processor
    from services.background_worker import BackgroundWorker
    worker = BackgroundWorker(youtube_service, manager, config_manager, task_queue)
    global background_worker
    background_worker = worker
    asyncio.create_task(worker.process_background_tasks())

    # P3: start the in-process job scheduler ticker (stdlib cron, no APScheduler).
    await worker.start()

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
                    suggestions = await get_channel_mapping_suggestions()
                    for s in suggestions:
                        if s["move_count"] >= 3:
                            config.channel_mappings[s["channel_id"]] = s["playlist_id"]
                            log.info(f"[NIGHTLY] Auto-applied mapping: {s['channel_title']} -> {s['playlist_name']}")
                    await config_manager.save(config)
                    log.info("[NIGHTLY] Auto-apply mappings complete")
            except Exception as e:
                log.error(f"[NIGHTLY] Auto-apply mappings failed: {e}")

    asyncio.create_task(nightly_auto_apply_mappings())

    # Load persisted bulk operations
    try:
        from api.bulk_operations import operations_storage
        await operations_storage.load()
        log.info("Bulk operations loaded from disk")
    except Exception as e:
        log.warning(f"Failed to load bulk operations (non-fatal): {e}")

    # Log registered routes for diagnostics
    # Use getattr to handle both Route and APIRouter/IncludedRouter objects
    log.info("[DIAG] Registered bulk routes: %s", [getattr(r, 'path', None) for r in bulk_router.routes])
    log.info("[DIAG] Registered auth routes: %s", [getattr(r, 'path', None) for r in auth_router.routes])
    log.info("[DIAG] Total app routes: %s", [getattr(r, 'path', None) for r in app.routes])

    log.info("motus.leap started successfully")

    yield

    # Shutdown
    log.info("motus.leap shutting down")
    await shutdown_http_client()


# =============================================================================
# Rate limit handler
# =============================================================================

async def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Handle rate limit exceeded errors."""
    return PlainTextResponse(f"Rate limit exceeded: {exc.detail}", status_code=429)


# =============================================================================
# Create FastAPI app (single instance)
# =============================================================================

app = FastAPI(
    title="motus.leap",
    description="YouTube Playlist Management System",
    version="2.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
# Get allowed origins from environment or use defaults
_render_url = os.environ.get("RENDER_EXTERNAL_URL", "https://tubemanager.onrender.com")
_extra_origins = os.environ.get("EXTRA_ALLOWED_ORIGINS", "").split(",") if os.environ.get("EXTRA_ALLOWED_ORIGINS") else []

# Generic error handler to avoid leaking internal paths/stack traces in production responses
@app.middleware("http")
async def generic_error_handler(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        log.exception("Unhandled exception")
        return JSONResponse(status_code=500, content={"error": "Internal server error"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        _render_url,
        "https://motus-leap.onrender.com",
        'http://localhost:8000',
        'http://localhost:3000',
        'http://127.0.0.1:8000',
        'http://127.0.0.1:3000',
    ] + [o.strip() for o in _extra_origins if o.strip()],
    allow_credentials=True,
    allow_methods=['GET','POST','PUT','DELETE','PATCH'],
    allow_headers=['Authorization','Content-Type','X-CSRF-Token'],
)

# Register routers
app.include_router(bulk_router, tags=["bulk"])
app.include_router(auth_router)


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
        import re
        content = re.sub(r"\?v=\d+", f'?v={deploy_tag}', content)
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


def _sync_worker_youtube_service() -> None:
    """Point the running background worker at the current youtube_service.

    After endpoints (disconnect / save_settings / reset) replace the module
    global ``youtube_service`` with a fresh instance, the worker would
    otherwise keep a stale client reference. The worker's ``youtube_service``
    property reads ``app.youtube_service`` dynamically, so in-flight and
    future tasks use the new credentials.
    """
    if background_worker is not None and youtube_service is not None:
        background_worker._youtube_service = youtube_service








# Mount static files
if not any(getattr(route, "path", "") == "/static" for route in app.routes):
    app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")




# Favicon route — serve favicon.png for /favicon.ico requests
@app.get("/favicon.ico")
async def favicon():
    """Serve favicon to prevent 404."""
    favicon_path = WEB_DIR / "static" / "favicon.png"
    if favicon_path.exists():
        return FileResponse(favicon_path, media_type="image/png")
    # Fallback: blank 1x1 ICO
    return Response(content=b"\x00\x00\x01\x00\x01\x00\x01\x01\x00\x00\x01\x00\x18\x00\x30\x00\x00\x00\x16\x00\x00\x00" + b"\x00" * 50, media_type="image/x-icon")

# H6 FIX: Gzip compression middleware for JSON responses
@app.middleware("http")
async def add_compression(request: Request, call_next):
    """Add gzip compression for JSON responses to reduce bandwidth."""
    response = await call_next(request)
    
    # Only compress JSON responses over 500 bytes
    accept_encoding = request.headers.get("accept-encoding", "")
    if "gzip" in accept_encoding and response.headers.get("content-type", "").startswith("application/json"):
        body = getattr(response, 'body', None)
        if body and len(body) > 500:
            import gzip
            compressed = gzip.compress(body)
            if len(compressed) < len(body):
                from starlette.responses import Response
                response = Response(
                    content=compressed,
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )
                response.headers["Content-Encoding"] = "gzip"
                response.headers["Content-Length"] = str(len(compressed))
    
    # H9/H17 FIX: Add ETag and Cache-Control headers for static assets
    path = request.url.path
    if path.startswith("/static/"):
        # H10 FIX: Versioned assets get long cache, non-versioned get stale-while-revalidate
        if "?v=" in path or any(ext in path for ext in [".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff2"]):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=86400"
        # H9 FIX: Add ETag for conditional requests
        if response.status_code == 200 and hasattr(response, 'body'):
            import hashlib
            etag = hashlib.md5(response.body).hexdigest()
            response.headers["ETag"] = f'"{etag}"'
    
    return response


# --- CSP strictness (motus.leap CSP-hardening workstream) -------------------
# Default behavior is UNCHANGED: every response gets the original CSP that
# allows 'unsafe-inline' (so the 8 legacy pages keep working). Strict mode is
# opt-in per-route via the `X-CSP-Mode: strict` response header AND only takes
# effect when CSP_STRICT is enabled in the environment (default OFF). This lets
# us flip pages one at a time with a kill-switch, with zero risk to the others.
_CSP_STRICT_ENABLED = os.environ.get("CSP_STRICT", "0") == "1"

def _csp_header(strict: bool) -> str:
    if strict:
        # Strict: no 'unsafe-inline'. All JS external + handlers removed on the
        # opted-in routes. Tailwind is served as a static stylesheet.
        return (
            "default-src 'self'; "
            "script-src 'self' https://cdnjs.cloudflare.com; "
            "style-src 'self' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
            "font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
            "img-src 'self' https://i.ytimg.com https://yt3.ggpht.com https://picsum.photos data:; "
            "connect-src 'self' https://www.googleapis.com https://www.youtube.com https://cdnjs.cloudflare.com wss://tubemanager.onrender.com ws: wss:; "
            "frame-ancestors 'none'; "
            "frame-src 'none';"
        )
    # Legacy/permissive (unchanged from before the workstream).
    return (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "font-src 'self' data: https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        "img-src 'self' https://i.ytimg.com https://yt3.ggpht.com https://picsum.photos; "
        "connect-src 'self' https://www.googleapis.com https://www.youtube.com https://cdnjs.cloudflare.com wss://tubemanager.onrender.com ws: wss:; "
        "frame-ancestors 'none'; "
        "frame-src 'none';"
    )


@app.post("/api/csp-report")
async def csp_violation_report(request: Request):
    """Receive CSP violation reports (report-only mode).

    Lets us observe which inline scripts/handlers/styles would break on a
    strict CSP BEFORE enforcing it. Logs the violation; never errors.
    """
    try:
        body = await request.body()
        # Browsers POST either JSON or CSP-report envelope.
        try:
            data = json.loads(body)
        except Exception:
            data = {"raw": body.decode("utf-8", "replace")[:500]}
        report = data.get("csp-report", data) if isinstance(data, dict) else data
        log.warning("CSP violation report: %s", json.dumps(report)[:500])
    except Exception as e:
        log.debug("csp-report parse failed: %s", e)
    return Response(status_code=204)


# Security middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers including strict CSP.

    Strict mode per-route: if the downstream route set `X-CSP-Mode: strict`
    on the response AND CSP_STRICT env is enabled, emit the strict header.
    Otherwise the original permissive CSP is used (unchanged behavior).
    """
    response = await call_next(request)

    # Honor a per-route strict opt-in only when the global kill-switch is on.
    route_wants_strict = response.headers.get("X-CSP-Mode", "").lower() == "strict"
    strict = _CSP_STRICT_ENABLED and route_wants_strict

    csp = _csp_header(strict)
    # When strict is active, also attach a report-only header so any residual
    # inline usage is logged without breaking the page.
    if strict:
        response.headers["Content-Security-Policy-Report-Only"] = (
            _csp_header(strict) + " report-uri /api/csp-report"
        )
    response.headers["Content-Security-Policy"] = csp

    # Additional security headers
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response



# Background task runners have been moved to services/background_worker.py


# API Models
class ActionIn(BaseModel):
    """Action request model."""
    action: str
    payload: dict[str, Any] | None = None


class MaintenanceActionIn(BaseModel):
    """Maintenance Queue action request model.

    Contract (Arwin's frontend calls this):
      action: "keep" | "remove" | "move" | "fix_all"
      type:   "dup" | "misplaced" | "move"
      video_id: str
      playlist_id: str                      (source playlist for remove/move)
      target_playlist_id: str | None        (target for move)
      playlist_item_id: str | None          (if known; otherwise looked up)
    """
    action: str
    type: str | None = None
    video_id: str | None = None
    playlist_id: str | None = None
    target_playlist_id: str | None = None
    playlist_item_id: str | None = None


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


@app.get("/")
async def index():
    """Serve root page - redirects to /auth if not authenticated."""
    return await no_cache_file_response(WEB_DIR / "dashboard.html")

@app.get("/dashboard")
async def dashboard():
    """Dashboard page - available without auth (frontend handles auth check)."""
    return await no_cache_file_response(WEB_DIR / "dashboard.html")


@app.get("/auth")
async def auth():
    """Auth page."""
    return await no_cache_file_response(WEB_DIR / "auth.html")



@app.get("/playlists")
async def playlists():
    """Playlists page."""
    return await no_cache_file_response(WEB_DIR / "playlists.html")


@app.get("/subscriptions")
async def subscriptions():
    """Subscriptions page."""
    return await no_cache_file_response(WEB_DIR / "subscriptions.html")


@app.get("/maintenance")
async def maintenance():
    """Maintenance page."""
    return await no_cache_file_response(WEB_DIR / "maintenance.html")


@app.get("/rules")
async def rules():
    """Rules & Mappings page."""
    return await no_cache_file_response(WEB_DIR / "settings.html")


@app.get("/ai")
@app.get("/ai/providers")
@app.get("/ai/models")
@app.get("/ai/rules")
@app.get("/ai/chat")
@app.get("/ai/jobs")
async def ai_hub():
    """AI Management Hub (P1+P2+P3 wired UI)."""
    return await no_cache_file_response(WEB_DIR / "ai-hub.html")


@app.get("/bulk")
async def bulk():
    """Bulk operations page."""
    return await no_cache_file_response(WEB_DIR / "bulk.html")


@app.get("/settings")
async def settings():
    """Settings page."""
    return await no_cache_file_response(WEB_DIR / "settings.html")


@app.get("/roadmap")
async def roadmap_page() -> Response:
    return await no_cache_file_response(WEB_DIR / "roadmap.html")


@app.get("/test")
async def test_page():
    """Test page."""
    return await no_cache_file_response(WEB_DIR / "test.html")
# Health check
@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


# Single-request endpoint - QUOTA OPTIMIZED
@app.get("/api/youtube/fetch-all", dependencies=[Depends(get_current_user)])
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


@app.get("/api/playlists/names", dependencies=[Depends(get_current_user)])
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


@app.get("/api/youtube/videos", dependencies=[Depends(get_current_user)])
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


@app.get("/api/youtube/duplicates", dependencies=[Depends(get_current_user)])
async def scan_duplicates_endpoint(playlist_id: Optional[str] = None):
    """Scan for duplicate videos in a playlist or all playlists.

    Reads from maintenance.json (populated by the background worker) when
    available. If that cache is absent, returns status="not_ready" rather than
    falling through to a live get_videos()/fetch_all_data() enumeration (which
    would burn the daily YouTube quota). Run Full Playlist Sync to populate it.
    """
    if not youtube_service:
        return {"duplicates": 0, "error": "YouTube service not initialized"}
    
    # Try reading from worker's maintenance.json first
    _data_dir = Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data"))
    maintenance_file = _data_dir / "maintenance.json"
    try:
        if maintenance_file.exists():
            maintenance = json.loads(await asyncio.to_thread(maintenance_file.read_text))
            dup_videos = maintenance.get("duplicated_videos", [])
            return {"duplicates": len(dup_videos), "total_videos": len(dup_videos), "playlist_id": playlist_id, "items": dup_videos}
    except Exception:
        pass

    # QUOTA GUARD: never fall through to a live get_videos()/fetch_all_data()
    # when maintenance.json is absent. That full enumeration is what exhausts
    # the daily YouTube quota on every dashboard reload/poll. Read-only cache
    # only — a full scan is an explicit user action (Full Playlist Sync).
    return {
        "duplicates": 0,
        "items": [],
        "playlist_id": playlist_id,
        "status": "not_ready",
        "error": "maintenance data not available",
    }


@app.get("/api/youtube/misplaced", dependencies=[Depends(get_current_user)])
async def scan_misplaced_endpoint(playlist_id: Optional[str] = None):
    """Scan for misplaced videos based on channel mappings.

    Reads from maintenance.json (populated by the background worker) when
    available. If that cache is absent, returns status="not_ready" rather than
    falling through to a live get_videos()/fetch_all_data() enumeration (which
    would burn the daily YouTube quota). Run Full Playlist Sync to populate it.
    """
    if not youtube_service:
        return {"misplaced": [], "error": "YouTube service not initialized"}
    
    # Try reading from worker's maintenance.json first
    _data_dir = Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data"))
    maintenance_file = _data_dir / "maintenance.json"
    try:
        if maintenance_file.exists():
            maintenance = json.loads(await asyncio.to_thread(maintenance_file.read_text))
            mis_videos = maintenance.get("misplaced_videos", [])
            return {"misplaced": mis_videos, "count": len(mis_videos)}
    except Exception:
        pass
    
    # QUOTA GUARD: never fall through to a live get_videos()/fetch_all_data()
    # when maintenance.json is absent. That full enumeration is what exhausts
    # the daily YouTube quota on every dashboard reload/poll. Read-only cache
    # only — a full scan is an explicit user action (Full Playlist Sync).
    return {
        "misplaced": [],
        "count": 0,
        "status": "not_ready",
    }


# Stats endpoint
@app.get("/api/stats", dependencies=[Depends(get_current_user)])
@limiter.limit("30/minute")
async def stats(request: Request) -> dict[str, Any]:
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
        "last_scan": config.last_scan_time or "Never",
    }


# Playlists endpoint
@app.get("/api/playlists", dependencies=[Depends(get_current_user)])
@limiter.limit("30/minute")
async def api_playlists(request: Request, force_refresh: bool = False) -> dict[str, Any]:
    """Get playlists data."""
    if youtube_service:
        return await youtube_service.list_playlists(force_refresh=force_refresh)
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
        if google_client is None:
            raise HTTPException(status_code=500, detail="OAuth client not available")
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
            cached_all = await youtube_service._cache.get(all_key)
            if cached_all and "playlists" in cached_all:
                for p in cached_all["playlists"]:
                    if p.get("id") == playlist_id:
                        p["title"] = new_title
                        break
                await youtube_service._cache.set(all_key, cached_all)
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
        if google_client is None:
            raise HTTPException(status_code=500, detail="OAuth client not available")
        google_client.playlists().delete(id=playlist_id).execute()
        
        # In-place cache update: remove the deleted playlist from caches
        config = config_manager.config
        user_id = hashlib.sha256((config.oauth.access_token or "").encode()).hexdigest()[:16]
        all_key = f"all_data_{user_id}"
        # Remove from memory cache
        if youtube_service._cache:
            cached_all = await youtube_service._cache.get(all_key)
            if cached_all and "playlists" in cached_all:
                cached_all["playlists"] = [p for p in cached_all["playlists"] if p.get("id") != playlist_id]
                stats = cached_all.get("stats") or {}
                stats["total_playlists"] = len(cached_all["playlists"])
                cached_all["stats"] = stats
                await youtube_service._cache.set(all_key, cached_all)
        
        return {"status": "success", "message": "Playlist deleted successfully"}
    except Exception as e:
        log.error(f"Error deleting playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/api/youtube/playlists/create", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def create_playlist_endpoint(body: dict):
    """Create a new YouTube playlist."""
    if not youtube_service:
        raise HTTPException(status_code=500, detail="YouTube service not initialized")
    yt_client = youtube_service.get_client(require_oauth=True)
    if not yt_client:
        raise HTTPException(status_code=401, detail="OAuth client not available")
    title = body.get("title", "New Playlist")
    description = body.get("description", "")
    privacy = body.get("privacy", "private")
    result = await asyncio.to_thread(yt_client.create_playlist, title=title, description=description, privacy_status=privacy)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/subscriptions/subscribe", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def subscribe_channel(body: dict):
    """Subscribe to a YouTube channel (accepts channel ID, @handle, or user URL)."""
    if not youtube_service:
        raise HTTPException(status_code=500, detail="YouTube service not initialized")
    yt_client = youtube_service.get_client(require_oauth=True)
    if not yt_client:
        raise HTTPException(status_code=401, detail="OAuth client not available")
    query = (body.get("channel_id") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="channel_id is required")
    # Accept bare ID, channel/ID, @handle, user/URL, or youtu.be URL
    m = re.search(r"channel\/([A-Za-z0-9_-]+)", query)
    if not m:
        m = re.search(r"@([A-Za-z0-9._-]+)", query)
    if not m:
        m = re.search(r"user\/([A-Za-z0-9._-]+)", query)
    if not m:
        m = re.search(r"^([A-Za-z0-9_-]{20,})$", query)
    target = m.group(1) if m else query
    # Let YouTubeClient.subscribe_to_channel handle it; on 400/not found, surface error
    result = await asyncio.to_thread(yt_client.subscribe_to_channel, target)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    await youtube_service._cache.delete(f"subscriptions_{youtube_service._get_user_id()}")
    return result


@app.post("/api/subscriptions/unsubscribe", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def unsubscribe_channel(body: dict):
    """Unsubscribe from a YouTube channel."""
    if not youtube_service:
        raise HTTPException(status_code=500, detail="YouTube service not initialized")
    yt_client = youtube_service.get_client(require_oauth=True)
    if not yt_client:
        raise HTTPException(status_code=401, detail="OAuth client not available")
    subscription_id = body.get("subscription_id")
    if not subscription_id:
        raise HTTPException(status_code=400, detail="subscription_id is required")
    try:
        await asyncio.to_thread(lambda: yt_client._get_client(require_oauth=True).subscriptions().delete(id=subscription_id).execute())
        await youtube_service._cache.delete(f"subscriptions_{youtube_service._get_user_id()}")
        return {"status": "success"}
    except Exception as e:
        log.error(f"Unsubscribe failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

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
        if google_client is None:
            raise HTTPException(status_code=500, detail="OAuth client not available")
        
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
            await youtube_service._cache_invalidate_playlist(playlist_id)
            
        return {"status": "success", "message": "Video removed from playlist"}
    except Exception as e:
        log.error(f"Error removing video from playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Subscriptions endpoint
@app.get("/api/subscriptions", dependencies=[Depends(get_current_user)])
async def api_subscriptions() -> dict[str, Any]:
    """Get subscriptions data."""
    if youtube_service:
        result = await youtube_service.list_subscriptions()
        # The list_subscriptions method returns {"channels": [], "total_subscriptions": N}
        # Ensure we return only the "channels" list or an empty list if an error occurred
        return {"channels": result.get("channels", []), "error": result.get("error")}
    return {"channels": [], "error": "YouTube service not available"}


# Maintenance endpoint
@app.get("/api/maintenance", dependencies=[Depends(get_current_user)])
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


def _load_maintenance_data() -> dict[str, Any]:
    """Load maintenance.json (scan output). Returns empty-shape dict on miss."""
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
    }


def _maintenance_items_by_type(maintenance: dict[str, Any], item_type: str) -> list[dict[str, Any]]:
    """Return the list of maintenance records for a given type key."""
    if item_type == "dup":
        return maintenance.get("duplicated_videos", [])
    if item_type == "misplaced":
        return maintenance.get("misplaced_videos", [])
    if item_type == "move":
        return maintenance.get("move_from_x_to_y", [])
    return []


async def _maintenance_resolve_item_id(
    yt_client, playlist_id: str, video_id: str, supplied_item_id: str | None
) -> str | None:
    """Resolve a playlistItem ID for delete/move.

    If the caller already supplied a playlist_item_id, use it directly.
    Otherwise look it up via list_videos/find_playlist_item_id (maintenance
    records do NOT store playlistItem IDs).
    """
    if supplied_item_id:
        return supplied_item_id
    # find_playlist_item_id iterates pages internally and returns the id or None.
    return yt_client.find_playlist_item_id(playlist_id, video_id)


async def _maintenance_apply_one(
    yt_client,
    action: str,
    item_type: str,
    record: dict[str, Any],
    playlist_id: str | None,
    target_playlist_id: str | None,
    playlist_item_id: str | None,
    video_id: str | None,
) -> dict[str, Any]:
    """Apply a single action to a single maintenance record.

    Returns a small result dict describing success/failure. Does NOT raise for
    YouTube errors — callers aggregate failures for the fix_all summary.
    """
    # Normalise inputs: prefer explicit args, else pull from the record shape.
    video_id = video_id or record.get("video_id")
    if not playlist_id:
        playlist_id = record.get("current_playlist_id") or record.get("source_playlist_id")
        # dup records store copies as playlists: [{id,title}] — use the first copy.
        if not playlist_id and item_type == "dup":
            _pls = record.get("playlists") or []
            if _pls:
                playlist_id = (_pls[0].get("id") if isinstance(_pls[0], dict) else None) or _pls[0]

    if action == "keep":
        # No-op. Optionally could prune the record from maintenance.json, but
        # keeping it simple: mark resolved, delete nothing.
        return {"status": "ok", "action": "keep", "video_id": video_id,
                "message": "No-op: item kept"}

    if not video_id:
        return {"status": "error", "action": action, "error": "missing video_id"}

    if action == "remove":
        if not playlist_id:
            return {"status": "error", "action": "remove", "error": "missing playlist_id"}
        item_id = await _maintenance_resolve_item_id(
            yt_client, playlist_id, video_id, playlist_item_id
        )
        if not item_id:
            return {"status": "error", "action": "remove",
                    "error": f"playlistItem id not found for video {video_id} in playlist {playlist_id}"}
        yt_client.remove_video_from_playlist_item(item_id)
        # Invalidate cache so the change shows immediately.
        try:
            await youtube_service._cache_invalidate_playlist(playlist_id)
        except Exception:
            pass
        return {"status": "ok", "action": "remove", "video_id": video_id,
                "playlist_item_id": item_id}

    if action == "move":
        target_playlist_id = target_playlist_id or record.get(
            "mapped_playlist_id"
        ) or record.get("target_playlist_id")
        if not playlist_id:
            return {"status": "error", "action": "move", "error": "missing source playlist_id"}
        if not target_playlist_id:
            return {"status": "error", "action": "move", "error": "missing target_playlist_id"}
        # 1 delete (source) + 1 insert (target) = 2 quota units.
        item_id = await _maintenance_resolve_item_id(
            yt_client, playlist_id, video_id, playlist_item_id
        )
        if not item_id:
            return {"status": "error", "action": "move",
                    "error": f"playlistItem id not found for video {video_id} in playlist {playlist_id}"}
        yt_client.remove_video_from_playlist_item(item_id)
        yt_client.add_video_to_playlist(target_playlist_id, video_id)
        for pid in (playlist_id, target_playlist_id):
            try:
                await youtube_service._cache_invalidate_playlist(pid)
            except Exception:
                pass
        return {"status": "ok", "action": "move", "video_id": video_id,
                "source": playlist_id, "target": target_playlist_id}

    return {"status": "error", "action": action, "error": f"unknown action '{action}'"}


# Maintenance action endpoint
@app.post("/api/maintenance/action", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def api_maintenance_action(payload: MaintenanceActionIn) -> dict[str, Any]:
    """Apply a Maintenance Queue action (keep/remove/move/fix_all).

    Body JSON (see MaintenanceActionIn):
      { "action": "keep"|"remove"|"move"|"fix_all",
        "type": "dup"|"misplaced"|"move",
        "video_id": str, "playlist_id": str,
        "target_playlist_id": str|null, "playlist_item_id": str|null }
    """
    action = (payload.action or "").lower()
    item_type = (payload.type or "").lower()

    if action not in ("keep", "remove", "move", "fix_all"):
        return {"status": "error", "error": f"invalid action '{payload.action}'"}
    if action != "fix_all" and item_type not in ("dup", "misplaced", "move"):
        return {"status": "error", "error": f"invalid or missing type '{payload.type}'"}

    # Defense-in-depth: validate ID shapes (Sheldon's hardening note).
    if payload.video_id and not validate_video_id(payload.video_id):
        return {"status": "error", "error": "invalid video_id format"}
    if payload.playlist_id and not validate_playlist_id(payload.playlist_id):
        return {"status": "error", "error": "invalid playlist_id format"}
    if payload.target_playlist_id and not validate_playlist_id(payload.target_playlist_id):
        return {"status": "error", "error": "invalid target_playlist_id format"}
    if payload.playlist_item_id and not validate_playlist_id(payload.playlist_item_id):
        return {"status": "error", "error": "invalid playlist_item_id format"}

    if youtube_service is None:
        return {"status": "error", "error": "YouTube service not initialized"}

    yt_client = youtube_service.get_client(require_oauth=True)
    if yt_client is None:
        return {"status": "error", "error": "OAuth client not available"}

    # Single-item actions
    if action != "fix_all":
        try:
            result = await _maintenance_apply_one(
                yt_client,
                action=action,
                item_type=item_type,
                record={},
                playlist_id=payload.playlist_id,
                target_playlist_id=payload.target_playlist_id,
                playlist_item_id=payload.playlist_item_id,
                video_id=payload.video_id,
            )
            if result.get("status") == "ok":
                # Drop the inner "status":"ok" so it doesn't overwrite "success".
                clean = {k: v for k, v in result.items() if k != "status"}
                return {"status": "success", **clean}
            return result  # already {"status": "error", ...}
        except Exception as e:
            log.error(f"Maintenance action '{action}' failed: {e}")
            return {"status": "error", "error": str(e)}

    # fix_all: apply the given action to every record of the given type.
    maintenance = _load_maintenance_data()
    records = _maintenance_items_by_type(maintenance, item_type)
    processed = 0
    succeeded = 0
    failed = 0
    errors = []
    for rec in records:
        # fix_all is an aggregate of a real per-item op. Map it to that op:
        #   - misplaced/move → remove (delete the item from its current/source playlist;
        #     there is no single insert target for "fix all" on these types).
        #   - dup → remove each *non-primary* copy (keep playlists[0], the primary).
        if item_type == "dup":
            sub_action = "remove"
            copy_playlists = rec.get("playlists", []) or []
            for idx, cp in enumerate(copy_playlists):
                cp_id = cp.get("id") if isinstance(cp, dict) else None
                if not cp_id:
                    continue
                if idx == 0:
                    continue  # keep the primary copy
                processed += 1
                try:
                    res = await _maintenance_apply_one(
                        yt_client,
                        action=sub_action,
                        item_type=item_type,
                        record=rec,
                        playlist_id=cp_id,
                        target_playlist_id=None,
                        playlist_item_id=None,
                        video_id=None,
                    )
                    if res.get("status") == "ok":
                        succeeded += 1
                    else:
                        failed += 1
                        errors.append(res.get("error", "unknown error"))
                except Exception as e:
                    failed += 1
                    errors.append(str(e))
            continue
        # misplaced / move: fix_all deletes each item from its current/source playlist.
        sub_action = "remove"
        processed += 1
        try:
            res = await _maintenance_apply_one(
                yt_client,
                action=sub_action,
                item_type=item_type,
                record=rec,
                playlist_id=None,
                target_playlist_id=None,
                playlist_item_id=None,
                video_id=None,
            )
            if res.get("status") == "ok":
                succeeded += 1
            else:
                failed += 1
                errors.append(res.get("error", "unknown error"))
        except Exception as e:
            failed += 1
            errors.append(str(e))
            continue
    return {
        "status": "success" if failed == 0 else "partial",
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
        "errors": errors[:25],
    }


# Mappings endpoints
def _norm_name(s: str) -> str:
    """Aggressively normalize a channel/playlist display name for matching.

    Exported subscription names frequently differ from the live API title by
    casing, unicode form, emoji, punctuation, or collapsed whitespace. We
    normalize to a canonical key so near-identical names still match:
      - NFKC unicode normalization (full-width -> ascii, etc.)
      - lowercase
      - strip emoji / symbols / punctuation
      - collapse all whitespace runs to a single space, then remove spaces
    """
    import unicodedata as _ud
    if not s:
        return ""
    s = _ud.normalize("NFKC", s).lower().strip()
    out = []
    for ch in s:
        cat = _ud.category(ch)
        # keep letters (L*) and numbers (N*); drop marks, punctuation, symbols
        if cat[0] in ("L", "N"):
            out.append(ch)
    return "".join(out)


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


@app.get("/api/mappings", dependencies=[Depends(get_current_user)])
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
    
    return {"mappings": _normalize_mappings(formatted), "metadata": config.channel_metadata or {}}


@app.post("/api/channels/titles", dependencies=[Depends(get_current_user), Depends(verify_origin)])
@limiter.limit("20/minute")
async def api_channel_titles(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    """Batch-resolve channel IDs -> {title, thumbnail} via channels.list.

    Used by the mappings UI to show real channel names for Auto-mapped
    channels that aren't in the user's subscriptions (so they can be
    reviewed/corrected instead of showing raw UC... IDs).
    """
    channel_ids = body.get("channel_ids") or []
    if not isinstance(channel_ids, list):
        channel_ids = [channel_ids]
    # De-dupe, keep valid-looking UC IDs, cap to avoid abuse.
    seen = set()
    cleaned = []
    for cid in channel_ids:
        cid = (cid or "").strip()
        if cid and cid not in seen and cid.startswith("UC") and len(cid) > 10:
            seen.add(cid)
            cleaned.append(cid)
    cleaned = cleaned[:1000]

    result: dict[str, Any] = {}
    if not cleaned:
        return {"titles": result}

    yt_client = youtube_service.get_client(require_oauth=True)
    if not yt_client:
        raise HTTPException(status_code=401, detail="OAuth client not available")
    try:
        google_client = yt_client._get_client(require_oauth=True)
        if google_client is None:
            raise HTTPException(status_code=401, detail="OAuth client not available")
    except Exception as e:
        log.error(f"Error getting YouTube client for channel titles: {e}")
        raise HTTPException(status_code=401, detail="OAuth client not available")

    # channels.list accepts up to 50 ids per call.
    for i in range(0, len(cleaned), 50):
        batch = cleaned[i:i + 50]
        try:
            resp = google_client.channels().list(
                part="snippet", id=",".join(batch), maxResults=50
            ).execute()
            for item in resp.get("items", []):
                cid = item["id"]
                sn = item.get("snippet", {})
                thumbs = sn.get("thumbnails", {})
                thumb = (thumbs.get("default") or thumbs.get("medium") or {}).get("url", "")
                result[cid] = {"title": sn.get("title", ""), "thumbnail": thumb}
        except Exception as e:
            log.error(f"Error resolving channel titles batch {i}: {e}")
            # Leave unresolved IDs out; frontend keeps the raw ID fallback.

    return {"titles": result}


@app.post("/api/mappings", dependencies=[Depends(get_current_user), Depends(verify_origin)])
@limiter.limit("30/minute")  # Rate limit: 30 save operations per minute
async def save_mappings(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    """Save channel mappings."""
    mappings = _normalize_mappings(_extract_mapping_items(body))
    config = config_manager.config
    config.channel_mappings = _serialize_mappings(mappings)
    await config_manager.save(config)
    return {"message": "Mappings saved", "mappings": mappings}


@app.post("/api/channels/metadata", dependencies=[Depends(get_current_user), Depends(verify_origin)])
@limiter.limit("10/minute")
async def save_channel_metadata(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    """Persist resolved channel metadata (name/avatar) keyed by channel ID.

    Merged losslessly into existing config.channel_metadata (never clobbers
    other keys; save() also preserves mappings + credentials). Keeps channel
    names on disk so the UI can render them immediately after a reload without
    re-hitting the YouTube API.
    """
    incoming = body.get("metadata") or {}
    if not isinstance(incoming, dict):
        raise HTTPException(status_code=422, detail="metadata must be an object")

    # Keep only well-formed entries.
    clean = {}
    for cid, info in incoming.items():
        if not isinstance(cid, str) or not cid.startswith("UC"):
            continue
        if isinstance(info, dict) and info.get("title"):
            clean[cid] = {
                "title": str(info.get("title"))[:200],
                "thumbnail": str(info.get("thumbnail", ""))[:500],
            }
    if len(clean) > 2000:
        # Cap to bound disk growth; keep the first N.
        clean = dict(list(clean.items())[:2000])

    config = config_manager.config
    merged = dict(config.channel_metadata or {})
    merged.update(clean)
    config.channel_metadata = merged
    await config_manager.save(config)
    return {"status": "success", "count": len(merged)}


@app.get("/api/channels/metadata", dependencies=[Depends(get_current_user)])
@limiter.limit("30/minute")
async def get_channel_metadata(request: Request) -> dict[str, Any]:
    """Read-only: return persisted channel metadata (name/avatar) keyed by ID.

    Clients use this to render real channel names everywhere (dashboard,
    maintenance queue, bulk) without re-hitting the YouTube API — purely a
    disk read of config.channel_metadata.
    """
    return {"metadata": config_manager.config.channel_metadata or {}}


@app.post("/api/mappings/import", dependencies=[Depends(get_current_user), Depends(verify_origin)])
@limiter.limit("10/minute")
async def import_mappings(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    """Import channel->playlist mappings by NAME, resolving against the
    user's live YouTube playlists + subscriptions (name->ID) using the
    app's authenticated client. No raw credentials leave the browser."""
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="No mapping text provided")

    if not youtube_service:
        raise HTTPException(status_code=503, detail="YouTube service unavailable")

    # Build name->ID lookups from the authenticated account.
    # Playlists: title -> id (from list_playlists).
    # Channels: title -> id. subscriptions.list snippet carries BOTH the
    # channel title and channelId directly, so read it straight from the raw
    # items (the enriched list_subscriptions() can drop titles if the
    # secondary channels.list call fails).
    try:
        pl_data = await youtube_service.list_playlists(force_refresh=True)
        client = youtube_service.get_client(require_oauth=True)
        if not client:
            raise HTTPException(status_code=503, detail="YouTube not connected. OAuth required.")
        raw_subs = await youtube_service._fetch_all_paginated(
            lambda mr, pt: client.list_mine_subscriptions(max_results=mr, page_token=pt),
            max_results=50,
            max_items=10000,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to read account data: {e}")

    playlist_by_name = {
        (p.get("title") or "").strip().lower(): p.get("id")
        for p in (pl_data.get("playlists") or [])
        if p.get("id")
    }
    # Fuzzy (normalized) fallback index: canonical-name -> id.
    playlist_by_norm: dict[str, str] = {}
    for p in (pl_data.get("playlists") or []):
        if p.get("id"):
            playlist_by_norm.setdefault(_norm_name(p.get("title") or ""), p["id"])

    channel_by_name: dict[str, str] = {}
    channel_by_norm: dict[str, str] = {}
    for sub in raw_subs:
        snip = (sub.get("snippet") or {})
        res = snip.get("resourceId") or {}
        cid = res.get("channelId") or ""
        title = (snip.get("title") or "").strip()
        if cid and title:
            channel_by_name.setdefault(title.lower(), cid)
            channel_by_norm.setdefault(_norm_name(title), cid)

    # Second pass: many channel names are actually YouTube HANDLES (single
    # tokens like "0musa07", "2CELLOS") that aren't in the user's
    # subscriptions. Resolve those cheaply via channels.list?forHandle
    # (API-key client, ~1 quota unit, no OAuth). Only resolve names not
    # already found via subscriptions to conserve quota.
    try:
        candidate_names = [
            ln.strip().split(" : ")[0].split(":")[0].split("-")[0].strip()
            for ln in text.splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        handle_candidates = [
            n for n in candidate_names
            if n and " " not in n and n.lower() not in channel_by_name
        ]
        if handle_candidates:
            resolved_handles = await youtube_service.resolve_channel_handles(handle_candidates)
            for h, cid in resolved_handles.items():
                channel_by_name.setdefault(h, cid)  # match by exact handle text
                channel_by_name.setdefault("@" + h, cid)  # and with leading @
    except Exception as e:
        log.warning(f"[import_mappings] handle fallback skipped: {e}")

    resolved: dict[str, str] = {}
    unmatched_channels: list[str] = []
    unmatched_playlists: list[str] = []
    skipped: int = 0

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # Accept "channel : playlist" or "channel - playlist"
        if " : " in line:
            ch_name, pl_name = line.split(" : ", 1)
        elif ":" in line:
            ch_name, pl_name = line.split(":", 1)
        elif "-" in line:
            ch_name, pl_name = line.split("-", 1)
        else:
            skipped += 1
            continue
        ch_name = ch_name.strip()
        pl_name = pl_name.strip()
        if not ch_name or not pl_name:
            skipped += 1
            continue
        ch_key = ch_name.lower()
        pl_key = pl_name.lower()
        # Channel: exact (lower) -> handle text -> fuzzy normalized.
        cid = (
            channel_by_name.get(ch_key)
            or channel_by_name.get(ch_key.lstrip("@"))
            or channel_by_name.get("@" + ch_key.lstrip("@"))
            or channel_by_norm.get(_norm_name(ch_name))
        )
        # Playlist: exact (lower) -> fuzzy normalized.
        pid = playlist_by_name.get(pl_key) or playlist_by_norm.get(_norm_name(pl_name))
        if not cid:
            unmatched_channels.append(ch_name)
            continue
        if not pid:
            unmatched_playlists.append(pl_name)
            continue
        resolved[cid] = pid

    # Merge into existing mappings (keep prior entries not in this import).
    config = config_manager.config
    existing = config.channel_mappings or {}
    if isinstance(existing, list):
        existing = _serialize_mappings(_normalize_mappings(existing))
    merged = dict(existing)
    merged.update(resolved)
    config.channel_mappings = merged
    await config_manager.save(config)

    return {
        "message": f"Imported {len(resolved)} mappings",
        "imported": len(resolved),
        "skipped": skipped,
        "unmatched_channels": unmatched_channels,
        "unmatched_playlists": unmatched_playlists,
        "total_mappings": len(merged),
        "debug": {
            "subs_fetched": len(raw_subs),
            "channels_indexed": len(channel_by_name),
            "playlists_fetched": len(playlist_by_name),
            "sample_sub_titles": sorted(channel_by_name.keys())[:15],
            "sample_playlist_titles": sorted(playlist_by_name.keys())[:15],
        },
    }


@app.post("/api/mappings/from-playlists", dependencies=[Depends(get_current_user), Depends(verify_origin)])
@limiter.limit("5/minute")
async def map_from_playlists(request: Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Derive channel->playlist mappings from the videos already in each
    playlist (majority vote per channel). Resolves non-subscribed channels
    from ground-truth data — no search-API quota needed.

    body: {"apply": bool}. apply=false (default) previews; apply=true merges
    the derived mappings into config (existing entries win on conflict unless
    "overwrite": true).
    """
    if not youtube_service:
        raise HTTPException(status_code=503, detail="YouTube service unavailable")
    body = body or {}
    apply = bool(body.get("apply"))
    overwrite = bool(body.get("overwrite"))

    result = await youtube_service.map_channels_from_playlist_contents()
    if result.get("error"):
        raise HTTPException(status_code=503, detail=result["error"])

    derived: dict[str, str] = result["mapping"]
    config = config_manager.config
    existing = config.channel_mappings or {}
    if isinstance(existing, list):
        existing = _serialize_mappings(_normalize_mappings(existing))

    new_count = sum(1 for cid in derived if cid not in existing)
    conflicts = [
        {"channel_id": cid, "existing": existing[cid], "derived": derived[cid], "channel": result["channel_titles"].get(cid, cid)}
        for cid in derived
        if cid in existing and existing[cid] != derived[cid]
    ]

    applied = 0
    if apply:
        merged = dict(existing)
        for cid, pid in derived.items():
            if overwrite or cid not in merged:
                if merged.get(cid) != pid:
                    applied += 1
                merged[cid] = pid
        config.channel_mappings = merged
        # Persist the free channel titles we already harvested from
        # playlistItems.list (videoOwnerChannelTitle) — no extra quota. This
        # is how non-subscribed channels get real names without channels.list.
        titles = result.get("channel_titles") or {}
        if titles:
            md = dict(config.channel_metadata or {})
            for cid, t in titles.items():
                if t and t != cid and not md.get(cid, {}).get("title"):
                    md[cid] = {"title": t, "thumbnail": md.get(cid, {}).get("thumbnail", "")}
            config.channel_metadata = md
        await config_manager.save(config)

    return {
        "applied": applied,
        "would_add": new_count,
        "conflicts": conflicts,
        "playlists_scanned": result["playlists_scanned"],
        "videos_scanned": result["videos_scanned"],
        "channels_found": len(derived),
        "total_mappings": len(config.channel_mappings or {}),
    }


@app.post("/api/channels/backfill-names", dependencies=[Depends(get_current_user), Depends(verify_origin)])
@limiter.limit("3/minute")
async def backfill_channel_names(request: Request) -> dict[str, Any]:
    """Harvest real channel names from already-cached playlist contents.

    Reads video snippets (videoOwnerChannelTitle) from the disk-cached
    all_data.json. To survive OAuth token rotation (which changes the cache
    dir hash), this also scans sibling user dirs for an all_data.json that
    actually contains videos. Returns diagnostics so the live box reports
    ground truth instead of a silent 0.
    """
    if not youtube_service:
        raise HTTPException(status_code=503, detail="YouTube service unavailable")

    # ---- DIAGNOSTIC: what is actually on disk? ----
    import glob, os
    diag: dict[str, Any] = {}
    try:
        base = youtube_service._user_data_dir
        diag["user_id"] = youtube_service._get_user_id()
        diag["cache_dir"] = str(base)
        diag["cache_dir_exists"] = await asyncio.to_thread(base.exists)
        # Scan ALL sibling user dirs for any all_data.json with videos.
        parent = base.parent
        candidates = []
        if await asyncio.to_thread(parent.exists):
            for d in await asyncio.to_thread(lambda: list(parent.iterdir())):
                ad = d / "all_data.json"
                if await asyncio.to_thread(ad.exists):
                    try:
                        data = json.loads(await asyncio.to_thread(ad.read_text))
                        n_vids = len(data.get("videos", []) or [])
                        candidates.append({"dir": str(d), "videos": n_vids})
                    except Exception:
                        candidates.append({"dir": str(d), "videos": -1})
        diag["all_data_candidates"] = candidates
    except Exception as e:  # noqa: BLE001
        diag["error"] = str(e)

    result = await youtube_service.map_channels_from_playlist_contents()
    if result.get("error"):
        raise HTTPException(status_code=503, detail=result["error"])
    titles = dict(result.get("channel_titles") or {})
    thumbs = {}

    # Zero-quota avatar fallback: harvest a representative VIDEO thumbnail
    # per channel from the cached playlist data (all_data.json). This is the
    # only free image available for non-subscribed mapped channels; combined
    # with the real channel logo from subscriptions.list (free, subscribers
    # only) it replaces every monogram circle with a real picture. A video
    # poster is not the channel logo, but it is a real image and beats a
    # letter — and channels.list (the only true-logo source) is quota-blocked.
    def _harvest(data):
        t, th = {}, {}
        for v in data.get("videos", []) or []:
            snip = v.get("snippet", {}) or {}
            cid = v.get("channel_id") or snip.get("videoOwnerChannelId") or snip.get("channelId")
            if not cid:
                continue
            nm = v.get("channel_title") or snip.get("videoOwnerChannelTitle") or snip.get("channelTitle")
            if nm:
                t.setdefault(cid, nm)
            thb = v.get("thumbnail") or _best_thumbnail(snip.get("thumbnails"))
            if thb:
                th.setdefault(cid, thb)
            else:
                vid = (
                    v.get("video_id")
                    or (v.get("contentDetails", {}) or {}).get("videoId")
                    or next((val for key, val in v.items() if isinstance(val, str) and YOUTUBE_VIDEO_ID_RE.match(val)), "")
                )
                if vid:
                    th.setdefault(cid, f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg")
        return t, th

    # Primary cache (same dir map_channels reads from).
    primary_path = base / "all_data.json"
    try:
        ad = json.loads(await asyncio.to_thread(primary_path.read_text))
        pt, pth = _harvest(ad)
        for k, v in pt.items():
            titles.setdefault(k, v)
        for k, v in pth.items():
            thumbs.setdefault(k, v)
        diag["primary_cache_read"] = "ok"
    except Exception as e:  # noqa: BLE001
        diag["primary_cache_read"] = f"error: {e}"
        pass

    # Merge orphan siblings AFTER primary so setdefault wins.
    def _count_and_harvest_files(paths):
        t = {}
        th = {}
        total = 0
        for p in paths:
            try:
                data = json.loads(Path(p).read_text())
                total += len(data.get("videos", []) or [])
                ft, fth = _harvest(data)
                for k, v in ft.items():
                    t.setdefault(k, v)
                for k, v in fth.items():
                    th.setdefault(k, v)
            except Exception:
                pass
        return t, th, total

    primary_path = str(base / "all_data.json")
    pt2, pth2, primary_total = await asyncio.to_thread(_count_and_harvest_files, [primary_path])
    titles.update(pt2)
    thumbs.update(pth2)

    # Orphaned sibling caches (token-rotation recovery) — merge ALL of them.
    orphan_paths = []
    for cand in diag.get("all_data_candidates", []):
        if cand.get("videos", 0) > 0:
            orphan_paths.append(str(Path(cand["dir"]) / "all_data.json"))
    ot2, oth2, orphan_total = await asyncio.to_thread(_count_and_harvest_files, orphan_paths)
    titles.update(ot2)
    thumbs.update(oth2)

    thumbs_applied = 0
    config = config_manager.config
    md = dict(config.channel_metadata or {})
    added = 0
    for cid, t in titles.items():
        if not t or t == cid:
            continue
        existing = md.get(cid, {}) or {}
        new_title = not existing.get("title")
        new_thumb = not existing.get("thumbnail") and thumbs.get(cid)
        if new_title or new_thumb:
            md[cid] = {
                "title": t,
                "thumbnail": existing.get("thumbnail") or thumbs.get(cid, ""),
            }
            if new_title:
                added += 1
            if new_thumb:
                thumbs_applied += 1
    config.channel_metadata = md
    await config_manager.save(config)
    all_data_scanned = primary_total + orphan_total
    log.info(
        f"[backfill-names] playlists_scanned={result.get('playlists_scanned')} "
        f"videos_scanned={result.get('videos_scanned')} "
        f"all_data_scanned={all_data_scanned} "
        f"titles_found={len(titles)} names_added={added} thumbs_applied={thumbs_applied} "
        f"total_named={len(md)} diag={diag}"
    )
    return {
        "names_added": added,
        "total_named": len(md),
        "playlists_scanned": result.get("playlists_scanned", 0),
        "videos_scanned": result.get("videos_scanned", 0),
        "all_data_scanned": all_data_scanned,
        "titles_found": len(titles),
        "thumbs_applied": thumbs_applied,
        "thumbs_found": len(thumbs),
        "diagnostics": diag,
    }


# Playlist detail page
@app.get("/playlist/{playlist_id}")
async def playlist_detail(playlist_id: str):
    """Serve playlist detail page."""
    return await no_cache_file_response(WEB_DIR / "playlist.html")


@app.get("/api/actions/status", dependencies=[Depends(get_current_user)])
async def action_status():
    """Get action status."""
    return {"queue_size": task_queue.qsize(), "running": worker.background_tasks_running if worker else False}


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



@app.get("/api/youtube/status", dependencies=[Depends(get_current_user)])
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
    _sync_worker_youtube_service()
    return {"message": "YouTube OAuth disconnected. Re-authorize in Settings to reconnect."}


class SettingsIn(BaseModel):
    """Settings input model."""
    youtube_api_key: str | None = None
    oauth_client_id: str | None = None
    oauth_client_secret: str | None = None
    # Raw Google client_secret.json (web or installed OAuth client). When
    # supplied we extract client_id + client_secret automatically so the user
    # never has to hand-copy them out of the downloaded file.
    oauth_client_secret_json: str | None = None
    default_privacy: str | None = None
    scan_interval: str | None = None
    max_concurrent: int | None = None
    auto_sort: bool | None = None
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


@app.get("/api/settings", dependencies=[Depends(get_current_user)])
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


def parse_google_client_secret_json(raw: str) -> tuple[str, str]:
    """Extract (client_id, client_secret) from a Google OAuth client_secret.json.

    Handles both the ``web`` and ``installed`` client shapes Google emits.
    Returns ("", "") if extraction fails; callers should surface a clear error.
    """
    import json
    raw = (raw or "").strip()
    if not raw:
        return "", ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "", ""
    # Installed/web clients nest creds under either key.
    creds = data.get("web") or data.get("installed") or {}
    client_id = (creds.get("client_id") or "").strip()
    client_secret = (creds.get("client_secret") or "").strip()
    return client_id, client_secret


@app.post("/api/settings", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def save_settings(body: SettingsIn):
    """Save settings."""
    config = config_manager.config

    # Auto-extract client_id/secret from an uploaded Google client_secret.json.
    if body.oauth_client_secret_json:
        cid, csec = parse_google_client_secret_json(body.oauth_client_secret_json)
        if not cid or not csec:
            return {"error": "Could not parse client_id/client_secret from the provided client_secret.json"}, 400
        # Prefer the JSON-derived values, but let explicit fields override them.
        if not body.oauth_client_id:
            body.oauth_client_id = cid
        if not body.oauth_client_secret:
            body.oauth_client_secret = csec

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
    _sync_worker_youtube_service()

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

    # P1: resolve the active provider connection. Fall back to legacy scalars
    # for back-compat (e.g. if no providers list yet but legacy fields set).
    active = _get_active_provider(config)
    if active is not None:
        provider = active.type
        api_key = _secret_val(active.api_key)
        prompt = config.ai_classification_prompt
        custom_endpoint = active.base_url
        custom_model = active.selected_models[0] if active.selected_models else ""
        base_url = active.base_url
        selected_models = active.selected_models
    else:
        # Legacy single-provider path (pre-migration config).
        provider = config.ai_provider
        api_key = _secret_val(config.ai_api_key)
        prompt = config.ai_classification_prompt
        custom_endpoint = config.ai_custom_endpoint
        custom_model = config.ai_custom_model
        base_url = ""
        selected_models = None

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

    # Bounded concurrency: classify all videos at once instead of serially, but
    # cap in-flight calls with a semaphore so a large batch can't open hundreds of
    # simultaneous HTTP connections / hammer the LLM provider. Results stay in
    # input order with the exact per-video (matched_playlist, error) shape the
    # frontend expects.
    sem = asyncio.Semaphore(5)

    async def _classify_one(vid, meta):
        async with sem:
            try:
                title = meta.get("title", "") if meta else ""
                channel = meta.get("channel", "") if meta else ""
                description = meta.get("description", "") if meta else ""
                matched_playlist, error = await classify_video(
                    title=title, channel=channel, description=description,
                    playlists=playlists, provider=provider, api_key=api_key,
                    prompt_template=prompt,
                    custom_endpoint=custom_endpoint, custom_model=custom_model,
                    base_url=base_url, selected_models=selected_models,
                )
                result = {
                    "video_id": vid,
                    "title": title,
                    "channel": channel,
                    "matched_playlist": matched_playlist,
                }
                if error:
                    result["error"] = error
                return result
            except Exception as e:
                return {"video_id": vid, "error": str(e)}

    results = await asyncio.gather(
        *(_classify_one(vid, (body.metadata[i] if body.metadata and i < len(body.metadata) else None))
          for i, vid in enumerate(body.video_ids))
    )

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
    await record_move(
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


@app.get("/api/ai/suggestions", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_get_suggestions():
    """Get channel mapping suggestions from training memory."""
    from services.ai_classifier import get_channel_mapping_suggestions
    suggestions = await get_channel_mapping_suggestions()
    return {"suggestions": suggestions}


@app.get("/api/ai/memory", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_get_memory():
    """Get raw training memory entries."""
    from services.ai_classifier import _load_memory
    memory = await _load_memory()
    return {"moves": memory[-100:]}


# =============================================================================
# P1 — AI Management: multi-provider config + dynamic model discovery
# (DESIGN_SPEC §7 contract; Gwen §A.2 / §B). Every mutating route carries
# get_current_user + verify_origin. Keys are redacted on all read responses.
# =============================================================================

class ProviderConnectIn(BaseModel):
    """Body for POST /api/ai/providers (connect a new connection)."""
    name: str
    type: str                          # one of PROVIDER_TYPES
    api_key: str = ""
    base_url: str = ""                 # required for custom; ignored for builtins
    # optional pre-selection of models at connect time (skips manual entry)
    selected_models: list[str] = []


class ProviderSelectModelsIn(BaseModel):
    """Body for PUT /api/ai/providers/{id}/models (select active + default)."""
    active: list[str] = []
    default: str = ""


def _get_active_provider(config: TubeManagerConfig) -> ProviderConnection | None:
    """Resolve the currently active ProviderConnection by ai_active_provider_id."""
    if not config.ai_providers:
        return None
    if config.ai_active_provider_id:
        for p in config.ai_providers:
            if p.id == config.ai_active_provider_id:
                return p
    # Fallback: first enabled provider.
    for p in config.ai_providers:
        if p.enabled:
            return p
    return None


def _discover_models_for_type(conn: ProviderConnection, api_key: str) -> dict:
    """Run model discovery for a connection.

    Returns a dict with one of:
      - {"models": [{"id", "name", "owned_by?"}], "manual_entry": False}
      - {"manual_entry": True}   (anthropic/google catalog OR probe-unsupported)
      - {"error": <msg>, "manual_entry": True}  (probe failed; manual fallback)

    For openai/groq/custom: live GET {base}/v1/models probe with B.4 error
    handling. For anthropic/google: probe skipped, manual_entry=True.
    """
    import httpx

    # anthropic/google: skip probe entirely (known non-OpenAI shape).
    if conn.type in ("anthropic", "google"):
        return {"manual_entry": True, "models": []}

    base = (conn.base_url or "").rstrip("/")
    if not base:
        return {"manual_entry": True, "error": "No base_url configured"}

    models_url = f"{base}/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(models_url, headers=headers)
    except (httpx.TimeoutException, httpx.ConnectError, httpx.TransportError) as e:
        # Retry once with backoff (B.4 timeout/network).
        try:
            import time
            time.sleep(1.0)
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(models_url, headers=headers)
        except Exception as e2:
            return {"manual_entry": True, "error": f"Discovery probe failed: {e2}"}

    # B.4: 401/403 -> invalid key, do NOT cache, surface to UI.
    if resp.status_code in (401, 403):
        return {"manual_entry": True, "error": "Invalid API key / unauthorized (401/403)"}
    # B.4: 404 / non-OpenAI host -> manual entry fallback.
    if resp.status_code == 404:
        return {"manual_entry": True, "error": "No /v1/models route (404)"}

    # B.4: non-JSON or unexpected shape -> manual entry.
    try:
        payload = resp.json()
    except Exception:
        return {"manual_entry": True, "error": "Provider returned non-JSON body"}

    if not isinstance(payload, dict) or payload.get("object") != "list":
        return {"manual_entry": True, "error": "Response is not OpenAI-shaped"}

    models = []
    try:
        for item in payload.get("data", []):
            models.append({
                "id": item.get("id"),
                "name": item.get("id"),
                "owned_by": item.get("owned_by"),
            })
    except Exception:
        return {"manual_entry": True, "error": "Malformed model list"}

    return {"models": models, "manual_entry": False}


@app.get("/api/ai/providers", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_list_providers():
    """List provider connections (keys redacted)."""
    config = config_manager.config
    providers = []
    for p in config.ai_providers:
        d = p.redacted()
        d["status"] = "active" if (p.id == config.ai_active_provider_id) else ("enabled" if p.enabled else "disabled")
        d["active_model_count"] = len(p.selected_models)
        d["discovered_model_count"] = len(p.discovered_models)
        d["is_active"] = (p.id == config.ai_active_provider_id)
        providers.append(d)
    return {"providers": providers}


@app.post("/api/ai/providers", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_connect_provider(body: ProviderConnectIn):
    """Connect (add) a new provider connection."""
    if body.type not in PROVIDER_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid provider type '{body.type}'")
    if body.type == "custom" and not body.base_url:
        raise HTTPException(status_code=400, detail="base_url is required for custom providers")

    config = config_manager.config

    # Derive base_url for builtins.
    if body.type == "custom":
        base_url = body.base_url.rstrip("/")
    else:
        base_url = PROVIDER_BUILTIN_BASE_URLS.get(body.type, body.base_url)

    conn = ProviderConnection(
        id=uuid.uuid4().hex,
        name=body.name,
        type=body.type,
        base_url=base_url,
        api_key=SecretStr(body.api_key) if body.api_key else SecretStr(""),
        enabled=True,
        selected_models=list(body.selected_models),
        is_builtin=(body.type in PROVIDER_BUILTIN_BASE_URLS),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    config.ai_providers.append(conn)
    # First provider connected becomes the active one if none is set.
    if not config.ai_active_provider_id:
        config.ai_active_provider_id = conn.id

    await config_manager.save(config)
    return {"id": conn.id, "status": "connected"}


@app.delete("/api/ai/providers/{provider_id}", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_disconnect_provider(provider_id: str):
    """Disconnect (remove) a provider connection."""
    config = config_manager.config
    before = len(config.ai_providers)
    config.ai_providers = [p for p in config.ai_providers if p.id != provider_id]
    if len(config.ai_providers) == before:
        raise HTTPException(status_code=404, detail="Provider not found")
    # If we removed the active provider, clear/advance the active pointer.
    if config.ai_active_provider_id == provider_id:
        config.ai_active_provider_id = next((p.id for p in config.ai_providers if p.enabled), None)
    await config_manager.save(config)
    return {"ok": True}


@app.get("/api/ai/providers/{provider_id}/models", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_discover_provider_models(provider_id: str):
    """Discover available models for a provider connection.

    openai/groq/custom -> live GET {base}/v1/models probe (B.3/B.4).
    anthropic/google  -> probe skipped, returns manual_entry:true.
    The discovered list is cached onto the connection (discovered_models).
    """
    config = config_manager.config
    conn = next((p for p in config.ai_providers if p.id == provider_id), None)
    if conn is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    api_key = _secret_val(conn.api_key)
    result = _discover_models_for_type(conn, api_key)

    if ("error" in result and not result.get("manual_entry")) or (result.get("manual_entry") and conn.discovered_models):
        # Probe failed (genuine error, or non-OpenAI 404/catalog fallback)
        # AND we have a previous discovery cache. Serve it so the Providers
        # page still lists known models instead of going blank when a key
        # is temporarily invalid/rotated or the host has no /v1/models.
        cached = [{"id": m, "name": m} for m in (conn.discovered_models or [])]
        if cached:
            log.warning("Discovery probe failed; serving cached %d models", len(cached))
            return {
                "provider_id": provider_id,
                "type": conn.type,
                "models": cached,
                "manual_entry": False,
                "error": None,
                "cached": True,
                "active": list(conn.selected_models),
                "default": conn.selected_models[0] if conn.selected_models else None,
            }
        if "error" in result:
            return {"provider_id": provider_id, "models": [], "manual_entry": True,
                    "error": result["error"]}
        return {"provider_id": provider_id, "models": [], "manual_entry": True}

    models = result.get("models", [])
    manual = result.get("manual_entry", False)
    error = result.get("error")

    # Cache discovered models when the probe succeeded.
    if not manual and models:
        conn.discovered_models = [m["id"] for m in models if m.get("id")]
        conn.discovered_at = datetime.now(timezone.utc).isoformat()
        # Best-effort persist (don't fail discovery on a save error).
        try:
            await config_manager.save(config)
        except Exception as e:
            log.warning(f"Failed to persist discovered models: {e}")

    return {
        "provider_id": provider_id,
        "type": conn.type,
        "models": models,
        "manual_entry": manual,
        "error": error,
        # Reflect the connection's saved selection so the UI can pre-check
        # active models and mark the default (Sheldon finding #8).
        "active": list(conn.selected_models),
        "default": conn.selected_models[0] if conn.selected_models else None,
    }


@app.put("/api/ai/providers/{provider_id}/models", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_select_provider_models(provider_id: str, body: ProviderSelectModelsIn):
    """Select active models for a provider and activate it.

    Sets selected_models on the connection and makes it the active provider
    (ai_active_provider_id). `default` (optional) is recorded in selected_models
    ordering / stored as the first element for classify precedence.
    """
    config = config_manager.config
    conn = next((p for p in config.ai_providers if p.id == provider_id), None)
    if conn is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Validate requested model ids against discovered/catalog when available.
    valid = set(conn.discovered_models) if conn.discovered_models else set(body.active)
    selected = []
    for m in body.active:
        if valid and m not in valid:
            # Allow manual-entry models through even if not in discovered set.
            if conn.discovered_models:
                raise HTTPException(status_code=400, detail=f"Unknown model id: {m}")
        selected.append(m)
    if body.default and body.default not in selected:
        # Same validation as `active`: block arbitrary model ids unless manual
        # entry is in play (no discovered set yet).
        if conn.discovered_models and body.default not in conn.discovered_models:
            raise HTTPException(status_code=400, detail=f"Unknown model id: {body.default}")
        selected.insert(0, body.default)

    conn.selected_models = selected
    conn.enabled = True
    config.ai_active_provider_id = conn.id
    await config_manager.save(config)
    return {"ok": True, "active_provider_id": conn.id, "selected_models": selected}


@app.get("/api/ai/models", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_list_active_models():
    """All active (selected) models grouped by provider."""
    config = config_manager.config
    providers = []
    for p in config.ai_providers:
        if not p.enabled or not p.selected_models:
            continue
        providers.append({
            "id": p.id,
            "name": p.name,
            "type": p.type,
            "is_active": (p.id == config.ai_active_provider_id),
            "models": [
                {"id": m, "name": m, "active": True,
                 "default": (m == (p.selected_models[0] if p.selected_models else None))}
                for m in p.selected_models
            ],
        })
    return {"providers": providers}




# =============================================================================
# P2 — AI Management: Rules CRUD + AI Chat with tool-calling
# (DESIGN_SPEC §7 contract; Gwen §A.2 / §C. Every mutating route carries
# get_current_user + verify_origin. Destructive chat actions are held PENDING
# (ai_chat.store_pending_action) and execute only on /api/ai/chat/confirm.)
# Chat rate-limit (M8) enforced here at the endpoint layer.
# =============================================================================

class AIRuleIn(BaseModel):
    """Body for POST /api/ai/rules."""
    name: str
    description: str = ""
    target_playlist: str                 # playlist id (uniqueness key, Decision 2)
    playlist_name: str = ""
    model: str = ""
    enabled: bool = True
    is_global: bool = False
    priority: int = 0


class AIRuleUpdateIn(BaseModel):
    """Body for PUT /api/ai/rules/{id} (partial)."""
    name: Optional[str] = None
    description: Optional[str] = None
    target_playlist: Optional[str] = None
    playlist_name: Optional[str] = None
    model: Optional[str] = None
    enabled: Optional[bool] = None
    is_global: Optional[bool] = None
    priority: Optional[int] = None


class ChatIn(BaseModel):
    """Body for POST /api/ai/chat."""
    message: str
    conversation_id: Optional[str] = None


class ChatConfirmIn(BaseModel):
    """Body for POST /api/ai/chat/confirm."""
    action_id: str


# ── M8: per-user chat rate-limit (simple in-memory token bucket) ──────────
_chat_limit = 20          # requests
_chat_window = 60.0       # seconds
_chat_buckets: dict[str, list[float]] = {}


def _chat_rate_ok(user_id: str) -> bool:
    """Return True if the user is under the chat rate limit (M8)."""
    now = __import__("time").monotonic()
    hits = _chat_buckets.setdefault(user_id, [])
    # Drop hits outside the window.
    _chat_buckets[user_id] = [t for t in hits if now - t < _chat_window]
    if len(_chat_buckets[user_id]) >= _chat_limit:
        return False
    _chat_buckets[user_id].append(now)
    return True


def _rules_list(config) -> list:
    """Redacted rule list (no secrets — rules carry none, but keep shape stable)."""
    return [r.model_dump() for r in config.ai_rules]


@app.get("/api/ai/rules", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_list_rules():
    """List AI classification rules."""
    return {"rules": _rules_list(config_manager.config)}


@app.post("/api/ai/rules", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_create_rule(body: AIRuleIn):
    """Create a rule. 409 if target_playlist already has a rule (Decision 2)."""
    config = config_manager.config
    if any(r.target_playlist == body.target_playlist for r in config.ai_rules):
        raise HTTPException(
            status_code=409,
            detail=f"Rule already exists for target_playlist '{body.target_playlist}'",
        )
    from models.config import AIRule
    rule = AIRule(
        name=body.name, description=body.description,
        target_playlist=body.target_playlist, playlist_name=body.playlist_name,
        model=body.model, enabled=body.enabled,
        is_global=body.is_global, priority=body.priority,
    )
    config.ai_rules.append(rule)
    await config_manager.save(config)
    return {"id": rule.id, "status": "created"}


@app.patch("/api/ai/rules/{rule_id}", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_patch_rule(rule_id: str, body: AIRuleUpdateIn):
    """PATCH alias for ai_update_rule (matches DESIGN_SPEC §7 + frontend convention)."""
    return await ai_update_rule(rule_id, body)


@app.put("/api/ai/rules/{rule_id}", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_update_rule(rule_id: str, body: AIRuleUpdateIn):
    """Update a rule. Re-checks 409 if target_playlist changes to an occupied one."""
    config = config_manager.config
    rule = next((r for r in config.ai_rules if r.id == rule_id), None)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    data = body.model_dump(exclude_unset=True)
    if "target_playlist" in data and data["target_playlist"] != rule.target_playlist:
        if any(r.target_playlist == data["target_playlist"] and r.id != rule_id
               for r in config.ai_rules):
            raise HTTPException(
                status_code=409,
                detail=f"Rule already exists for target_playlist '{data['target_playlist']}'",
            )
    for k, v in data.items():
        setattr(rule, k, v)
    await config_manager.save(config)
    return {"id": rule.id, "status": "updated"}


@app.delete("/api/ai/rules/{rule_id}", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_delete_rule(rule_id: str):
    """Delete a rule."""
    config = config_manager.config
    before = len(config.ai_rules)
    config.ai_rules = [r for r in config.ai_rules if r.id != rule_id]
    if len(config.ai_rules) == before:
        raise HTTPException(status_code=404, detail="Rule not found")
    await config_manager.save(config)
    return {"ok": True}


@app.post("/api/ai/chat", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_chat(body: ChatIn, request: Request):
    """Conversational management with constrained tool-calling (ai_chat.run_chat).

    Destructive tools (move/delete/remove-duplicates) are held pending and
    returned as previews; they execute only on /api/ai/chat/confirm.
    """
    from services import ai_chat as chat_mod
    user = getattr(request.state, "user", None)
    user_id = user.get("sub") if isinstance(user, dict) else "anon"
    if not _chat_rate_ok(user_id):
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(int(_chat_window))},
            content={"error": "Chat rate limit exceeded. Retry later."},
        )
    config = config_manager.config
    key = chat_mod.conversation_key(user_id, body.conversation_id)
    history = chat_mod.get_conversation(key)
    result = chat_mod.run_chat(
        message=body.message, config=config,
        youtube_service=youtube_service, history=history,
    )
    # Persist the turn (with any pending actions) for /history.
    chat_mod.append_turn(key, "user", body.message,
                          pending=result.get("pending_actions"))
    chat_mod.append_turn(key, "assistant", result.get("reply", ""),
                          pending=result.get("pending_actions"))
    return result


@app.post("/api/ai/chat/confirm", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_chat_confirm(body: ChatConfirmIn):
    """Execute a retained pending destructive action (P1-9 / M4).

    Reads the in-memory pending record, dispatches the REAL bulk op
    (api.bulk_operations_impl), and consumes the record (one-shot).
    """
    from services import ai_chat as chat_mod
    pending = chat_mod.consume_pending_action(body.action_id)
    if pending is None:
        raise HTTPException(status_code=404, detail="Pending action not found or already executed")
    action = pending.get("action")
    params = pending.get("params", {})
    try:
        if action == "move_video":
            from api.bulk_operations_impl import BulkOperationsService
            svc = BulkOperationsService(config_manager.config, config_manager)
            await svc.move_video(
                params["video_id"],
                target_playlist_id=params["to_playlist"],
                source_playlist_id=params["from_playlist"],
            )
        elif action == "delete_video":
            from api.bulk_operations_impl import BulkOperationsService
            svc = BulkOperationsService(config_manager.config, config_manager)
            await svc.delete_video(params["video_id"], params["playlist_id"])
        elif action == "remove_duplicates":
            from api.bulk_operations_impl import BulkOperationsService
            svc = BulkOperationsService(config_manager.config, config_manager)
            del_ids = pending.get("params", {}).get("duplicate_video_ids", [])
            pid = pending.get("params", {}).get("playlist_id", "")
            deleted = 0
            for vid in del_ids:
                ok = await svc.delete_video(vid, pid)
                if ok:
                    deleted += 1
            return {"ok": True, "action": action, "deleted": deleted,
                    "action_id": body.action_id}
        else:
            raise HTTPException(status_code=400, detail=f"Unknown pending action '{action}'")
    except HTTPException:
        raise
    except Exception as e:
        # Redact secrets in surfaced errors (M3).
        return JSONResponse(status_code=200, content={
            "ok": False, "error": chat_mod._redact(str(e)), "action_id": body.action_id})
    return {"ok": True, "action": action, "action_id": body.action_id}


@app.get("/api/ai/chat/history", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_chat_history(conversation_id: Optional[str] = None, request: Request = None):
    """Return prior chat turns for a conversation."""
    from services import ai_chat as chat_mod
    user = getattr(request.state, "user", None) if request else None
    user_id = user.get("sub") if isinstance(user, dict) else "anon"
    key = chat_mod.conversation_key(user_id, conversation_id)
    return {"conversation_id": conversation_id, "turns": chat_mod.get_conversation(key)}


# =============================================================================
# P3 — AI Job Scheduling (scheduled_jobs.json, NOT config.json)
#
# Endpoints (all mutating routes carry Depends(get_current_user) +
# Depends(verify_origin), matching P1/P2 — clause P3-5):
#   GET    /api/ai/jobs            list jobs
#   POST   /api/ai/jobs            create job (privilege gate P1-2 on destructive)
#   POST   /api/ai/jobs/parse      NL -> {cron, task} via active provider
#   POST   /api/ai/jobs/{id}/run   run now (Flow C confirm for destructive)
#   POST   /api/ai/jobs/{id}/cancel hard-cancel an in-flight run (no future effect)
#   PATCH  /api/ai/jobs/{id}       enable/pause
#   DELETE /api/ai/jobs/{id}       delete
# =============================================================================

from models.scheduled_job import (
    ScheduledJob,
    ScheduledJobTask,
    ALLOWED_JOB_ACTIONS,
    DESTRUCTIVE_JOB_ACTIONS,
)
from services import cron_util
from services import job_store
from services import job_parse


class JobIn(BaseModel):
    """Body for POST /api/ai/jobs (create)."""
    name: str
    cron: str
    task: dict                       # {"type": <action>, "payload": {...}}
    enabled: bool = True
    # P1-2: MUST be True to schedule a destructive task. Never defaults open.
    confirm_destructive: bool = False


class JobPatchIn(BaseModel):
    """Body for PATCH /api/ai/jobs/{id} (enable/pause)."""
    enabled: Optional[bool] = None


def _validate_task(task: dict) -> ScheduledJobTask:
    """Strict validation (M4): enumerated type + additionalProperties:false."""
    if not isinstance(task, dict):
        raise ValueError("task must be an object")
    ttype = task.get("type")
    if ttype not in ALLOWED_JOB_ACTIONS:
        raise ValueError(f"unknown task type '{ttype}'")
    if "payload" not in task:
        raise ValueError("task.payload is required")
    payload = task.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("task.payload must be an object")
    # additionalProperties:false — reject any key other than type/payload.
    extra = set(task.keys()) - {"type", "payload"}
    if extra:
        raise ValueError(f"task has unknown fields: {sorted(extra)}")
    return ScheduledJobTask(type=ttype, payload=payload)


def _job_summary(job: ScheduledJob) -> dict:
    """Stable client shape (no secrets)."""
    return job.model_dump()


@app.get("/api/ai/jobs", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_list_jobs():
    """List scheduled jobs (no secrets in the shape)."""
    jobs = job_store.load_jobs()
    return {"jobs": [_job_summary(j) for j in jobs]}


@app.post("/api/ai/jobs", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_create_job(body: JobIn):
    """Create a scheduled job.

    Validation (M4): cron must parse; task.type must be in ALLOWED_JOB_ACTIONS;
    task must be {type, payload} only. Destructive tasks (P1-2) require
    confirm_destructive=True — otherwise 400. On success the job is persisted
    and next_run recomputed (the scheduler reads it on its next tick).
    """
    cron = body.cron.strip()
    if not cron_util.cron_valid(cron):
        raise HTTPException(status_code=400, detail=f"invalid cron expression: {cron!r}")

    try:
        task = _validate_task(body.task)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Privilege gate P1-2: destructive payloads need explicit creation-time
    # confirmation. We never allow a destructive job to be scheduled silently.
    if task.type in DESTRUCTIVE_JOB_ACTIONS and not body.confirm_destructive:
        raise HTTPException(
            status_code=400,
            detail=(
                "Refusing to schedule destructive task "
                f"'{task.type}' without confirm_destructive=true. "
                "Destructive jobs execute automatically once created; this "
                "confirmation is the only consent point."
            ),
        )

    job = ScheduledJob(
        name=body.name,
        cron=cron,
        task=task,
        enabled=body.enabled,
    )
    nxt = cron_util.next_run(cron)
    job.next_run = nxt.isoformat() if nxt else None
    job_store.add_job(job)
    return JSONResponse(status_code=201,
                        content={"id": job.id, "next_run": job.next_run, "status": "created"})


@app.post("/api/ai/jobs/parse", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_parse_job(body: dict):
    """Parse natural-language into {cron, task} via the active AI provider.

    Returns a validated structured object, or 400/502 if the model returns
    something unparseable or no provider is configured (M4 — never forward raw
    model text into a schedule).
    """
    text = (body or {}).get("text", "")
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="missing 'text'")
    try:
        parsed = job_parse.parse_schedule_nl(text, config_manager.config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"could not parse schedule: {str(e)[:300]}")
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"cron": parsed["cron"], "name": parsed["name"],
            "task": parsed["task"], "explain": parsed["explain"]}


@app.post("/api/ai/jobs/{job_id}/run", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_run_job(job_id: str):
    """Run a job immediately (Flow D / Run now).

    Non-destructive: dispatched synchronously through the shared handler (like
    the scheduler). Destructive: held PENDING via the existing ai_chat pending
    store (P1-9 / Flow C) and returned as a preview needing explicit confirm
    through POST /api/ai/chat/confirm — i.e. we reuse the existing confirm
    wiring rather than duplicating the bulk-ops service.
    """
    from services import ai_chat as chat_mod

    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    action = job.task.type
    if action not in DESTRUCTIVE_JOB_ACTIONS:
        # Non-destructive: run like a scheduled fire (tracked + persisted).
        if background_worker is not None:
            try:
                await background_worker._execute_job(job)
            except Exception as e:
                return JSONResponse(status_code=200, content={
                    "job_run_id": job.id, "ok": False,
                    "error": chat_mod._redact(str(e))})
            return {"job_run_id": job.id, "ok": True, "last_status": job.last_status}
        raise HTTPException(status_code=503, detail="scheduler worker unavailable")

    # Destructive: build preview + hold pending (Flow C). Execution only via
    # POST /api/ai/chat/confirm (reuses BulkOperationsService wiring).
    params = dict(job.task.payload or {})
    if action == "remove_duplicates":
        # Capture dupe ids NOW (read-only scan) so /confirm can delete without
        # a second call.
        try:
            from services.ai_chat import _tool_find_duplicates
            dup = _tool_find_duplicates(
                getattr(background_worker, "youtube_service", None),
                params.get("playlist_id", ""))
            ids = []
            for g in dup.get("duplicate_groups", []):
                ids.extend(g.get("video_ids", []))
            params["duplicate_video_ids"] = ids
        except Exception:
            params.setdefault("duplicate_video_ids", [])
    pending = {
        "action": action,
        "preview": {"action": action, **params},
        "display": f"{action} (scheduled job {job.name})",
        "params": params,
    }
    action_id = chat_mod.store_pending_action(pending)
    return {
        "job_run_id": job.id,
        "needs_confirm": True,
        "pending_action_id": action_id,
        "preview": pending["preview"],
        "action": action,
    }


@app.patch("/api/ai/jobs/{job_id}", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_patch_job(job_id: str, body: JobPatchIn):
    """Enable / pause a job."""
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if body.enabled is not None:
        job.enabled = body.enabled
        nxt = cron_util.next_run(job.cron) if job.enabled else None
        job.next_run = nxt.isoformat() if nxt else None
    job_store.update_job(job)
    return {"ok": True, "enabled": job.enabled, "id": job.id}


@app.post("/api/ai/jobs/{job_id}/cancel", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_cancel_job(job_id: str):
    """Hard-cancel an in-flight run of this job (Dave's "hard cancel").

    Stops a scheduled/Run-now job that is CURRENTLY executing. Does not affect
    future ticks (use DELETE to remove, or PATCH {enabled:false} to pause).
    Returns {"ok": true, "cancelled": <bool>} — cancelled is False if nothing
    was running.
    """
    job = job_store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    if background_worker is None:
        raise HTTPException(status_code=503, detail="scheduler worker unavailable")
    cancelled = background_worker.cancel_in_flight()
    return {"ok": True, "cancelled": cancelled, "id": job_id}


@app.delete("/api/ai/jobs/{job_id}", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def ai_delete_job(job_id: str):
    """Delete a job (removed from store; scheduler skips it next tick)."""
    removed = job_store.remove_job(job_id)
    if not removed:
        raise HTTPException(status_code=404, detail="job not found")
    return {"ok": True}


# Reset settings

# Reset settings
@app.post("/api/settings/reset", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def reset_settings():
    """Reset all settings to defaults."""
    config = TubeManagerConfig()
    await config_manager.save(config)
    
    global youtube_service
    youtube_service = YouTubeService(config)
    _sync_worker_youtube_service()

    return {"message": "Settings reset to defaults"}


# Action dispatch endpoint for dashboard buttons
@app.post("/api/action", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def dispatch_action(body: dict):
    """Dispatch a dashboard action (sync_playlists, sync_watch_later)."""
    action = body.get("action", "")
    payload = body.get("payload", None)

    if not action:
        return {"status": "error", "error": "No action specified"}

    actions = {
        "sync_playlists": "Full Playlist Sync",
        "scan_duplicates": "Scan Duplicates",
        "scan_misplaced": "Scan Misplaced",
    }

    name = actions.get(action, action)
    log.info(f"Action dispatched: {name}")

    # Process based on action type
    try:
        if not background_worker:
            return {"status": "error", "error": "Background worker not initialized"}

        known_actions = {
            "sync_playlists",
            "scan_duplicates",
            "scan_misplaced",
            "full_cluster_scan",
            "diagnose_failures",
            "apply_rules",
        }
        if action not in known_actions:
            return {"status": "error", "error": f"Unknown action: {action}"}

        # Enqueue onto the task queue. The single background consumer
        # (process_background_tasks) serializes actions and dispatches them,
        # so cancel_current_task() can drain pending work and hard-cancel the
        # in-flight task. Launching via asyncio.create_task here would bypass
        # the queue, making cancellation and queue stats ineffective.
        await task_queue.put({"action": action, "payload": payload or {}})
        # Broadcast an immediate status update so the dashboard Scan Details
        # panel reflects the queued task without waiting for a poll.
        if background_worker:
            await background_worker._broadcast_status()
    except Exception as e:
        log.error(f"Action {action} failed: {e}")
        return {"status": "error", "error": str(e)}

    return {"status": "started", "action": action}


@app.post("/api/action/cancel", dependencies=[Depends(get_current_user), Depends(verify_origin)])
async def cancel_action():
    """Cancel the currently running background task."""
    global background_worker
    if background_worker:
        background_worker.cancel_current_task()
    await manager.broadcast(json.dumps({"type": "log", "message": "[AGENT] Action cancelled by user"}))
    return {"status": "cancelled"}


# Diagnostic endpoints
@app.get("/api/diagnostics/youtube", dependencies=[Depends(get_current_user), Depends(check_role([RoleEnum.ADMIN]))])
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
                raw_resp = raw_playlists.json()
                # Redact any token/secret fields from the response
                raw_resp = _redact_secrets(raw_resp)
                result["raw_api_response"] = raw_resp
            except Exception:
                result["raw_api_body"] = raw_playlists.text[:500]
    except Exception as e:
        result["status"] = "error"
        result["error"] = f"{type(e).__name__}: {str(e)}"
    
    return result


@app.get("/api/diagnostics/oauth-user", dependencies=[Depends(get_current_user)])
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
    return result

    











@app.get("/api/system/logs", dependencies=[Depends(get_current_user), Depends(check_role([RoleEnum.ADMIN]))])
async def get_system_logs():
    """Get recent system logs from the log file."""
    log_file = Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data")) / "tube_manager.log"
    if not log_file.exists():
        return {
            "logs": [],
            "info": "No log file found. Logs are written to stdout by default.",
            "total": 0,
        }
    try:
        lines = await asyncio.to_thread(log_file.read_text)
        lines = lines.strip().split("\n")
        last_200 = lines[-200:] if len(lines) > 200 else lines
        return {
            "logs": last_200,
            "total": len(lines),
            "returned": len(last_200),
        }
    except Exception as e:
        return {
            "logs": [],
            "info": f"Failed to read logs: {str(e)}",
            "total": 0,
        }


@app.get("/system/logs", dependencies=[Depends(get_current_user), Depends(check_role([RoleEnum.ADMIN]))])
async def system_logs_page():
    """System logs viewer page."""
    log_file = Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data")) / "tube_manager.log"
    logs_html = ""
    if log_file.exists():
        try:
            content = await asyncio.to_thread(log_file.read_text)
            lines = content.strip().split("\n")
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
        thumb_dir = Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data")) / "thumbnails"
        if thumb_dir.exists():
            shutil.rmtree(thumb_dir)
        thumb_dir.mkdir(parents=True, exist_ok=True)
        return {"message": "Thumbnail cache cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/storage/export", dependencies=[Depends(get_current_user)])
async def export_data(request: Request):
    """Export all data as JSON.

    SECURITY: secrets (OAuth client_secret/tokens, API keys) are NEVER included
    in plaintext. The previous implementation used config.model_dump(exclude={
    'oauth': {...}}) which silently leaked the entire oauth block (a nested
    Pydantic model the dict-form exclude does not affect) plus the raw
    SecretStr API keys. We now redact every secret field.
    """
    from datetime import datetime
    config = config_manager.config

    # Redacted config: copy non-secret fields, mask secret-bearing ones.
    config_dict = config.model_dump(exclude={"oauth", "youtube_api_key", "ai_api_key"})
    config_dict["oauth"] = {
        "client_id": _secret_val(config.oauth.client_id) or "",
        "client_secret": "••••••••" if _secret_val(config.oauth.client_secret) else "",
        "access_token": "••••••••" if config.oauth.access_token else None,
        "refresh_token": "••••••••" if config.oauth.refresh_token else None,
        "token_expiry": config.oauth.token_expiry,
    }
    config_dict["youtube_api_key"] = "••••••••" if _secret_val(config.youtube_api_key) else ""
    config_dict["ai_api_key"] = "••••••••" if _secret_val(config.ai_api_key) else ""

    export_data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "config": config_dict,
        "stats": await stats(request),
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
    # Validate token from query param before accepting connection
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return

    from api.auth import decode_access_token, is_token_revoked, get_users_db
    try:
        payload = decode_access_token(token)
        if is_token_revoked(token):
            await websocket.close(code=4001, reason="Token has been revoked")
            return
        username = payload.get("sub")
        if not username:
            await websocket.close(code=4001, reason="Invalid token")
            return
        users_db = await get_users_db()
        user = users_db.get(username)
        if not user:
            await websocket.close(code=4001, reason="User not found")
            return
    except Exception:
        await websocket.close(code=4001, reason="Authentication failed")
        return

    await manager.connect(websocket)
    ping_interval = 30
    max_ping_failures = 3
    ping_failures = 0
    last_pong = time.monotonic()

    try:
        await websocket.send_text(json.dumps({"type": "log", "message": "[WS] Connected to agent terminal"}))

        # ping_loop only SENDS pings and checks staleness of last_pong.
        # It must never call receive_text() — the main loop below is the
        # single reader that owns the WebSocket. Concurrent reads on a
        # Starlette WebSocket are unsafe and silently steal each other's
        # messages.
        async def ping_loop():
            nonlocal ping_failures, last_pong
            while True:
                await asyncio.sleep(ping_interval)
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                    # If we haven't seen a pong since the last ping, count a failure.
                    if time.monotonic() - last_pong > ping_interval + 5:
                        ping_failures += 1
                    if ping_failures >= max_ping_failures:
                        await manager.broadcast(json.dumps({"type": "log", "message": "[WS] Connection lost - max ping failures reached"}))
                        break
                except Exception as e:
                    log.debug(f"WebSocket handler terminated: {e}")
                    break

        ping_task = asyncio.create_task(ping_loop())

        # Single reader — owns all incoming messages and dispatches them.
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            mtype = msg.get("type")
            if mtype == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif mtype == "pong":
                ping_failures = 0
                last_pong = time.monotonic()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.error(f"Broad WebSocket error: {e}")
        # Send the error only to the affected connection, not broadcast to all clients.
        try:
            await websocket.send_text(json.dumps({"type": "log", "message": "[WS ERROR] connection error"}))
        except Exception:
            pass
        # Log error but don't break - let the connection be handled normally
    finally:
        ping_task.cancel()
        manager.disconnect(websocket)


# Entry point
if __name__ == "__main__":
    import uvicorn
    setup_logging()
    uvicorn.run("app:app", host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8000")), reload=True)
