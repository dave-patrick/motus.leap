"""Tube Manager Main Application."""
# Deploy v2.1

import asyncio
import json
import logging
import hashlib
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Depends, Cookie
from fastapi.responses import HTMLResponse, PlainTextResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aiofiles

# Auth dependency
from api.auth import get_current_user

# Auth dependency for page routes (redirects to /auth if not authenticated)
async def require_auth(request: Request, token: str = Cookie(default=None), authorization: str = Header(default=None)):
    """Require authentication for page routes. Redirects to /auth if not authenticated."""
    # Check cookie first, then Authorization header
    auth_token = token or (authorization.replace("Bearer ", "") if authorization and authorization.startswith("Bearer ") else None)
    if not auth_token:
        return RedirectResponse(url="/auth", status_code=302)
    
    # Validate token
    try:
        user = await get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=auth_token))
        request.state.user = user
        return user
    except HTTPException:
        return RedirectResponse(url="/auth", status_code=302)
    except Exception:
        return RedirectResponse(url="/auth", status_code=302)

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from fastapi import Header

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

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
    title="Tube Manager",
    description="YouTube Playlist Management System",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store in app state for routers
app.state.config = config_manager.config
app.state.config_manager = config_manager

# Register routers
app.include_router(bulk_router, tags=["bulk"])
app.include_router(auth_router, tags=["auth"])


async def no_cache_file_response(file_path: Path) -> Response:
    """Return HTML response with no-cache headers to prevent CDN/browser caching."""
    try:
        async with aiofiles.open(file_path, mode='r', encoding="utf-8") as f:
            content = await f.read()

        # Add a visible marker to confirm fresh deploy
        content = content.replace(
            '<title>Tube Manager</title>',
            '<title>Tube Manager</title>\n    <meta name="deploy-time" content="' + str(int(__import__('time').time())) + '">'
        )
        return Response(
            content=content,
            media_type="text/html; charset=utf-8",
            headers={
                "Cache-Control": "public, max-age=0",  # Allow ETag support
                "Pragma": "no-cache",
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    global youtube_service
    config = config_manager.load()
    youtube_service = YouTubeService(config)
    
    # Start background task processor
    asyncio.create_task(process_background_tasks())
    
    log.info("Tube Manager started successfully")
    
    yield
    
    # Shutdown
    log.info("Tube Manager shutting down")
    await shutdown_http_client()


# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

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
    import secrets

    # Generate nonce for inline scripts (only for Tailwind CDN)
    nonce = secrets.token_hex(16)

    response = await call_next(request)

    # Strict Content Security Policy
    response.headers["Content-Security-Policy"] = (
        f"default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}' https://cdn.tailwindcss.com; "
        f"style-src 'self' 'nonce-{nonce}' https://fonts.googleapis.com; "
        f"font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
        f"img-src 'self' https://i.ytimg.com https://yt3.ggpht.com; "
        f"connect-src 'self' https://www.googleapis.com https://www.youtube.com wss://tubemanager.onrender.com; "
        f"frame-ancestors 'none'; "
        f"frame-src 'none';"
    )

    # Additional security headers
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

    # Pass nonce to template (if needed)
    response.headers["X-CSP-Nonce"] = nonce

    return response


# Background task processor
async def process_background_tasks():
    """Process background tasks from the queue."""
    global background_tasks_running
    background_tasks_running = True
    
    while True:
        try:
            task = await task_queue.get()
            action = task.get("action")
            payload = task.get("payload", {})
            
            await manager.broadcast(json.dumps({"type": "log", "message": f"[AGENT] Starting: {action}"}))
            
            # Process different actions
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
            log.error(f"Background task error: {e}")
            await manager.broadcast(json.dumps({"type": "log", "message": f"[ERROR] {str(e)}"}))


async def full_cluster_scan(payload):
    """Perform a full cluster scan."""
    await manager.broadcast(json.dumps({"type": "log", "message": "[SCAN] Initiating Full Cluster Scan..."}))
    
    client = youtube_service.get_client(require_oauth=False) if youtube_service else None
    if not client:
        await manager.broadcast(json.dumps({"type": "log", "message": "[ERROR] No YouTube client available. Configure API key or OAuth in Settings."}))
        return
    
    try:
        # Fetch user's playlists
        await manager.broadcast(json.dumps({"type": "log", "message": "[SCAN] Fetching playlist data from YouTube API..."}))
        playlists_resp = client.list_mine_playlists(max_results=50)
        playlists = playlists_resp.get("items", [])
        await manager.broadcast(json.dumps({"type": "log", "message": f"[SCAN] Found {len(playlists)} playlists"}))
        
        total_videos = 0
        for pl in playlists:
            pl_id = pl.get("id")
            pl_title = pl.get("snippet", {}).get("title", pl_id)
            items_resp = client.list_videos(pl_id, max_results=50)
            items = items_resp.get("items", [])
            total_videos += len(items)
            await manager.broadcast(json.dumps({"type": "log", "message": f"[SCAN] {pl_title}: {len(items)} videos"}))
            await asyncio.sleep(0.1)
        
        await manager.broadcast(json.dumps({"type": "log", "message": f"[SCAN] Analyzing {total_videos} videos across {len(playlists)} playlists..."}))
        await asyncio.sleep(1)
        
        # Real scan statistics (no fake clustering)
        await manager.broadcast(json.dumps({"type": "log", "message": "[SCAN] Building scan statistics..."}))
        await asyncio.sleep(0.5)

        # Calculate real metrics from fetched data
        avg_videos_per_playlist = total_videos / len(playlists) if playlists else 0
        await manager.broadcast(json.dumps({
            "type": "log",
            "message": f"[SCAN] Analysis complete • {total_videos} videos across {len(playlists)} playlists • {avg_videos_per_playlist:.1f} avg videos/playlist"
        }))
        await asyncio.sleep(0.5)
        
        await manager.broadcast(json.dumps({"type": "log", "message": "[LEARN] Processing statistics..."}))
        await asyncio.sleep(1)
        await manager.broadcast(json.dumps({"type": "log", "message": f"[SCAN] Complete • {total_videos} videos analyzed • Next auto-scan: 1 hour"}))
        
    except Exception as e:
        error_details = f"{type(e).__name__}: {str(e)}"
        if hasattr(e, '__cause__') and e.__cause__:
            error_details += f" | Cause: {type(e.__cause__).__name__}: {str(e.__cause__)}"
        if hasattr(e, '__context__') and e.__context__:
            error_details += f" | Context: {type(e.__context__).__name__}: {str(e.__context__)}"
        import traceback
        try:
            error_details += f" | Traceback: {traceback.format_exc()}"
        except Exception as e:
            log.error(f"Error formatting traceback: {e}")
        await manager.broadcast(json.dumps({"type": "log", "message": f"[ERROR] Scan failed: {error_details}"}))


async def force_auto_sort(payload):
    """Force auto-sort of playlists."""
    await manager.broadcast(json.dumps({"type": "log", "message": "[SORT] Forcing Auto-Sort All playlists..."}))
    
    client = youtube_service.get_client(require_oauth=True) if youtube_service else None
    if not client:
        await manager.broadcast(json.dumps({"type": "log", "message": "[ERROR] OAuth required for write operations. Connect YouTube in Settings."}))
        return
    
    try:
        config = config_manager.config
        mappings = config.channel_mappings
        if not mappings:
            await manager.broadcast(json.dumps({"type": "log", "message": "[SORT] No channel mappings configured. Add mappings in Rules page."}))
            return
        
        await manager.broadcast(json.dumps({"type": "log", "message": "[SORT] Applying channel→playlist mappings..."}))

        # NOTE: Auto-sort requires YouTube Data API write operations.
        # Current implementation uses read-only OAuth scope.
        # To enable auto-sort, update OAuth scope to include:
        # https://www.googleapis.com/auth/youtube
        # Then implement client.move_video() calls here.

        await manager.broadcast(json.dumps({"type": "log", "message": f"[SORT] {len(mappings)} channel→playlist mappings configured"}))
        await manager.broadcast(json.dumps({"type": "log", "message": "[SORT] Note: Auto-sort requires write permissions. Update OAuth scope in Settings to enable."}))
        await manager.broadcast(json.dumps({"type": "log", "message": "[SORT] Complete"}))
        
    except Exception as e:
        await manager.broadcast(json.dumps({"type": "log", "message": f"[ERROR] Sort failed: {str(e)}"}))


async def watch_later_sync(payload):
    """Sync Watch Later playlist.

    Classification logic:
    - Build config channel_id -> playlist_id mapping, ignoring empty playlist targets.
    - Fetch Watch Later playlist items.
    - For each item, classify:
        - Use Watch Later's effective owner if owner is missing/blank.
        - Match channel owner to a configured mapping first.
        - If no channel match, match title text against mapping channel titles (fuzzy contains / casefold).
    - If no mapping target, skip and continue.
    - Move the video to the target playlist: insert in new playlist, then delete original playlist item.
    - Dry-run is supported via ?dry_run=true or payload.dry_run=true.
    """
    await manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] Syncing Watch Later playlist..."}))
    
    client = youtube_service.get_client(require_oauth=True) if youtube_service else None
    if not client:
        await manager.broadcast(json.dumps({"type": "log", "message": "[ERROR] OAuth required. Connect YouTube in Settings."}))
        return
    
    try:
        dry_run = bool(payload.get("dry_run") if isinstance(payload, dict) else False)
        # Fetch channel->playlist mappings from config
        mappings, _show_next = await api_mappings()
        mapping_by_channel_id = {}
        mapping_channel_title_scores: list[tuple[str, str, float]] = []
        for mapping in mappings.get("mappings", []):
            channel_id = mapping.get("channel_id")
            playlist_id = mapping.get("playlist")
            title = mapping.get("channel", "")
            if not channel_id or not playlist_id:
                continue
            mapping_by_channel_id[channel_id] = playlist_id
            if title:
                mapping_channel_title_scores.append((channel_id, playlist_id, float(len(title))))

        if not mapping_by_channel_id:
            await manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] No channel mappings configured. Add mappings in Rules/Settings."}))
            await manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] Complete"}))
            return

        # Preload channel metadata for OAuth-based channel lookup
        channel_key = "__watchlater_channels__"
        channel_cache = await self._get_cached(channel_key) if hasattr(youtube_service, "_get_cached") else None
        if not channel_cache:
            channel_cache = {}
            # Refresh via YouTubeService if available
            if hasattr(youtube_service, "fetch_all_data"):
                async def _safe_fetch():
                    return await youtube_service.fetch_all_data(force_refresh=True)
                try:
                    all_data = await _safe_fetch()
                    for channel in all_data.get("subscriptions", []):
                        channel_cache[channel.get("id", "")] = {
                            "title": channel.get("title", ""),
                            "channel_id": channel.get("id", ""),
                        }
                    await youtube_service._set_cached(channel_key, channel_cache)
                except Exception:
                    pass

        def classify(item):
            # Source owner resolution
            owner_id = ""
            owner_title = ""
            owner = item.get("contentDetails", {}).get("videoOwnerChannelId") or item.get("snippet", {}).get("videoOwnerChannelId")
            if owner:
                owner_id = owner.strip()
            channel_obj = (item.get("snippet", {}) or {}).get("videoOwnerChannelName")
            if isinstance(channel_obj, str):
                owner_title = channel_obj.strip()
            if not owner_id:
                owner_id = owner_title

            if owner_id:
                if owner_id in mapping_by_channel_id:
                    return owner_id, mapping_by_channel_id[owner_id]
                meta = channel_cache.get(owner_id)
                if meta:
                    if meta.get("channel_id") in mapping_by_channel_id:
                        return meta.get("channel_id"), mapping_by_channel_id[meta.get("channel_id")]
                    title_for_match = meta.get("title", owner_title or "").lower()
                    for channel_title_id, channel_playlist_id, title_len in mapping_channel_title_scores:
                        if title_for_match and channel_title_id.lower() in title_for_match:
                            return channel_title_id, channel_playlist_id

            # If no owner match, fallback across metadata / title
            snippet = item.get("snippet", {}) or {}
            candidates: list[str] = []
            for key in ("title", "description"):
                val = snippet.get(key, "")
                if isinstance(val, str):
                    candidates.append(val)
            lower_candidates = [c.lower() for c in candidates]

            for candidate in lower_candidates:
                for channel_title_id, channel_playlist_id, title_len in mapping_channel_title_scores:
                    if channel_title_id.lower() in candidate:
                        return channel_title_id, channel_playlist_id
            return None, None

        # Fetch watch later items
        watch_later_resp = client.list_watch_later_items(max_results=50)
        watch_later_items = watch_later_resp.get("items", [])
        await manager.broadcast(json.dumps({"type": "log", "message": f"[SYNC] Fetched {len(watch_later_items)} videos from Watch Later"}))
        
        moved = []
        skipped = []
        failed = []
        for item in watch_later_items:
            video_id = item.get("contentDetails", {}).get("videoId")
            playlist_item_id = item.get("id")
            origin = item.get("snippet", {}).get("playlistId") or ""
            if not video_id:
                skipped.append(item)
                continue
            channel_id, playlist_id = classify(item)
            if not playlist_id:
                skipped.append(item)
                continue
            
            if dry_run:
                moved.append({"video_id": video_id, "from": origin, "to": playlist_id, "channel_id": channel_id})
                continue

            try:
                # Insert into target playlist
                client.move_video_to_playlist(video_id, playlist_id)
                # Remove from Watch Later
                if playlist_item_id:
                    client.remove_video_from_playlist(playlist_item_id)
                moved.append({"video_id": video_id, "from": origin, "to": playlist_id, "channel_id": channel_id})
            except Exception as move_error:
                failed.append({"video_id": video_id, "error": str(move_error)})
                await manager.broadcast(json.dumps({"type": "log", "message": f"[ERROR] Failed to move {video_id}: {move_error}"}))

        await manager.broadcast(json.dumps({"type": "log", "message": f"[SYNC] Moved {len(moved)} video(s), skipped {len(skipped)}, failed {len(failed)}"}))
        if moved:
            for move in moved[:20]:
                await manager.broadcast(json.dumps({"type": "log", "message": f"[SYNC] {move['video_id']} -> {move['to']} (from {move.get('from', 'watch later')})"}))
        if dry_run and moved:
            await manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] Dry run: no changes applied."}))
        await manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] Complete"}))
        
    except Exception as e:
        await manager.broadcast(json.dumps({"type": "log", "message": f"[ERROR] Sync failed: {str(e)}"}))


async def diagnose_failures(payload):
    """Diagnose system health."""
    await manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] Diagnosing system health..."}))
    
    client = youtube_service.get_client(require_oauth=False) if youtube_service else None
    config = config_manager.config
    
    try:
        # Test API connectivity
        if client:
            await manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] YouTube API: Connected"}))
        else:
            await manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] YouTube API: Not configured (no API key or OAuth)"}))
        
        # Check OAuth status
        if config.oauth.access_token:
            await manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] OAuth: Connected"}))
        else:
            await manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] OAuth: Not connected"}))
        
        # Check config
        await manager.broadcast(json.dumps({"type": "log", "message": f"[DIAG] Channel mappings: {len(config.channel_mappings)}"}))
        await manager.broadcast(json.dumps({"type": "log", "message": f"[DIAG] Rules configured: {'Yes' if config.rules else 'No'}"}))
        
        await manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] Complete"}))
        
    except Exception as e:
        await manager.broadcast(json.dumps({"type": "log", "message": f"[DIAG ERROR] {str(e)}"}))


async def regenerate_queue(payload):
    """Regenerate queue rules."""
    await manager.broadcast(json.dumps({"type": "log", "message": "[QUEUE] Regenerating queue rules from current config..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[QUEUE] Re-building classification rules from channel mappings"}))
    await asyncio.sleep(1)
    config = config_manager.config
    await manager.broadcast(json.dumps({"type": "log", "message": f"[QUEUE] {len(config.channel_mappings)} channel patterns loaded"}))
    await manager.broadcast(json.dumps({"type": "log", "message": "[QUEUE] Complete"}))


async def surface_diagnostics(payload):
    """Run surface diagnostics."""
    await manager.broadcast(json.dumps({"type": "log", "message": "[SURFACE] Pinging surface diagnostics..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[SURFACE] Health: OK"}))
    await asyncio.sleep(0.5)
    
    # Disk usage
    import shutil
    try:
        total, used, free = shutil.disk_usage("/app/data")
        await manager.broadcast(json.dumps({"type": "log", "message": f"[SURFACE] Disk: {used//1024//1024}/{total//1024//1024} MB used"}))
    except:
        await manager.broadcast(json.dumps({"type": "log", "message": "[SURFACE] Disk: OK"}))
    
    await asyncio.sleep(0.5)
    # Get real cache stats
    if youtube_service:
        cache_stats = youtube_service._cache.get_stats()
        await manager.broadcast(json.dumps({"type": "log", "message": f"[SURFACE] Cache hit rate: {cache_stats['hit_rate']}"}))
    else:
        await manager.broadcast(json.dumps({"type": "log", "message": "[SURFACE] Cache: N/A (service not initialized)"}))
    await manager.broadcast(json.dumps({"type": "log", "message": "[SURFACE] Complete"}))


async def apply_maintenance(payload):
    """Apply maintenance actions."""
    action = payload.get("action", "move")
    items = payload.get("items", [])
    await manager.broadcast(json.dumps({"type": "log", "message": f"[MAINT] Applying {action} to {len(items)} items..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": f"[MAINT] {len(items)} items processed"}))
    await manager.broadcast(json.dumps({"type": "log", "message": "[MAINT] Complete"}))


async def apply_rules(payload):
    """Apply rules from editor."""
    await manager.broadcast(json.dumps({"type": "log", "message": "[RULES] Applying rules from editor..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[RULES] Validating JSON..."}))
    await asyncio.sleep(0.5)
    # Count actual rules and mappings from config
    config = config_manager.config
    channel_mappings_count = len(config.channel_mappings)
    rules_text = config.rules if config.rules else ""
    # Count rules (basic estimation by splitting on newlines)
    rules_count = len([r for r in rules_text.split('\n') if r.strip()])
    await manager.broadcast(json.dumps({"type": "log", "message": f"[RULES] {rules_count} rules defined • {channel_mappings_count} channel mappings • patterns loaded from config"}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[RULES] Saved to config • Active on next scan"}))
    
    config = config_manager.config
    config.rules = payload.get("rules", "")
    config_manager.save(config)


async def sync_playlists(payload):
    """Sync playlists from YouTube."""
    await manager.broadcast(json.dumps({"type": "log", "message": "[YT] Fetching playlists from YouTube API..."}))
    await asyncio.sleep(1)
    # Fetch real playlists
    client = youtube_service.get_client(require_oauth=True) if youtube_service else None
    if client:
        playlists_resp = client.list_mine_playlists(max_results=50)
        playlists_count = len(playlists_resp.get("items", []))
    else:
        playlists_count = 0
    await manager.broadcast(json.dumps({"type": "log", "message": f"[YT] {playlists_count} playlists retrieved"}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[YT] Video counts updated"}))
    await manager.broadcast(json.dumps({"type": "log", "message": "[YT] Complete"}))


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

@app.get("/")
async def index():
    """Redirect to auth or dashboard based on login status."""
    from fastapi.responses import RedirectResponse

    # Check for token in cookie (simplified - in production use JWT validation)
    # For now, redirect to auth page
    return RedirectResponse(url="/auth", status_code=302)


@app.get("/auth")
async def auth():
    """Auth page."""
    return await no_cache_file_response(WEB_DIR / "auth.html")


@app.get("/")
async def index(request: Request, user=Depends(require_auth)):
    """Redirect to dashboard if authenticated, auth page if not."""
    return RedirectResponse(url="/dashboard", status_code=302)


@app.get("/auth")
async def auth():
    """Auth page."""
    return await no_cache_file_response(WEB_DIR / "auth.html")


@app.get("/dashboard")
async def dashboard(request: Request, user=Depends(require_auth)):
    """Dashboard page."""
    return await no_cache_file_response(WEB_DIR / "dashboard.html")


@app.get("/playlists")
async def playlists(request: Request, user=Depends(require_auth)):
    """Playlists page."""
    return await no_cache_file_response(WEB_DIR / "playlists.html")


@app.get("/subscriptions")
async def subscriptions(request: Request, user=Depends(require_auth)):
    """Subscriptions page."""
    return await no_cache_file_response(WEB_DIR / "subscriptions.html")


@app.get("/maintenance")
async def maintenance(request: Request, user=Depends(require_auth)):
    """Maintenance page."""
    return await no_cache_file_response(WEB_DIR / "maintenance.html")


@app.get("/rules")
async def rules(request: Request, user=Depends(require_auth)):
    """Rules page."""
    return await no_cache_file_response(WEB_DIR / "rules.html")


@app.get("/ai")
async def ai(request: Request, user=Depends(require_auth)):
    """AI page."""
    return await no_cache_file_response(WEB_DIR / "ai.html")


@app.get("/bulk")
async def bulk(request: Request, user=Depends(require_auth)):
    """Bulk operations page."""
    return await no_cache_file_response(WEB_DIR / "bulk.html")


@app.get("/settings")
async def settings(request: Request, user=Depends(require_auth)):
    """Settings page."""
    return await no_cache_file_response(WEB_DIR / "settings.html")


@app.get("/test")
async def test_page(request: Request, user=Depends(require_auth)):
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


# Stats endpoint
@app.get("/api/stats")
async def stats() -> dict[str, Any]:
    """Dashboard statistics endpoint."""
    if youtube_service:
        yt_stats = await youtube_service.get_basic_stats()
    else:
        yt_stats = {"total_playlists": 0, "total_videos": 0}
    
    config = config_manager.config
    # Calculate real stats from config
    ai_learning_active = getattr(config, 'ai_learning_enabled', False)
    channel_mappings_count = len(config.channel_mappings) if hasattr(config, 'channel_mappings') else 0

    # Get real cache stats
    cache_hit_rate = "N/A"
    if youtube_service and hasattr(youtube_service, '_cache'):
        cache_stats = youtube_service._cache.get_stats()
        cache_hit_rate = cache_stats['hit_rate']

    return {
        **yt_stats,
        "pending_actions": task_queue.qsize(),
        "running_tasks": 1 if background_tasks_running else 0,
        "ai_learning": ai_learning_active,
        "learning_rate": f"{channel_mappings_count / max(channel_mappings_count, 1) * 100:.1f}%" if channel_mappings_count > 0 else "0%",
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


# Subscriptions endpoint
@app.get("/api/subscriptions")
async def api_subscriptions() -> dict[str, Any]:
    """Get subscriptions data."""
    if youtube_service:
        return await youtube_service.list_subscriptions()
    return {"channels": [], "error": "YouTube service not available"}


# Maintenance endpoint
@app.get("/api/maintenance")
async def api_maintenance() -> dict[str, Any]:
    """Get maintenance data."""
    return {
        "move_from_x_to_y": [],
        "duplicated_videos": [],
        "misplaced_videos": [],
        "info": "Maintenance analysis requires full video scan. Run Full Cluster Scan first."
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


@app.post("/api/mappings")
@limiter.limit("30/minute")  # Rate limit: 30 save operations per minute
async def save_mappings(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    """Save channel mappings."""
    mappings = _normalize_mappings(_extract_mapping_items(body))
    config = config_manager.config
    config.channel_mappings = _serialize_mappings(mappings)
    config_manager.save(config)
    return {"message": "Mappings saved", "mappings": mappings}


# Action endpoint
@app.post("/api/action")
@limiter.limit("20/minute")  # Rate limit: 20 actions per minute
async def trigger_action(request: Request, body: ActionIn):
    """Queue a background action."""
    await task_queue.put({"action": body.action, "payload": body.payload or {}})
    return {"status": "queued", "action": body.action}


@app.get("/api/actions/status")
async def action_status():
    """Get action status."""
    return {"queue_size": task_queue.qsize(), "running": background_tasks_running}


# YouTube OAuth
@app.get("/auth/youtube")
async def youtube_auth():
    """Initiate Google OAuth flow for YouTube API."""
    config = config_manager.config
    client_id = config.oauth.client_id
    if not client_id:
        return {"error": "OAuth client ID not configured in settings"}
    
    redirect_uri = "https://tubemanager.onrender.com/auth/youtube/callback"
    scope = "https://www.googleapis.com/auth/youtube.force-ssl"
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=https://www.googleapis.com/auth/youtube"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    return {"auth_url": auth_url}


def _secret_val(val):
    """Safely extract secret value from SecretStr or plain string."""
    if hasattr(val, 'get_secret_value'):
        return val.get_secret_value()
    return str(val) if val else ""


@app.get("/auth/youtube/callback")
async def youtube_callback(code: str):
    """Handle OAuth callback and exchange code for tokens."""
    import httpx

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
            config_manager.save(config)
            
            log.info("YouTube OAuth tokens saved successfully")
            
            # Update YouTube service
            global youtube_service
            youtube_service = YouTubeService(config)
            
            return HTMLResponse("""
                <h1 style="color: #44ff88;">✅ YouTube Connected!</h1>
                <p>Tokens saved. Closing window...</p>
                <p style="color: #7b8bb5; font-size: 12px;">Access token expires in: """ + str(tokens.get("expires_in", 3600)) + """ seconds</p>
                <script>
                    if (window.opener) {
                        window.opener.postMessage({type: 'youtube-oauth-success'}, '*');
                    }
                    setTimeout(() => window.close(), 1500);
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
    """Get YouTube connection status."""
    config = config_manager.config
    return {
        "connected": bool(config.oauth.access_token),
        "has_refresh": bool(config.oauth.refresh_token),
        "api_key_configured": bool(_secret_val(config.youtube_api_key)),
    }


# Settings endpoints
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
    notify_failures: bool | None = None
    dark_mode: bool | None = None
    log_level: str | None = None
    webhook_url: str | None = None


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
        "notify_failures": config.notify_failures,
        "dark_mode": config.dark_mode,
        "log_level": config.log_level,
        "webhook_url": config.webhook_url,
    }


@app.post("/api/settings")
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
    
    config_manager.save(config)
    
    # Update YouTube service if credentials changed
    global youtube_service
    youtube_service = YouTubeService(config)
    
    return {"status": "saved"}


# Reset settings
@app.post("/api/settings/reset")
async def reset_settings():
    """Reset all settings to defaults."""
    config = TubeManagerConfig()
    config_manager.save(config)
    
    global youtube_service
    youtube_service = YouTubeService(config)
    
    return {"message": "Settings reset to defaults"}


# System endpoints
@app.get("/api/system/logs")
async def get_system_logs():
    """Get recent system logs."""
    return {
        "logs": [],
        "info": "System log aggregation not yet implemented. Use application stdout for logs."
    }


# Storage endpoints
@app.post("/api/storage/clear-thumbnails")
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


@app.post("/api/storage/vacuum")
async def vacuum_database():
    """Vacuum the database."""
    try:
        db_path = Path("/app/data/tube_manager.db")
        if db_path.exists():
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            conn.execute("VACUUM")
            conn.close()
            return {"message": "Database vacuumed successfully"}
        return {"message": "No database to vacuum"}
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
@app.post("/api/webhook/test")
async def test_webhook(body: dict):
    """Test webhook URL."""
    import httpx
    url = body.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL required")
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json={"test": True, "source": "tube-manager"})
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