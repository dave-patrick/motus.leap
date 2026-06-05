import os
import json
import uvicorn
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

import scheduler
from core import task_manager
from core.utils import (
    is_oauth_configured,
    get_user_file_path,
    extract_video_id,
    get_current_user
)
from routers import auth, playlists, maintenance, rules

app = FastAPI(title="YT Playlist Manager API")

# Register routers
app.include_router(auth.router)
app.include_router(playlists.router)
app.include_router(maintenance.router)
app.include_router(rules.router)

# Data models for root router
class SettingsRequest(BaseModel):
    gemini_api_key: str
    notification_webhook: str


# Start the background scheduler thread on startup
@app.on_event("startup")
def startup_event():
    scheduler.start_scheduler()
    print("FastAPI: Background scheduler successfully initialized.")

# Serve SPA
@app.get("/")
def read_root():
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    base_dir = os.path.dirname(__file__)
    return FileResponse(os.path.join(base_dir, "static", "index.html"), headers=headers)

@app.get("/api/status")
def get_status(user=Depends(get_current_user)):
    total_playlists = 0
    total_videos = 0
    pending_actions = 0
    ai_cache_hits = 0
    
    # 1. Total Playlists & Videos
    report_path = get_user_file_path("playlists_report.json", user)
    if os.path.exists(report_path):
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                report = json.load(f)
                total_playlists = len(report)
                total_videos = sum(p.get("video_count", 0) for p in report)
        except: pass
        
    # 2. Pending Actions
    maint_path = get_user_file_path("maintenance_actions.json", user)
    if os.path.exists(maint_path):
        try:
            with open(maint_path, "r", encoding="utf-8") as f:
                actions = json.load(f)
                pending_actions = len(actions)
        except: pass
        
    # 3. AI Cache Hits
    ai_pending = 0
    ai_reviewed = 0
    ai_total = 0
    class_path = get_user_file_path("ai_classifications.json", user)
    if os.path.exists(class_path):
        try:
            with open(class_path, "r", encoding="utf-8") as f:
                classifications = json.load(f)
                
            vid_to_playlist = {}
            if os.path.exists(report_path):
                try:
                    with open(report_path, "r", encoding="utf-8") as rf:
                        report = json.load(rf)
                    for p in report:
                        playlist_name = p.get("name")
                        for v in p.get("videos", []):
                            vid = extract_video_id(v.get("url", ""))
                            if vid:
                                vid_to_playlist[vid] = playlist_name
                except:
                    pass

            filtered_classifications = []
            for c in classifications:
                status = c.get("status")
                if status == 'pending':
                    curr_pl = vid_to_playlist.get(c.get("vid"))
                    cat = c.get("category")
                    if curr_pl and cat and curr_pl.lower() == cat.lower():
                        continue
                filtered_classifications.append(c)

            ai_total = len(filtered_classifications)
            ai_pending = sum(1 for c in filtered_classifications if c.get("status") == "pending")
            ai_reviewed = ai_total - ai_pending
            ai_cache_hits = ai_total
        except: pass
        
    if ai_total == 0:
        cache_path = get_user_file_path("ai_cache_hits.txt", user)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r") as f:
                    ai_cache_hits = int(f.read().strip() or "0")
                    ai_total = ai_cache_hits
            except: pass
        
    # 4. Last run
    last_run = "--:--"
    last_run_path = get_user_file_path("last_run.txt", user)
    if os.path.exists(last_run_path):
        try:
            with open(last_run_path, "r") as f:
                last_run = f.read().strip()
        except: pass
        
    engine_status = "running" if task_manager.is_running() else "idle"
    
    active_job = task_manager.get_active_job()
    if active_job == "generate_maintenance":
        progress_path = get_user_file_path("generate_progress.json", user)
        if os.path.exists(progress_path):
            try:
                with open(progress_path, "r") as f:
                    progress = json.load(f)
                    active_job = f"generate_maintenance ({progress['current']}/{progress['total']})"
            except:
                pass
                
    return {
        "total_playlists": total_playlists,
        "total_videos": total_videos,
        "pending_actions": pending_actions,
        "ai_cache_hits": ai_cache_hits,
        "ai_pending": ai_pending,
        "ai_reviewed": ai_reviewed,
        "ai_total": ai_total,
        "engine_status": engine_status,
        "active_job": active_job,
        "queued_jobs": [t["job_name"] for t in task_manager.queue],
        "last_run": last_run
    }

@app.post("/api/run-scan")
def run_scan(user=Depends(get_current_user)):
    if not is_oauth_configured():
        success, msg = task_manager.run_task("scan", ["cli.py", "scan"])
    else:
        user_id = user.get("user_id") if "user_id" in user else user.get("id")
        import yt_api
        success, msg = task_manager.run_function(
            "scan",
            yt_api.run_api_scan_and_save,
            (user_id,)
        )
    if success:
        return {"success": True, "message": "Starting scan in background..."}
    else:
        raise HTTPException(status_code=400, detail=msg)

@app.post("/api/run-sort")
def run_sort():
    success, msg = task_manager.run_task("sort", ["cli.py", "auto-sort"])
    if success:
        return {"success": True, "message": "Starting auto-sort in background..."}
    else:
        raise HTTPException(status_code=400, detail=msg)

@app.post("/api/tasks/stop")
def stop_current_task():
    success, msg = task_manager.stop_task()
    if success:
        return {"success": True, "message": msg}
    else:
        raise HTTPException(status_code=400, detail=msg)

@app.get("/api/logs")
def get_logs():
    log_path = os.path.join(os.path.dirname(__file__), "agent_run.log")
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
                return {"logs": content[-100000:]}
        except Exception as e:
            return {"logs": f"Error reading log file: {e}"}
    return {"logs": "No log output recorded yet."}

@app.post("/api/logs/clear")
def clear_logs():
    log_path = os.path.join(os.path.dirname(__file__), "agent_run.log")
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/screenshots/{name}")
def get_screenshot(name: str):
    name = os.path.basename(name)
    path = os.path.join(os.path.dirname(__file__), name)
    if os.path.exists(path):
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="Screenshot not found")

@app.get("/api/settings")
def api_get_settings():
    settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r") as f:
                data = json.load(f)
                key = data.get("gemini_api_key", "")
                masked_key = key[:4] + "*" * (len(key) - 8) + key[-4:] if len(key) > 8 else key
                return {
                    "gemini_api_key": masked_key,
                    "notification_webhook": data.get("notification_webhook", "")
                }
        except: pass
    return {"gemini_api_key": "", "notification_webhook": ""}

@app.post("/api/settings")
def save_settings(req: SettingsRequest):
    settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
    old_key = ""
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r") as f:
                old_key = json.load(f).get("gemini_api_key", "")
        except: pass
        
    api_key = req.gemini_api_key
    if "*" in api_key and old_key:
        api_key = old_key
        
    try:
        with open(settings_path, "w") as f:
            json.dump({
                "gemini_api_key": api_key,
                "notification_webhook": req.notification_webhook
            }, f, indent=2)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ImportCookiesRequest(BaseModel):
    cookies_txt: str  # Netscape-format cookie file content

@app.post("/api/sync-item-ids")
def sync_playlist_item_ids(background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    """Trigger a full YouTube API rescan to populate playlist_item_id in the cache."""
    from core.utils import is_oauth_configured, append_agent_log
    if not is_oauth_configured():
        raise HTTPException(status_code=400, detail="OAuth not configured")
    user_id = user.get("user_id") or user.get("id")
    
    def do_sync():
        import yt_api
        from core.utils import append_agent_log
        append_agent_log(f"Starting full playlist item ID sync for user {user_id}...")
        try:
            report = yt_api.run_api_scan_and_save(user_id)
            append_agent_log(f"Sync complete: {len(report)} playlists re-scanned with playlist_item_id.")
        except Exception as e:
            append_agent_log(f"Sync failed: {e}")
    
    background_tasks.add_task(do_sync)
    return {"success": True, "message": "Playlist item ID sync started in background. Check logs for progress."}

@app.post("/api/import-yt-cookies")
def import_yt_cookies(req: ImportCookiesRequest, user=Depends(get_current_user)):
    """Import Netscape-format YouTube cookies into the Camofox browser session."""
    import requests as req_lib
    from core.utils import append_agent_log
    
    # Parse Netscape cookie format
    cookies = []
    for line in req.cookies_txt.splitlines():
        line = line.strip()
        if not line or line.startswith("#") and not line.startswith("#HttpOnly_"):
            continue
        http_only = False
        if line.startswith("#HttpOnly_"):
            http_only = True
            line = line[len("#HttpOnly_"):]
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain = parts[0]
        cookie_path = parts[2]
        secure = parts[3].upper() == "TRUE"
        try:
            expires = float(parts[4])
        except:
            expires = -1
        name = parts[5]
        value = "\t".join(parts[6:])
        cookies.append({
            "name": name,
            "value": value,
            "domain": domain,
            "path": cookie_path,
            "expires": expires,
            "httpOnly": http_only,
            "secure": secure,
        })
    
    if not cookies:
        raise HTTPException(status_code=400, detail="No valid cookies found in the provided text.")
    
    # Filter to YouTube/Google cookies only
    yt_cookies = [c for c in cookies if any(x in c["domain"] for x in ["youtube", "google", "goog"])]
    if not yt_cookies:
        raise HTTPException(status_code=400, detail="No YouTube/Google cookies found. Make sure to export cookies from youtube.com.")
    
    # Import into Camofox
    camofox_url = "http://localhost:9377"
    camofox_user_id = "yt_playlist_agent_default"
    headers = {"Authorization": "Bearer my_secret_cookie_key", "Content-Type": "application/json"}
    
    try:
        resp = req_lib.post(
            f"{camofox_url}/sessions/{camofox_user_id}/cookies",
            headers=headers,
            json={"cookies": yt_cookies},
            timeout=30
        )
        if not resp.ok:
            raise HTTPException(status_code=500, detail=f"Camofox cookie import failed: {resp.status_code} {resp.text}")
    except req_lib.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="Camofox browser service is not running. Check that the camofox PM2 service is up.")
    
    # Save to ~/.camofox/cookies/cookies.txt for persistence on restart
    try:
        cookies_dir = os.path.expanduser("~/.camofox/cookies")
        os.makedirs(cookies_dir, exist_ok=True)
        cookies_file = os.path.join(cookies_dir, "cookies.txt")
        with open(cookies_file, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            for c in yt_cookies:
                http_only_prefix = "#HttpOnly_" if c.get("httpOnly") else ""
                secure_str = "TRUE" if c.get("secure") else "FALSE"
                exp = int(c.get("expires", -1)) if c.get("expires", -1) > 0 else 0
                f.write(f"{http_only_prefix}{c['domain']}\tTRUE\t{c['path']}\t{secure_str}\t{exp}\t{c['name']}\t{c['value']}\n")
    except Exception as e:
        append_agent_log(f"Warning: Could not save cookies to disk: {e}")
    
    append_agent_log(f"Imported {len(yt_cookies)} YouTube/Google cookies into Camofox browser session.")
    return {"success": True, "message": f"Successfully imported {len(yt_cookies)} cookies into the browser session.", "count": len(yt_cookies)}

# Mount static files (must be after endpoints to avoid shadowing)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
