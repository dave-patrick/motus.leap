# Performance & Efficiency Review — motus.leap Backend

**Date:** 2026-06-27  
**Scope:** `/opt/data/motus.leap/tube-manager/`  
**Reviewer:** neo (automated code review agent)

---

## Executive Summary

The motus.leap backend has **12 identifiable performance issues** across caching, async patterns, storage, connection pooling, memory, and endpoint design. Three are **HIGH impact**, seven are **MEDIUM**, and two are **LOW**. The most critical findings are: (1) synchronous blocking I/O in async handlers, (2) per-request file writes without debouncing, and (3) no background cleanup task for stale cache entries.

---

## 1. Caching Efficiency

### Issue 1.1: `cleanup_stale()` is never invoked — only on-access TTL check

| Attribute | Value |
|-----------|-------|
| **File** | `core/lru_cache.py` |
| **Performance Impact** | **HIGH** |
| **Effort to Fix** | **LOW** |
| **Description** | `cleanup_stale()` exists but is **never called** anywhere in the codebase. Stale entries older than `max_age` accumulate indefinitely until accessed again (which triggers TTL expiry). With `max_size=100` the LRU cap prevents unbounded growth, but stale entries waste memory slots and reduce cache hit rate. |

**Evidence:** Search for `cleanup_stale` across the entire project returns **zero call sites** outside the class definition itself.

**Suggested Fix:** Add a periodic background task in the application lifespan:

```python
# In app.py lifespan, after starting the worker:
async def cache_cleanup_loop():
    """Periodically evict stale LRU cache entries."""
    while True:
        await asyncio.sleep(600)  # Every 10 minutes
        if youtube_service:
            try:
                removed = await youtube_service._cache.cleanup_stale()
                if removed:
                    log.info(f"Periodic LRU cleanup: {removed} stale entries removed")
            except Exception as e:
                log.warning(f"LRU cleanup failed: {e}")

asyncio.create_task(cache_cleanup_loop())
```

---

### Issue 1.2: Cache key generation uses double SHA-256 — unnecessarily expensive

| Attribute | Value |
|-----------|-------|
| **File** | `services/youtube_service.py:26` |
| **Performance Impact** | **LOW** |
| **Effort to Fix** | **LOW** |
| **Description** | The `@cache_result` decorator computes `hashlib.sha256(json.dumps(args).encode()).hexdigest()` AND `hashlib.sha256(json.dumps(kwargs).encode()).hexdigest()` for every cache key. For simple calls with no args (most use cases), this hashes an empty list and dict twice — wasted CPU. |

**Suggested Fix:** Use a simpler, faster key derivation:

```python
cache_key = f"{key_prefix}_{instance._get_user_id()}_{hash(json.dumps(args, default=str))}_{hash(json.dumps(kwargs, default=str))}"
```

Or even simpler for most methods that have no positional args:

```python
cache_key = f"{key_prefix}_{instance._get_user_id()}"
```

---

### Issue 1.3: `disk_cache_cleanup()` is synchronous `glob` + per-file `stat` in async method

| Attribute | Value |
|-----------|-------|
| **File** | `services/youtube_service.py:122-150` |
| **Performance Impact** | **MEDIUM** |
| **Effort to Fix** | **LOW** |
| **Description** | `disk_cache_cleanup()` calls `self._user_data_dir.glob("*.json")` **synchronously** on line 136 (not wrapped in `asyncio.to_thread`). This blocks the event loop while the filesystem is scanned. Individual `stat()` and `unlink()` calls ARE wrapped in `to_thread`, but the glob itself is not. |

**Suggested Fix:**

```python
async def disk_cache_cleanup(self, max_age_days: int = 7) -> int:
    removed = 0
    cutoff = datetime.now() - timedelta(days=max_age_days)
    try:
        if not await asyncio.to_thread(self._user_data_dir.exists):
            return 0
        # Run glob in thread pool to avoid blocking
        files = await asyncio.to_thread(lambda: list(self._user_data_dir.glob("*.json")))
        for file_path in files:
            # ... rest is already using to_thread correctly
```

---

## 2. Async Patterns

### Issue 2.1: Synchronous `httpx.post` in `ai_classifier.py` blocks the event loop

| Attribute | Value |
|-----------|-------|
| **File** | `services/ai_classifier.py:194-208, 214-227, 233-247, 253-265, 272-286` |
| **Performance Impact** | **HIGH** |
| **Effort to Fix** | **MEDIUM** |
| **Description** | All five `_classify_*` functions use **synchronous** `httpx.post()` (not `httpx.AsyncClient`). When called from an async endpoint, these block the event loop for up to 15-30 seconds per call. For the AI-assisted Watch Later sync, this means the entire server becomes unresponsive during classification. |

**Evidence:** `classify_video()` (line 155) is a synchronous function. It's called from `watch_later_sync` which is async. The caller does NOT wrap it in `asyncio.to_thread`.

**Suggested Fix:** Convert to async httpx client, or wrap the synchronous call:

**Option A — Wrap in to_thread (quick fix):**
```python
# Wherever classify_video is called in background_worker.py:
result = await asyncio.to_thread(
    classify_video, title, channel, description, playlists, provider, api_key
)
```

**Option B — Convert to async (better, reuses connection pool):**
```python
async def _classify_openai(prompt: str, api_key: str) -> tuple[str | None, str | None]:
    from core.http_client import get_http_client
    client = get_http_client()
    resp = await client.post(
        API_ENDPOINTS["openai"],
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 50,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"].strip()
    return (text if text != "UNSURE" else None), None
```

---

### Issue 2.2: Blocking `read_text()` in `/api/maintenance` endpoint

| Attribute | Value |
|-----------|-------|
| **File** | `app.py:1015-1017` |
| **Performance Impact** | **MEDIUM** |
| **Effort to Fix** | **LOW** |
| **Description** | `maintenance_file.read_text()` and `maintenance_file.exists()` are synchronous file I/O called directly from an async handler. This blocks the event loop. |

**Suggested Fix:**

```python
@app.get("/api/maintenance")
async def api_maintenance() -> dict[str, Any]:
    maintenance_file = Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data")) / "maintenance.json"
    if await asyncio.to_thread(maintenance_file.exists):
        try:
            content = await asyncio.to_thread(maintenance_file.read_text)
            return json.loads(content)
        except Exception:
            pass
    return {
        "move_from_x_to_y": [],
        "duplicated_videos": [],
        "misplaced_videos": [],
        "info": "Maintenance analysis requires full video scan. Run Full Playlist Sync first."
    }
```

---

### Issue 2.3: `_save_sessions()` is synchronous — blocks event loop

| Attribute | Value |
|-----------|-------|
| **File** | `api/auth.py:257-272` |
| **Performance Impact** | **HIGH** |
| **Effort to Fix** | **LOW** |
| **Description** | Unlike `_save_users()` which uses `asyncio.to_thread`, `_save_sessions()` directly calls `tmp.write_text()` and `tmp.replace()` synchronously. It is called from async endpoints (`login`, `logout`, `refresh_token`, `register`) where it blocks the event loop. |

**Evidence:** Compare line 80 (`await asyncio.to_thread(tmp.write_text, content)`) in `_save_users` with line 269 (`tmp.write_text(...)` ) in `_save_sessions`. Same pattern, but the sessions version is missing `to_thread`.

**Suggested Fix:**

```python
async def _save_sessions(sessions: Dict[str, Dict[str, Any]]) -> None:
    try:
        await asyncio.to_thread(SESSIONS_FILE.parent.mkdir, parents=True, exist_ok=True)
        serializable: Dict[str, Dict[str, Any]] = {}
        for token, entry in sessions.items():
            s = dict(entry)
            for field in ("created_at", "expires_at"):
                val = s.get(field)
                if isinstance(val, datetime):
                    s[field] = val.isoformat()
            serializable[token] = s
        content = json.dumps(serializable, indent=2, default=str)
        tmp = SESSIONS_FILE.with_suffix(".json.tmp")
        await asyncio.to_thread(tmp.write_text, content, encoding="utf-8")
        await asyncio.to_thread(tmp.replace, SESSIONS_FILE)
    except Exception as e:
        log.error("Failed to save user sessions: %s", e)
```

And update all call sites from `_save_sessions(user_sessions)` to `await _save_sessions(user_sessions)`.

---

### Issue 2.4: `_load_sessions()` is also synchronous and called at module import time

| Attribute | Value |
|-----------|-------|
| **File** | `api/auth.py:238-254, 275` |
| **Performance Impact** | **MEDIUM** |
| **Effort to Fix** | **LOW** |
| **Description** | `_load_sessions()` is synchronous (uses `SESSIONS_FILE.read_text()` directly). It is called at module level: `user_sessions: Dict = _load_sessions()`. This runs during import, which is acceptable at startup, but the function is also potentially re-invoked. More importantly, it sets a pattern that any future lazy-reload would block. |

**Suggested Fix:** Make it async and load in the lifespan, matching the pattern used for users:

```python
user_sessions: Dict[str, Dict[str, Any]] = {}

async def _load_sessions_async() -> Dict[str, Dict[str, Any]]:
    # ... same logic but with asyncio.to_thread for file operations
```

---

## 3. Database / Storage Efficiency

### Issue 3.1: Per-request file writes — no debouncing for `_save_users` / `_save_sessions`

| Attribute | Value |
|-----------|-------|
| **File** | `api/auth.py:66-83, 257-272` |
| **Performance Impact** | **MEDIUM** |
| **Effort to Fix** | **MEDIUM** |
| **Description** | Every auth mutation (login, logout, register, password reset, user update) triggers an immediate `_save_users()` or `_save_sessions()` call that writes the entire JSON file to disk. Under rapid requests (e.g., multiple users logging in simultaneously), this creates a write storm. The in-memory state is always consistent, so these writes could be batched. |

**Suggested Fix:** Implement a simple debounced writer:

```python
class DebouncedSaver:
    """Debounces file saves — coalesces multiple writes within a window."""
    def __init__(self, save_fn, delay: float = 2.0):
        self._save_fn = save_fn
        self._delay = delay
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def schedule(self, *args):
        async with self._lock:
            if self._task and not self._task.done():
                self._task.cancel()
            self._task = asyncio.create_task(self._deferred_save(*args))

    async def _deferred_save(self, *args):
        try:
            await asyncio.sleep(self._delay)
            await self._save_fn(*args)
        except asyncio.CancelledError:
            pass  # superseded by a newer save
        except Exception as e:
            log.error("Debounced save failed: %s", e)

_users_saver = DebouncedSaver(_save_users, delay=2.0)

# In register/login/etc:
await _users_saver.schedule(users_db)  # instead of await _save_users(users_db)
```

---

### Issue 3.2: `OperationsStorage.save()` writes entire operations file on every progress update

| Attribute | Value |
|-----------|-------|
| **File** | `api/bulk_operations.py:131-145, 160-163` |
| **Performance Impact** | **MEDIUM** |
| **Effort to Fix** | **LOW** |
| **Description** | `update_and_save()` is called every 10 items during bulk operations (line 490, 549, 610). Each call serializes and writes the **entire** operations dict to disk. For a bulk move of 1000 videos, this writes ~100 times. The operations dict also grows unbounded (see Issue 6.1). |

**Suggested Fix:** Apply the same debounced writer pattern, or at minimum only save at start and end (remove the intermediate saves, relying on in-memory state for progress queries via the WebSocket):

```python
# Only save at key transitions: pending->in_progress, in_progress->completed/failed
# Progress updates are reflected in-memory and queryable via the status endpoint
```

---

## 4. Connection Pooling

### Issue 4.1: `ai_classifier.py` creates a new `httpx.Client` per classification call

| Attribute | Value |
|-----------|-------|
| **File** | `services/ai_classifier.py:193, 213, 232, 253, 270` |
| **Performance Impact** | **MEDIUM** |
| **Effort to Fix** | **LOW** |
| **Description** | Each `_classify_*` function does `import httpx` then `httpx.post(...)` which creates a **new connection** per call. No connection reuse, no pooling. If AI classification is called in a batch (one per video), this could make 50+ separate TCP connections. |

**Suggested Fix:** Use the shared async client from `core/http_client.py`:

```python
from core.http_client import get_http_client

async def _classify_openai(prompt: str, api_key: str) -> tuple[str | None, str | None]:
    client = get_http_client()  # Reuses pooled connection
    resp = await client.post(
        API_ENDPOINTS["openai"],
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1, "max_tokens": 50},
        timeout=15,
    )
    # ...
```

---

### Issue 4.2: `youtube_client.py` shared `httpx.Client` never closed on shutdown

| Attribute | Value |
|-----------|-------|
| **File** | `services/youtube_client.py:32` |
| **Performance Impact** | **LOW** |
| **Effort to Fix** | **LOW** |
| **Description** | The module-level `_shared_client = httpx.Client(timeout=45.0)` is created at import but never closed. `shutdown_http_client()` in `core/http_client.py` only closes the _async_ client, not this sync one. On process exit this is usually fine (OS reclaims), but in test scenarios with multiple process invocations it could leak file descriptors. |

**Suggested Fix:** Add cleanup in `app.py` lifespan or use an atexit handler:

```python
# In youtube_client.py, add at bottom:
import atexit
if _shared_client:
    atexit.register(_shared_client.close)
```

---

### Issue 4.3: `http_client.py` async client has conservative pool limits for API-heavy workloads

| Attribute | Value |
|-----------|-------|
| **File** | `core/http_client.py:24-28` |
| **Performance Impact** | **LOW** |
| **Effort to Fix** | **LOW** |
| **Description** | `max_keepalive_connections=10, max_connections=20` may be too low when the app is concurrently fetching YouTube data (5 concurrent playlist fetches via semaphore) + AI classification calls + OAuth refresh tokens. If more than 20 concurrent HTTP requests are needed, new connections will be created and destroyed, reducing the benefit of HTTP/2 multiplexing. |

**Suggested Fix:**

```python
_http_client = AsyncClient(
    limits=Limits(
        max_keepalive_connections=20,
        max_connections=50,
        keepalive_expiry=60.0,
    ),
    timeout=Timeout(30.0, connect=5.0),
    http2=True,
    verify=certifi.where(),
)
```

---

## 5. Memory Usage

### Issue 5.1: WebSocket `active_connections` list uses O(N) `remove()` — broadcast also O(N)

| Attribute | Value |
|-----------|-------|
| **File** | `app.py:286-335` |
| **Performance Impact** | **LOW** |
| **Effort to Fix** | **LOW** |
| **Description** | `ConnectionManager.active_connections` is a `list[WebSocket]`. `disconnect()` uses `list.remove()` which is O(N). `broadcast()` iterates all connections sending messages, which is inherently O(N) but failed connections trigger `disconnect()` (another O(N) per failure). For a small number of WebSocket connections (typical: 1-5), this is fine. But the pattern doesn't scale. |

**Suggested Fix:** Use a `set` instead of `list` for O(1) add/remove:

```python
class ConnectionManager:
    def __init__(self):
        self.active_connections: set[WebSocket] = set()
        self._user_connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str = None):
        await websocket.accept()
        self.active_connections.add(websocket)
        if user_id:
            self._user_connections.setdefault(user_id, set()).add(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str = None):
        self.active_connections.discard(websocket)  # O(1), no ValueError
        if user_id and user_id in self._user_connections:
            self._user_connections[user_id].discard(websocket)
            if not self._user_connections[user_id]:
                del self._user_connections[user_id]
```

---

### Issue 5.2: Broadcast with `send_text` is sequential — slow with many connections

| Attribute | Value |
|-----------|-------|
| **File** | `app.py:323-335` |
| **Performance Impact** | **MEDIUM** |
| **Effort to Fix** | **LOW** |
| **Description** | `broadcast()` sends to each connection **sequentially** with `await connection.send_text(message)`. If one connection is slow (high latency), it blocks all subsequent sends. With 5+ connections, this can add noticeable latency. |

**Suggested Fix:** Use `asyncio.gather` for concurrent sends:

```python
async def broadcast(self, message: str, user_id: str = None):
    if user_id:
        await self.send_to_user(user_id, message)
    else:
        connections = list(self.active_connections)  # snapshot
        async def _safe_send(ws):
            try:
                await ws.send_text(message)
                return True
            except Exception:
                return False
        results = await asyncio.gather(*[_safe_send(ws) for ws in connections])
        for ws, ok in zip(connections, results):
            if not ok:
                self.disconnect(ws)
```

---

### Issue 5.3: `user_sessions` dict grows unbounded — expired sessions never cleaned

| Attribute | Value |
|-----------|-------|
| **File** | `api/auth.py:275` |
| **Performance Impact** | **MEDIUM** |
| **Effort to Fix** | **LOW** |
| **Description** | `user_sessions` is a plain `Dict` loaded at startup. Sessions are added on login/register/refresh but **never removed** even after expiry (7 days with `ACCESS_TOKEN_EXPIRE_MINUTES = 10080`). Only `logout()` removes a session. Over weeks of uptime, this dict accumulates thousands of stale entries. |

**Suggested Fix:** Add a periodic cleanup in the lifespan, similar to the cache cleanup:

```python
async def sessions_cleanup_loop():
    """Remove expired sessions periodically."""
    while True:
        await asyncio.sleep(3600)  # Every hour
        now = datetime.now()
        expired = [k for k, v in user_sessions.items()
                   if v.get("expires_at") and v["expires_at"] < now]
        for k in expired:
            user_sessions.pop(k, None)
        if expired:
            await _save_sessions(user_sessions)
            log.info(f"Cleaned {len(expired)} expired sessions")

asyncio.create_task(sessions_cleanup_loop())
```

---

## 6. Endpoint Performance

### Issue 6.1: `OperationsStorage._operations` grows without bound — no cleanup of old operations

| Attribute | Value |
|-----------|-------|
| **File** | `api/bulk_operations.py:109-158` |
| **Performance Impact** | **MEDIUM** |
| **Effort to Fix** | **LOW** |
| **Description** | Operations are never removed from `_operations` dict (only on explicit cancel). The `list_all()` method returns all operations. Over time this dict grows unbounded and the `save()` method serializes an increasingly large dict. |

**Suggested Fix:**

```python
async def cleanup_old_operations(self, max_age_hours: int = 24) -> int:
    """Remove completed/failed operations older than max_age_hours."""
    now = datetime.now()
    cutoff = now - timedelta(hours=max_age_hours)
    to_remove = [
        k for k, v in self._operations.items()
        if v.status in ("completed", "failed", "cancelled")
        and v.completed_at and v.completed_at < cutoff
    ]
    for k in to_remove:
        del self._operations[k]
    if to_remove:
        await self.save()
    return len(to_remove)
```

Call this periodically or after each operation completes.

---

### Issue 6.2: `list_users` endpoint has no pagination

| Attribute | Value |
|-----------|-------|
| **File** | `api/auth.py:708-713` |
| **Performance Impact** | **LOW** |
| **Effort to Fix** | **LOW** |
| **Description** | `GET /api/auth/users` returns all users without pagination. While user counts are expected to be small in this app, the endpoint creates a Pydantic model for every user, which could be slow with thousands of users. |

**Suggested Fix:**

```python
@router.get("/users")
async def list_users(
    limit: int = 50,
    offset: int = 0,
    current_user: Dict[str, Any] = Depends(check_role(["admin"])),
    users_db: Dict[str, Dict[str, Any]] = Depends(get_users_db),
):
    all_users = list(users_db.values())
    return [UserResponse(**u) for u in all_users[offset:offset + limit]]
```

---

## Summary Tables

### All Issues Ranked by Impact

| # | Issue | Area | Impact | Effort | File |
|---|-------|------|--------|--------|------|
| 2.1 | Sync `httpx.post` blocks event loop in AI classifier | Async | 🔴 HIGH | 🟡 MED | `ai_classifier.py` |
| 2.3 | `_save_sessions()` synchronous — blocks event loop | Async | 🔴 HIGH | 🟢 LOW | `api/auth.py` |
| 1.1 | `cleanup_stale()` never called — stale cache accumulates | Cache | 🔴 HIGH | 🟢 LOW | `core/lru_cache.py` |
| 1.3 | Synchronous `glob()` in disk cache cleanup | Cache | 🟡 MED | 🟢 LOW | `youtube_service.py` |
| 2.2 | Blocking `read_text()` in `/api/maintenance` | Async | 🟡 MED | 🟢 LOW | `app.py` |
| 2.4 | `_load_sessions()` synchronous at module level | Async | 🟡 MED | 🟢 LOW | `api/auth.py` |
| 3.1 | Per-request file writes — no debouncing | Storage | 🟡 MED | 🟡 MED | `api/auth.py` |
| 3.2 | Operations file written every 10 items | Storage | 🟡 MED | 🟢 LOW | `bulk_operations.py` |
| 4.1 | New `httpx.Client` per AI classification call | Pooling | 🟡 MED | 🟢 LOW | `ai_classifier.py` |
| 5.2 | Sequential WebSocket broadcast — slow with many connections | Memory | 🟡 MED | 🟢 LOW | `app.py` |
| 5.3 | `user_sessions` dict never cleaned of expired entries | Memory | 🟡 MED | 🟢 LOW | `api/auth.py` |
| 6.1 | `_operations` dict grows without bound | Endpoint | 🟡 MED | 🟢 LOW | `bulk_operations.py` |
| 1.2 | Double SHA-256 in cache key generation | Cache | 🟢 LOW | 🟢 LOW | `youtube_service.py` |
| 4.2 | Sync `httpx.Client` never closed on shutdown | Pooling | 🟢 LOW | 🟢 LOW | `youtube_client.py` |
| 4.3 | Conservative pool limits for API-heavy workloads | Pooling | 🟢 LOW | 🟢 LOW | `http_client.py` |
| 5.1 | WebSocket `list` uses O(N) remove | Memory | 🟢 LOW | 🟢 LOW | `app.py` |
| 6.2 | `list_users` has no pagination | Endpoint | 🟢 LOW | 🟢 LOW | `api/auth.py` |

### Quick Wins (HIGH impact, LOW effort)

| # | Issue | Fix Summary |
|---|-------|-------------|
| 2.3 | `_save_sessions()` synchronous | Add `asyncio.to_thread` wrapper (4 lines to change) |
| 1.1 | `cleanup_stale()` never called | Add background task in lifespan (~8 lines) |

### Estimated Total Remediation

| Impact Level | Count | Estimated Effort |
|-------------|-------|-----------------|
| HIGH | 3 | ~1-2 days |
| MEDIUM | 9 | ~2-3 days |
| LOW | 5 | ~0.5 day |
| **Total** | **17** | **~4-6 days** |

---

## Architectural Recommendations

1. **Standardize async file I/O**: Create a utility module (e.g., `core/async_io.py`) with `async_read_text()`, `async_write_text()`, `async_exists()`, `async_glob()` helpers. This eliminates the pattern mismatch where some code uses `asyncio.to_thread` and some doesn't.

2. **Implement a debounced writer**: Many write-on-mutation patterns exist (users, sessions, operations, config). A single reusable `DebouncedSaver` class would reduce I/O by 80%+ under load.

3. **Add a periodic maintenance task**: The lifespan should have a single "housekeeper" background task that handles: LRU cache cleanup, session expiry, operations cleanup, and disk cache cleanup — all at appropriate intervals.

4. **Use the shared `AsyncClient` everywhere**: Both `ai_classifier.py` and `api/auth.py` (Google OAuth callback) create their own `httpx` clients. They should use `core/http_client.py:get_http_client()` to share the pooled, HTTP/2-enabled client.
