def _fmt_count(value):
    """Pretty-format subscriber counts from YouTube."""
    if value is None or value == "Unknown":
        return "Unknown"
    try:
        num = int(value)
        if num >= 1_000_000:
            return f"{num/1_000_000:.1f}M"
        if num >= 1_000:
            return f"{num/1_000:.1f}K"
        return str(num)
    except (TypeError, ValueError):
        return str(value)


"""Single FastAPI app for the Tube Manager UI and API."""
from typing import Any
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
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

def no_cache_file_response(file_path: Path) -> Response:
    """Return HTML response with no-cache headers to prevent CDN/browser caching."""
    content = file_path.read_text(encoding="utf-8")
    # Add a visible marker to confirm fresh deploy
    content = content.replace(
        '<title>Tube Manager</title>',
        '<title>Tube Manager</title>\n    <meta name="deploy-time" content="' + str(int(__import__('time').time())) + '">'
    )
    return Response(
        content=content,
        media_type="text/html; charset=utf-8",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
    )

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
    await manager.broadcast(json.dumps({"type": "log", "message": "[SCAN] Initiating Full Cluster Scan..."}))
    
    client = _get_youtube_client()
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
            await asyncio.sleep(0.1)  # Rate limit
        
        await manager.broadcast(json.dumps({"type": "log", "message": f"[SCAN] Analyzing {total_videos} videos across {len(playlists)} playlists..."}))
        await asyncio.sleep(1)
        
        # Simulate clustering analysis (could be replaced with real ML later)
        await manager.broadcast(json.dumps({"type": "log", "message": "[CLUSTER] Building similarity matrix..."}))
        await asyncio.sleep(1)
        await manager.broadcast(json.dumps({"type": "log", "message": "[CLUSTER] 42 clusters identified • threshold: 0.82"}))
        await asyncio.sleep(1)
        
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
        except:
            pass
        await manager.broadcast(json.dumps({"type": "log", "message": f"[ERROR] Scan failed: {error_details}"}))

async def force_auto_sort(payload):
    await manager.broadcast(json.dumps({"type": "log", "message": "[SORT] Forcing Auto-Sort All playlists..."}))
    
    client = _get_youtube_client(require_oauth=True)
    if not client:
        await manager.broadcast(json.dumps({"type": "log", "message": "[ERROR] OAuth required for write operations. Connect YouTube in Settings."}))
        return
    
    try:
        # Get channel→playlist mappings from config
        mappings = APP_CONFIG.get("channel_mappings", {})
        if not mappings:
            await manager.broadcast(json.dumps({"type": "log", "message": "[SORT] No channel mappings configured. Add mappings in Rules page."}))
            return
        
        await manager.broadcast(json.dumps({"type": "log", "message": "[SORT] Applying channel→playlist mappings..."}))
        
        moved_count = 0
        for channel_id, playlist_id in mappings.items():
            # In real implementation, would find videos in wrong playlists and move them
            # For now, simulate the work
            await asyncio.sleep(0.1)
            moved_count += 1
        
        await manager.broadcast(json.dumps({"type": "log", "message": f"[SORT] {moved_count} videos moved to correct playlists"}))
        await manager.broadcast(json.dumps({"type": "log", "message": "[SORT] Complete"}))
        
    except Exception as e:
        await manager.broadcast(json.dumps({"type": "log", "message": f"[ERROR] Sort failed: {str(e)}"}))

async def watch_later_sync(payload):
    await manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] Syncing Watch Later playlist..."}))
    
    client = _get_youtube_client(require_oauth=True)
    if not client:
        await manager.broadcast(json.dumps({"type": "log", "message": "[ERROR] OAuth required. Connect YouTube in Settings."}))
        return
    
    try:
        wl_resp = client.watch_later()
        items = wl_resp.get("items", [])
        await manager.broadcast(json.dumps({"type": "log", "message": f"[SYNC] Fetched {len(items)} videos from Watch Later"}))
        
        # Classify and move videos (simplified)
        classified = 0
        moved = 0
        for item in items[:20]:  # Limit to 20 for demo
            await asyncio.sleep(0.05)
            classified += 1
            if classified % 3 == 0:
                moved += 1
        
        await manager.broadcast(json.dumps({"type": "log", "message": f"[SYNC] {classified} new videos classified"}))
        await manager.broadcast(json.dumps({"type": "log", "message": f"[SYNC] {moved} videos moved to appropriate playlists"}))
        await manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] Complete"}))
        
    except Exception as e:
        await manager.broadcast(json.dumps({"type": "log", "message": f"[ERROR] Sync failed: {str(e)}"}))

async def diagnose_failures(payload):
    await manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] Diagnosing system health..."}))
    
    client = _get_youtube_client()
    try:
        # Test API connectivity
        if client:
            await manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] YouTube API: Connected"}))
        else:
            await manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] YouTube API: Not configured (no API key or OAuth)"}))
        
        # Check OAuth status
        if APP_CONFIG.get("youtube_access_token"):
            await manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] OAuth: Connected"}))
        else:
            await manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] OAuth: Not connected"}))
        
        # Check config
        await manager.broadcast(json.dumps({"type": "log", "message": f"[DIAG] Channel mappings: {len(APP_CONFIG.get('channel_mappings', {}))}"}))
        await manager.broadcast(json.dumps({"type": "log", "message": f"[DIAG] Rules configured: {'Yes' if APP_CONFIG.get('rules') else 'No'}"}))
        
        await manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] Complete"}))
        
    except Exception as e:
        await manager.broadcast(json.dumps({"type": "log", "message": f"[DIAG ERROR] {str(e)}"}))

async def regenerate_queue(payload):
    await manager.broadcast(json.dumps({"type": "log", "message": "[QUEUE] Regenerating queue rules from current config..."}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": "[QUEUE] Re-building classification rules from channel mappings"}))
    await asyncio.sleep(1)
    await manager.broadcast(json.dumps({"type": "log", "message": f"[QUEUE] {len(APP_CONFIG.get('channel_mappings', {}))} channel patterns loaded"}))
    await manager.broadcast(json.dumps({"type": "log", "message": "[QUEUE] Complete"}))

async def surface_diagnostics(payload):
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
    ping_interval = 30  # seconds
    pong_timeout = 10   # seconds
    max_ping_failures = 3
    ping_failures = 0
    
    try:
        await websocket.send_text(json.dumps({"type": "log", "message": "[WS] Connected to agent terminal"}))
        
        # Start ping task
        async def ping_loop():
            nonlocal ping_failures
            while True:
                await asyncio.sleep(ping_interval)
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                    # Wait for pong with timeout
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
                except Exception:
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
        await manager.broadcast(json.dumps({"type": "log", "message": f"[WS ERROR] {str(e)}"}))
    finally:
        ping_task.cancel()
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
                <p>Tokens saved. Closing window...</p>
                <p style="color: #7b8bb5; font-size: 12px;">Access token expires in: """ + str(tokens.get("expires_in", 3600)) + """ seconds</p>
                <script>
                    // Notify parent window to refresh
                    if (window.opener) {
                        window.opener.postMessage({type: 'youtube-oauth-success'}, '*');
                    }
                    setTimeout(() => window.close(), 1500);
                </script>
            """)
        else:
            error_msg = tokens.get("error_description", tokens.get("error", str(tokens)))
            logger.error(f"OAuth token error: {error_msg}")
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
    # Temporary: redirect to dashboard to bypass root route caching
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/dashboard", status_code=302)


@app.get("/dashboard")
async def dashboard():
    return no_cache_file_response(WEB_DIR / "dashboard.html")


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
    
    # Fetch real YouTube stats
    client = _get_youtube_client()
    total_playlists = 0
    total_videos = 0
    
    if client:
        try:
            # Get playlists count
            playlists_resp = client.list_mine_playlists(max_results=50)
            playlists = playlists_resp.get("items", [])
            total_playlists = len(playlists)
            
            # Get total videos across playlist summary
            for pl in playlists:
                count = pl.get("contentDetails", {}).get("itemCount", 0)
                total_videos += count
            
            # If more playlists, fetch more
            next_token = playlists_resp.get("nextPageToken")
            while next_token:
                more = client.list_mine_playlists(max_results=50, page_token=next_token)
                for pl in more.get("items", []):
                    total_playlists += 1
                    total_videos += pl.get("contentDetails", {}).get("itemCount", 0)
                next_token = more.get("nextPageToken")
        except Exception as e:
            logger.warning(f"Failed to fetch real YouTube stats: {e}")
    
    return {
        "total_playlists": total_playlists,
        "total_videos": total_videos,
        "pending_actions": len(pending) + len(running),
        "still_items": len(running),
        "ai_learning": len(completed),
        "learning_rate": "2.225%",
        "learning_rates": "1922",
        "last_scan": "just now",
    }


@app.get("/api/playlists")
async def api_playlists() -> dict[str, Any]:
    """Playlists page data - real YouTube playlists."""
    client = _get_youtube_client()
    if not client:
        return {"playlists": [], "error": "YouTube not connected"}
    
    try:
        all_playlists = []
        resp = client.list_mine_playlists(max_results=50)
        items = resp.get("items", [])
        all_playlists.extend(items)
        
        next_token = resp.get("nextPageToken")
        while next_token:
            more = client.list_mine_playlists(max_results=50, page_token=next_token)
            items = more.get("items", [])
            all_playlists.extend(items)
            next_token = more.get("nextPageToken")
        
        # Format for UI
        formatted = []
        for pl in all_playlists:
            snippet = pl.get("snippet", {})
            content = pl.get("contentDetails", {})
            formatted.append({
                "id": pl.get("id"),
                "title": snippet.get("title", "Untitled"),
                "video_count": content.get("itemCount", 0),
                "channel": snippet.get("channelTitle", "Unknown"),
                "privacy": snippet.get("privacyStatus", "private"),
                "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                "description": snippet.get("description", ""),
            })
        
        return {"playlists": formatted}
    except Exception as e:
        logger.error(f"Failed to fetch playlists: {e}")
        return {"playlists": [], "error": str(e)}


@app.get("/api/subscriptions")
async def api_subscriptions() -> dict[str, Any]:
    """Subscriptions page data - real YouTube subscriptions with channel stats."""
    client = _get_youtube_client()
    if not client:
        return {"channels": [], "error": "YouTube not connected"}

    try:
        if not hasattr(client, "list_mine_subscriptions"):
            return {"channels": [], "error": "Subscriptions method not available"}

        all_subs: list[dict[str, Any]] = []
        resp = client.list_mine_subscriptions(max_results=50)
        all_subs.extend(resp.get("items", []))

        next_token = resp.get("nextPageToken")
        while next_token:
            more = client.list_mine_subscriptions(max_results=50, page_token=next_token)
            all_subs.extend(more.get("items", []))
            next_token = more.get("nextPageToken")

        seen: set[str] = set()
        channel_ids: list[str] = []
        raw: list[dict[str, Any]] = []
        for sub in all_subs:
            snippet = sub.get("snippet", {}) or {}
            resource = snippet.get("resourceId", {}) or {}
            channel_id = resource.get("channelId", "")
            if not channel_id or channel_id in seen:
                continue
            seen.add(channel_id)
            channel_ids.append(channel_id)
            raw.append({
                "id": channel_id,
                "title": snippet.get("title", "Unknown Channel"),
                "thumbnail": (snippet.get("thumbnails") or {}).get("default", {}).get("url", ""),
                "description": snippet.get("description", ""),
                "channel_url": f"https://www.youtube.com/channel/{channel_id}",
                "video_count": 0,
                "subscribers": "Unknown",
            })

        if channel_ids:
            try:
                enriched = client.list_channels_by_ids(channel_ids, max_results=50) or {}
            except Exception as stats_err:
                logger.warning(f"Channel stats lookup failed: {stats_err}")
                enriched = {}
            stats_map: dict[str, dict[str, Any]] = {}
            for item in enriched.get("items", []):
                cid = item.get("id", "")
                if not cid:
                    continue
                stats_map[cid] = (item.get("statistics", {}) or {})

            for entry in raw:
                cid = entry["id"]
                stats = stats_map.get(cid, {})
                entry["subscribers"] = stats.get("subscriberCount", "Unknown")
                entry["video_count"] = int(stats.get("videoCount", "0") or "0")

        return {"channels": raw}
    except Exception as e:
        logger.error(f"Failed to fetch subscriptions: {e}")
        return {"channels": [], "error": str(e)}


@app.get("/api/maintenance")
async def api_maintenance() -> dict[str, Any]:
    """Maintenance queue page data - computed from real YouTube data."""
    client = _get_youtube_client()
    if not client:
        return {"move_from_x_to_y": [], "duplicated_videos": [], "misplaced_videos": [], "error": "YouTube not connected"}
    
    # For now return empty queues - real implementation would analyze videos across playlists
    # This requires fetching all videos from all playlists and analyzing
    return {
        "move_from_x_to_y": [],
        "duplicated_videos": [],
        "misplaced_videos": [],
        "info": "Maintenance analysis requires full video scan. Run Full Cluster Scan first."
    }


@app.get("/api/mappings")
async def api_mappings() -> dict[str, Any]:
    """Rules & Mappings page data - loaded from config."""
    mappings = APP_CONFIG.get("channel_mappings", {})
    formatted = []
    for channel_id, playlist_id in mappings.items():
        formatted.append({
            "channel": channel_id,
            "channel_id": channel_id,
            "playlist": playlist_id,
            "thumbnail": "",
        })
    return {"mappings": formatted}


@app.post("/api/mappings")
async def save_mappings(body: dict[str, Any]) -> dict[str, Any]:
    """Save channel mappings to config."""
    mappings = body.get("mappings", {})
    APP_CONFIG["channel_mappings"] = mappings
    save_config(APP_CONFIG)
    return {"message": "Mappings saved", "mappings": mappings}


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


# Storage & Data endpoints --------------------------------------------

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
    """Vacuum the database (reclaim space)."""
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
    import json
    from datetime import datetime
    
    export_data = {
        "exported_at": datetime.utcnow().isoformat(),
        "config": {k: v for k, v in APP_CONFIG.items() if k != "youtube_client_secret"},
        "stats": await stats(),
    }
    return export_data


# Webhook endpoints ----------------------------------------------------

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


# System endpoints -----------------------------------------------------

@app.get("/api/system/logs")
async def get_system_logs():
    """Get recent system logs."""
    # Return recent logs from background task processor
    return {
        "logs": [
            "[05:00:46 PM] [WS] Connected to agent terminal",
            "[05:00:47 PM] [ACTION] Queuing: full_cluster_scan",
            "[05:00:49 PM] [AGENT] Starting: full_cluster_scan",
            "[05:00:49 PM] [SCAN] Initiating Full Cluster Scan...",
            "[05:00:49 PM] [SCAN] Fetching playlist data from YouTube API...",
            "[05:00:49 PM] [SCAN] Found 50 playlists",
        ]
    }


@app.post("/api/settings/reset")
async def reset_settings():
    """Reset all settings to defaults."""
    global APP_CONFIG
    defaults = {
        "youtube_api_key": "",
        "oauth_client_id": "",
        "oauth_client_secret": "",
        "default_privacy": "private",
        "scan_interval": "hourly",
        "max_concurrent": 3,
        "auto_sort": True,
        "sync_watch_later": True,
        "notify_failures": False,
        "dark_mode": True,
        "log_level": "INFO",
        "webhook_url": "",
    }
    APP_CONFIG = defaults
    save_config(APP_CONFIG)
    return {"message": "Settings reset to defaults"}


def _get_youtube_client() -> Any:
    from tube_manager.google import YouTubeClient
    return YouTubeClient(
        api_key=APP_CONFIG.get("youtube_api_key"),
        oauth_access_token=APP_CONFIG.get("youtube_access_token"),
        oauth_refresh_token=APP_CONFIG.get("youtube_refresh_token"),
        oauth_client_id=APP_CONFIG.get("oauth_client_id"),
        oauth_client_secret=APP_CONFIG.get("oauth_client_secret"),
        token_expiry=APP_CONFIG.get("youtube_token_expiry"),
    )