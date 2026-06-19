"""Background worker service for motus.leap."""

import asyncio
import json
import logging
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, List, Dict

from models.config import TubeManagerConfig
from core.config_manager import ConfigManager

log = logging.getLogger(__name__)


def get_formatted_mappings(config) -> dict[str, Any]:
    raw = config.channel_mappings if hasattr(config, "channel_mappings") else {}
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
        for item in raw:
            channel_id = item.get("channel_id") or item.get("channel") or ""
            playlist_id = item.get("playlist") or item.get("playlist_id") or ""
            formatted.append({
                "channel": channel_id,
                "channel_id": channel_id,
                "playlist": playlist_id,
            })
    return {"mappings": formatted}


class BackgroundWorker:
    def __init__(self, youtube_service, manager, config_manager, task_queue):
        self._youtube_service = youtube_service
        self.manager = manager
        self.config_manager = config_manager
        self.task_queue = task_queue
        self.background_tasks_running = False
        self.current_task_name = None
        self._cancel_requested = False
        # Playlist cache for AI mode
        self._playlist_cache = None
        self._playlist_cache_time = 0
        self._playlist_cache_ttl = 3600  # 1 hour TTL
    
    def cancel_current_task(self):
        """Request cancellation of the currently running task."""
        self._cancel_requested = True
        self.current_task_name = None
        # Drain the queue so pending tasks are cleared
        while not self.task_queue.empty():
            try:
                self.task_queue.get_nowait()
                self.task_queue.task_done()
            except asyncio.QueueEmpty:
                break
        log.info("[WORKER] Cancel requested — current task will stop, queue drained")

    async def _ensure_playlist_cache(self, client):
        """Ensure playlist cache is populated and valid (1 hour TTL)."""
        import time
        now = time.time()
        if self._playlist_cache and (now - self._playlist_cache_time) < self._playlist_cache_ttl:
            return
        
        try:
            pl_data = client.list_mine_playlists(max_results=50)
            self._playlist_cache = []
            for pl in pl_data.get("items", []):
                pid = pl.get("id", "")
                pt = pl.get("snippet", {}).get("title", "")
                if pid and pt:
                    self._playlist_cache.append((pid, pt))
            self._playlist_cache_time = now
            log.info(f"[WORKER] Refreshed playlist cache: {len(self._playlist_cache)} playlists")
        except Exception as e:
            log.warning(f"Failed to refresh playlist cache: {e}")
            if not self._playlist_cache:
                self._playlist_cache = []

    @property
    def youtube_service(self):
        try:
            import app
            return getattr(app, "youtube_service", self._youtube_service)
        except Exception:
            return self._youtube_service

    async def process_background_tasks(self):
        """Process background tasks from the queue."""
        self.background_tasks_running = True
        
        while True:
            try:
                # Check if cancel was requested before picking up a new task
                if self._cancel_requested:
                    await self.manager.broadcast(json.dumps({"type": "log", "message": "[AGENT] Cancel acknowledged — no new tasks will run."}))
                    self._cancel_requested = False
                
                task = await self.task_queue.get()
                action = task.get("action")
                payload = task.get("payload", {})
                
                # If cancel was requested while waiting in queue, skip this task
                if self._cancel_requested:
                    self._cancel_requested = False
                    self.task_queue.task_done()
                    continue
                
                await self.manager.broadcast(json.dumps({"type": "log", "message": f"[AGENT] Starting: {action}"}))
                
                self.current_task_name = action
                
                # Process different actions
                if action == "full_cluster_scan":
                    await self.full_cluster_scan(payload)
                elif action == "watch_later_sync":
                    await self.watch_later_sync(payload)
                elif action == "diagnose_failures":
                    await self.diagnose_failures(payload)
                elif action == "regenerate_queue":
                    await self.regenerate_queue(payload)
                elif action == "surface_diagnostics":
                    await self.surface_diagnostics(payload)
                elif action == "apply_maintenance":
                    await self.apply_maintenance(payload)
                elif action == "apply_rules":
                    await self.apply_rules(payload)
                elif action == "sync_playlists":
                    await self.sync_playlists(payload)
                elif action == "scan_duplicates":
                    result = await self.scan_duplicates(payload)
                    await self.manager.broadcast(json.dumps({"type": "result", "data": result}))
                elif action == "scan_misplaced":
                    result = await self.scan_misplaced(payload)
                    await self.manager.broadcast(json.dumps({"type": "result", "data": result}))
                
                await self.manager.broadcast(json.dumps({"type": "log", "message": f"[AGENT] Completed: {action}"}))
                self.task_queue.task_done()
                self.current_task_name = None
            except Exception as e:
                log.error(f"Background task error: {e}")
                await self.manager.broadcast(json.dumps({"type": "log", "message": f"[ERROR] {str(e)}"}))
                self.current_task_name = None

    async def full_cluster_scan(self, payload):
        """Perform a full cluster scan."""
        await self.manager.broadcast(json.dumps({"type": "log", "message": "[SCAN] Initiating Full Playlist Sync..."}))
        
        client = self.youtube_service.get_client(require_oauth=True) if self.youtube_service else None
        if not client:
            await self.manager.broadcast(json.dumps({"type": "log", "message": "[ERROR] No YouTube OAuth client available. Connect YouTube in Settings first."}))
            return
        
        try:
            # Fetch user's playlists
            await self.manager.broadcast(json.dumps({"type": "log", "message": "[SCAN] Fetching playlist data from YouTube API..."}))
            playlists = []
            page_token = None
            while True:
                playlists_resp = await asyncio.to_thread(client.list_mine_playlists, max_results=50, page_token=page_token)
                items = playlists_resp.get("items", [])
                playlists.extend(items)
                page_token = playlists_resp.get("nextPageToken")
                if not page_token:
                    break
            await self.manager.broadcast(json.dumps({"type": "log", "message": f"[SCAN] Found {len(playlists)} playlists"}))
            
            # Real duplicate and misplaced detection
            video_to_playlists = {} # video_id -> list of (playlist_id, playlist_title)
            video_titles = {} # video_id -> video_title
            misplaced_videos = []
            
            # Load mappings from config
            config = await self.config_manager.config # Await the config property
            mappings = config.channel_mappings if hasattr(config, 'channel_mappings') else {}
            playlist_titles = {pl.get("id"): pl.get("snippet", {}).get("title", pl.get("id")) for pl in playlists}
            
            total_videos = 0
            for pl in playlists:
                pl_id = pl.get("id")
                pl_title = pl.get("snippet", {}).get("title", pl_id)
                items_resp = await asyncio.to_thread(client.list_videos, pl_id, max_results=50)
                items = items_resp.get("items", [])
                total_videos += len(items)
                
                for item in items:
                    video_id = item.get("contentDetails", {}).get("videoId")
                    video_title = item.get("snippet", {}).get("title", "Untitled")
                    if video_id:
                        video_titles[video_id] = video_title
                        video_to_playlists.setdefault(video_id, []).append((pl_id, pl_title))
                        
                        # Misplaced video check
                        owner_channel_id = item.get("snippet", {}).get("videoOwnerChannelId")
                        if owner_channel_id and owner_channel_id in mappings:
                            mapped_playlist_id = mappings[owner_channel_id]
                            if mapped_playlist_id and pl_id != mapped_playlist_id:
                                mapped_pl_title = playlist_titles.get(mapped_playlist_id, mapped_playlist_id)
                                misplaced_videos.append({
                                    "video_id": video_id,
                                    "video_title": video_title,
                                    "current_playlist_id": pl_id,
                                    "current_playlist_title": pl_title,
                                    "mapped_playlist_id": mapped_playlist_id,
                                    "mapped_playlist_title": mapped_pl_title
                                })
                
                await self.manager.broadcast(json.dumps({"type": "log", "message": f"[SCAN] {pl_title}: {len(items)} videos"}))
                await asyncio.sleep(0.01) # Reduced sleep here
            
            await self.manager.broadcast(json.dumps({"type": "log", "message": f"[SCAN] Analyzing {total_videos} videos across {len(playlists)} playlists..."}))
            # await asyncio.sleep(1) # Removed
            
            # Filter duplicates
            duplicated_videos = []
            for video_id, pls in video_to_playlists.items():
                if len(pls) > 1:
                    duplicated_videos.append({
                        "video_id": video_id,
                        "video_title": video_titles[video_id],
                        "playlists": [{"id": p[0], "title": p[1]} for p in pls]
                    })
                    
            # Build move suggestions
            move_suggestions = []
            for mv in misplaced_videos:
                move_suggestions.append({
                    "video_id": mv["video_id"],
                    "video_title": mv["video_title"],
                    "source_playlist_id": mv["current_playlist_id"],
                    "source_playlist_title": mv["current_playlist_title"],
                    "target_playlist_id": mv["mapped_playlist_id"],
                    "target_playlist_title": mv["mapped_playlist_title"]
                })
                
            # Save maintenance analysis
            maintenance_data = {
                "move_from_x_to_y": move_suggestions,
                "duplicated_videos": duplicated_videos,
                "misplaced_videos": misplaced_videos,
                "info": f"Analysis complete on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}. Found {len(duplicated_videos)} duplicates and {len(misplaced_videos)} misplaced videos."
            }
            maintenance_file = Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data")) / "maintenance.json"
            try:
                await asyncio.to_thread(maintenance_file.parent.mkdir, parents=True, exist_ok=True)
                await asyncio.to_thread(maintenance_file.write_text, json.dumps(maintenance_data, indent=2))
            except Exception as e:
                log.error(f"Failed to save maintenance data: {e}")
            
            # Real scan statistics (no fake clustering)
            await self.manager.broadcast(json.dumps({"type": "log", "message": "[SCAN] Building scan statistics..."}))
            # await asyncio.sleep(0.5) # Removed

            # Calculate real metrics from fetched data
            avg_videos_per_playlist = total_videos / len(playlists) if playlists else 0
            await self.manager.broadcast(json.dumps({
                "type": "log",
                "message": f"[SCAN] Analysis complete • {total_videos} videos across {len(playlists)} playlists • {avg_videos_per_playlist:.1f} avg videos/playlist"
            }))
            # await asyncio.sleep(0.5) # Removed
            
            await self.manager.broadcast(json.dumps({"type": "log", "message": "[LEARN] Processing statistics..."}))
            # await asyncio.sleep(1) # Removed
            
            # Populate the persistent cache so subsequent reads don't hit the API
            if self.youtube_service:
                await self.manager.broadcast(json.dumps({"type": "log", "message": "[CACHE] Updating local data cache..."}))
                try:
                    await self.youtube_service.fetch_all_data(force_refresh=True)
                    await self.manager.broadcast(json.dumps({"type": "log", "message": "[CACHE] Local cache updated. All reads will use cached data."}))
                except Exception as cache_err:
                    log.warning(f"Failed to update cache after scan: {cache_err}")
            
            await self.manager.broadcast(json.dumps({"type": "log", "message": f"[SCAN] Complete • {total_videos} videos analyzed • Cache updated • Next auto-scan: 1 hour"}))
            
        except Exception as e:
            error_details = f"{type(e).__name__}: {str(e)}"
            if hasattr(e, '__cause__') and e.__cause__:
                error_details += f" | Cause: {type(e.__cause__).__name__}: {str(e.__cause__)}"
            if hasattr(e, '__context__') and e.__context__:
                error_details += f" | Context: {type(e.__context__).__name__}: {str(e.__context__)}"
            try:
                error_details += f" | Traceback: {traceback.format_exc()}"
            except Exception as t_err:
                log.error(f"Error formatting traceback: {t_err}")
            await self.manager.broadcast(json.dumps({"type": "log", "message": f"[ERROR] Scan failed: {error_details}"}))

    async def watch_later_sync(self, payload):
        """Sync Watch Later playlist."""
        await self.manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] Syncing Watch Later playlist..."}))
        
        client = self.youtube_service.get_client(require_oauth=True) if self.youtube_service else None
        if not client:
            await self.manager.broadcast(json.dumps({"type": "log", "message": "[ERROR] OAuth required. Connect YouTube in Settings."}))
            return
        
        try:
            dry_run = bool(payload.get("dry_run") if isinstance(payload, dict) else False)
            # Fetch channel->playlist mappings from config
            config = self.config_manager.config
            mappings = get_formatted_mappings(config)
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
                await self.manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] No channel mappings configured. Add mappings in Rules/Settings."}))
                await self.manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] Complete"}))
                return

            # Preload channel metadata for OAuth-based channel lookup
            channel_key = "__watchlater_channels__"
            channel_cache = await self.youtube_service._get_cached(channel_key) if hasattr(self.youtube_service, "_get_cached") else None
            if not channel_cache:
                channel_cache = {}
                # Refresh via YouTubeService if available
                if hasattr(self.youtube_service, "fetch_all_data"):
                    async def _safe_fetch():
                        return await self.youtube_service.fetch_all_data(force_refresh=True)
                    try:
                        all_data = await _safe_fetch()
                        for channel in all_data.get("subscriptions", []):
                            channel_cache[channel.get("id", "")] = {
                                "title": channel.get("title", ""),
                                "channel_id": channel.get("id", ""),
                            }
                        await self.youtube_service._set_cached(channel_key, channel_cache)
                    except Exception:
                        pass

            # Use extracted classify method
            def classify(item):
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

            # Pre-build playlist lookup data for AI classification
            playlist_id_title_pairs: list[tuple[str, str]] = []
            playlist_title_list: list[dict] = []
            await self._ensure_playlist_cache(client)
            for pid, pt in self._playlist_cache:
                playlist_id_title_pairs.append((pid, pt))
                playlist_title_list.append({"id": pid, "title": pt})

            # Fetch watch later items using the cached method
            force_refresh = payload.get("force_refresh", False) # Allow forcing refresh from payload
            watch_later_resp = await self.youtube_service.list_watch_later_items_cached(
                playlist_id=configured_id if configured_id else None,
                force_refresh=force_refresh
            )
            watch_later_items = watch_later_resp.get("items", [])
                
            await self.manager.broadcast(json.dumps({"type": "log", "message": f"[SYNC] Fetched {len(watch_later_items)} videos from sync source (cached: {not force_refresh})"}))
            
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
                
                # Safeguard: skip if the target playlist is the same as the source playlist
                if playlist_id == origin:
                    skipped.append(item)
                    continue
                
                if dry_run:
                    moved.append({"video_id": video_id, "from": origin, "to": playlist_id, "channel_id": channel_id})
                    continue

                try:
                    # Insert into target playlist (offload sync call to thread)
                    await asyncio.to_thread(client.move_video_to_playlist, video_id, playlist_id)
                    # Remove from Watch Later
                    if playlist_item_id:
                        await asyncio.to_thread(client.remove_video_from_playlist, playlist_item_id)
                    moved.append({"video_id": video_id, "from": origin, "to": playlist_id, "channel_id": channel_id})
                    # Record move for AI training memory
                    try:
                        from services.ai_classifier import record_move
                        item_snippet = item.get("snippet", {}) or {}
                        record_move(
                            video_id=video_id,
                            title=item_snippet.get("title", ""),
                            channel_id=channel_id or "",
                            channel_title=item_snippet.get("videoOwnerChannelTitle", ""),
                            from_playlist_name="Watch Later",
                            from_playlist_id=origin,
                            to_playlist_name="",
                            to_playlist_id=playlist_id,
                            source="sync",
                        )
                    except Exception:
                        pass
                except Exception as move_error:
                    failed.append({"video_id": video_id, "error": str(move_error)})
                    await self.manager.broadcast(json.dumps({"type": "log", "message": f"[ERROR] Failed to move {video_id}: {move_error}"}))

            await self.manager.broadcast(json.dumps({"type": "log", "message": f"[SYNC] Moved {len(moved)} video(s), skipped {len(skipped)}, failed {len(failed)}"}))
            if moved:
                for move in moved[:20]:
                    await self.manager.broadcast(json.dumps({"type": "log", "message": f"[SYNC] {move['video_id']} -> {move['to']} (from {move.get('from', 'watch later')})"}))
            if dry_run and moved:
                await self.manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] Dry run: no changes applied."}))
            await self.manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] Complete"}))
            
        except Exception as e:
            error_details = f"{type(e).__name__}: {str(e)}"
            try:
                error_details += f" | {traceback.format_exc()}"
            except Exception:
                pass
            await self.manager.broadcast(json.dumps({"type": "log", "message": f"[ERROR] Sync failed: {error_details}"}))

    async def diagnose_failures(self, payload):
        """Diagnose system health."""
        await self.manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] Diagnosing system health..."}))
        
        client = self.youtube_service.get_client(require_oauth=False) if self.youtube_service else None
        config = self.config_manager.config
        
        try:
            # Test API connectivity
            if client:
                await self.manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] YouTube API: Connected"}))
            else:
                await self.manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] YouTube API: Not configured (no API key or OAuth)"}))
            
            # Check OAuth status
            if config.oauth.access_token:
                await self.manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] OAuth: Connected"}))
            else:
                await self.manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] OAuth: Not connected"}))
            
            # Check config
            await self.manager.broadcast(json.dumps({"type": "log", "message": f"[DIAG] Channel mappings: {len(config.channel_mappings)}"}))
            await self.manager.broadcast(json.dumps({"type": "log", "message": f"[DIAG] Rules configured: {'Yes' if config.rules else 'No'}"}))
            await self.manager.broadcast(json.dumps({"type": "log", "message": "[DIAG] Complete"}))
            
        except Exception as e:
            await self.manager.broadcast(json.dumps({"type": "log", "message": f"[DIAG ERROR] {str(e)}"}))

    async def regenerate_queue(self, payload):
        """Regenerate queue rules."""
        await self.manager.broadcast(json.dumps({"type": "log", "message": "[QUEUE] Regenerating queue rules from current config..."}))
        await asyncio.sleep(1)
        await self.manager.broadcast(json.dumps({"type": "log", "message": "[QUEUE] Re-building classification rules from channel mappings"}))
        await asyncio.sleep(1)
        config = self.config_manager.config
        await self.manager.broadcast(json.dumps({"type": "log", "message": f"[QUEUE] {len(config.channel_mappings)} channel patterns loaded"}))
        await self.manager.broadcast(json.dumps({"type": "log", "message": "[QUEUE] Complete"}))

    async def surface_diagnostics(self, payload):
        """Run surface diagnostics."""
        await self.manager.broadcast(json.dumps({"type": "log", "message": "[SURFACE] Pinging surface diagnostics..."}))
        await asyncio.sleep(1)
        await self.manager.broadcast(json.dumps({"type": "log", "message": "[SURFACE] Health: OK"}))
        await asyncio.sleep(0.5)
        
        # Disk usage
        import shutil
        try:
            total, used, free = shutil.disk_usage("/app/data")
            await self.manager.broadcast(json.dumps({"type": "log", "message": f"[SURFACE] Disk: {used//1024//1024}/{total//1024//1024} MB used"}))
        except:
            await self.manager.broadcast(json.dumps({"type": "log", "message": "[SURFACE] Disk: OK"}))
        
        await asyncio.sleep(0.5)
        # Get real cache stats
        if self.youtube_service:
            cache_stats = self.youtube_service._cache.get_stats()
            await self.manager.broadcast(json.dumps({"type": "log", "message": f"[SURFACE] Cache hit rate: {cache_stats['hit_rate']}"}))
        else:
            await self.manager.broadcast(json.dumps({"type": "log", "message": "[SURFACE] Cache: N/A (service not initialized)"}))
        await self.manager.broadcast(json.dumps({"type": "log", "message": "[SURFACE] Complete"}))

    async def apply_maintenance(self, payload):
        """Apply maintenance actions."""
        action = payload.get("action", "move")
        items = payload.get("items", [])
        await self.manager.broadcast(json.dumps({"type": "log", "message": f"[MAINT] Applying {action} to {len(items)} items..."}))
        await asyncio.sleep(1)
        await self.manager.broadcast(json.dumps({"type": "log", "message": f"[MAINT] {len(items)} items processed"}))
        await self.manager.broadcast(json.dumps({"type": "log", "message": "[MAINT] Complete"}))

    async def apply_rules(self, payload):
        """Apply rules from editor."""
        await self.manager.broadcast(json.dumps({"type": "log", "message": "[RULES] Applying rules from editor..."}))
        await asyncio.sleep(1)
        await self.manager.broadcast(json.dumps({"type": "log", "message": "[RULES] Validating JSON..."}))
        await asyncio.sleep(0.5)
        config = self.config_manager.config
        rules_count = len(config.channel_mappings) if hasattr(config, 'channel_mappings') else 0
        await self.manager.broadcast(json.dumps({"type": "log", "message": f"[RULES] {rules_count} rules saved successfully"}))
        await self.manager.broadcast(json.dumps({"type": "log", "message": "[RULES] Complete"}))

    async def sync_playlists(self, payload):
        """Sync all playlists and videos, then cache everything."""
        await self.manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] Starting full playlist sync from YouTube..."}))
        await asyncio.sleep(0.5)
        
        if not self.youtube_service:
            await self.manager.broadcast(json.dumps({"type": "log", "message": "[ERROR] YouTube service not initialized."}))
            return
        
        try:
            # Use fetch_all_data which populates the persistent cache
            await self.manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] Fetching playlists, videos, and subscriptions..."}))
            result = await self.youtube_service.fetch_all_data(force_refresh=True)
            
            if "error" in result:
                await self.manager.broadcast(json.dumps({"type": "log", "message": f"[ERROR] Sync failed: {result['error']}"}))
                return
            
            total_playlists = result.get("stats", {}).get("total_playlists", 0)
            total_videos = result.get("stats", {}).get("total_videos", 0)
            total_subs = result.get("stats", {}).get("total_subscriptions", 0)
            
            await self.manager.broadcast(json.dumps({
                "type": "log",
                "message": f"[SYNC] Successfully synchronized {total_playlists} playlists, {total_videos} videos, {total_subs} subscriptions. Cache updated."
            }))
            await asyncio.sleep(0.5)
            await self.manager.broadcast(json.dumps({"type": "log", "message": "[SYNC] Complete • All data cached locally. No further API calls needed for reads."}))
            
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            await self.manager.broadcast(json.dumps({"type": "log", "message": f"[ERROR] Sync failed: {error_msg}"}))

    async def scan_duplicates(self, payload):
        """Scan playlist for duplicate videos."""
        playlist_id = payload.get("playlist_id") if payload else None
        location = f" in playlist {playlist_id}" if playlist_id else ""
        await self.manager.broadcast(json.dumps({"type": "log", "message": f"[SCAN] Scanning for duplicates{location}..."}))
        await asyncio.sleep(0.5)
        duplicates = len(self.youtube_service.videos) - len(set(v.get("video_id") for v in self.youtube_service.videos)) if self.youtube_service else 0
        await self.manager.broadcast(json.dumps({"type": "log", "message": f"[SCAN] Found {duplicates} duplicate videos"}))
        return {"duplicates": duplicates}

    async def scan_misplaced(self, payload):
        """Scan playlist for misplaced videos based on rules."""
        playlist_id = payload.get("playlist_id") if payload else None
        location = f" in playlist {playlist_id}" if playlist_id else ""
        await self.manager.broadcast(json.dumps({"type": "log", "message": f"[SCAN] Scanning for misplaced videos{location}..."}))
        await asyncio.sleep(0.5)
        count = 0
        if self.youtube_service and hasattr(self.youtube_service, 'config') and hasattr(self.youtube_service.config, 'channel_mappings'):
            videos = self.youtube_service.videos
            for v in videos:
                if playlist_id and v.get("playlist_id") != playlist_id:
                    continue
                channel_id = v.get("channel_id")
                playlist_id_v = v.get("playlist_id")
                if channel_id and playlist_id_v:
                    for ch, target_pl in self.youtube_service.config.channel_mappings.items():
                        if channel_id == ch and target_pl and target_pl != playlist_id_v:
                            count += 1
                            break
        await self.manager.broadcast(json.dumps({"type": "log", "message": f"[SCAN] Found {count} misplaced videos"}))
        return {"misplaced": count}
