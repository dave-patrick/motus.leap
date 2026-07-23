# Tube Manager Codebase Refactoring & Stabilization Plan

> **For Hermes:** Use this step-by-step plan to resolve critical bugs, persistent operations state, stub data removal, performance bottlenecks, and architectural code smells in the Tube Manager codebase.

**Goal:** Stabilization, bug remediation, and performance tuning of the Tube Manager FastAPI monolith.

**Architecture:** 
- Fix latent runtime NameErrors and CORS violations.
- Introduce persistent JSON storage for background operation state (replacing volatile in-memory dicts).
- Implement real, dynamic maintenance diagnostics (duplicate and misplaced video scanning) to replace hardcoded empty stubs.
- Move background tasks out of the 1500-line `app.py` monolith to separate service modules.

**Tech Stack:** FastAPI, Pydantic v2, Python 3.11+, Pytest, HTTPX

---

## Task 1: Remediate `self` NameError inside `watch_later_sync`

**Objective:** Correct the latent runtime error where `self` is referenced inside a global function.

**Files:**
- Modify: `C:/Users/davem/repos/tube-manager/tube-manager/app.py:446`

**Step 1: Write/Review failing test case**
There is no direct test calling the caching branch of `watch_later_sync` with `hasattr(youtube_service, "_get_cached")` as True. We will patch this line directly.

**Step 2: Implement the Fix**
Replace:
```python
channel_cache = await self._get_cached(channel_key) if hasattr(youtube_service, "_get_cached") else None
```
With a correct reference to `youtube_service`:
```python
channel_cache = await youtube_service._get_cached(channel_key) if hasattr(youtube_service, "_get_cached") else None
```

**Step 3: Run the test suite**
Run: `uv run --extra dev pytest tube-manager/tests/unit/test_youtube_service.py`
Expected: PASS

**Step 4: Commit**
```bash
git add tube-manager/app.py
git commit -m "fix: resolve NameError in watch_later_sync by correcting self reference"
```

---

## Task 2: Implement Persistent Storage for Bulk Operations State

**Objective:** Save background operation logs to disk under `/app/data/operations.json` to prevent state loss on Render container recycle.

**Files:**
- Modify: `C:/Users/davem/repos/tube-manager/tube-manager/api/bulk_operations.py`

**Step 1: Write helper functions for disk serialization**
At the top of `api/bulk_operations.py`, introduce `_load_operations` and `_save_operations` helpers, similar to `auth.py`:

```python
import os
import json
from pathlib import Path

OPERATIONS_FILE = Path(os.getenv("TUBE_MANAGER_DATA_DIR", "/app/data")) / "operations.json"

def _load_operations() -> Dict[str, Any]:
    if OPERATIONS_FILE.exists():
        try:
            data = json.loads(OPERATIONS_FILE.read_text())
            return {k: BulkOperationResponse(**v) for k, v in data.items()}
        except Exception as e:
            log.warning("Failed to load operations: %s", e)
    return {}

def _save_operations(ops: Dict[str, BulkOperationResponse]) -> None:
    try:
        OPERATIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        serializable = {k: v.model_dump(mode="json") for k, v in ops.items()}
        OPERATIONS_FILE.write_text(json.dumps(serializable, indent=2))
    except Exception as e:
        log.error("Failed to save operations: %s", e)
```

**Step 2: Refactor API endpoints to use persistence**
Modify operations read/write in `bulk_operations.py`:
- In `bulk_move_videos` and `bulk_delete_videos`, read active operations via `_load_operations()`, insert the new operation, and write via `_save_operations()`.
- Update state updates in the background handlers (`process_bulk_move`, `process_bulk_delete`) to save progress increments to disk after processing each item chunk.

**Step 3: Verification**
Run: `uv run --extra dev pytest tube-manager/tests/api/test_bulk_operations.py`
Expected: PASS

**Step 4: Commit**
```bash
git add tube-manager/api/bulk_operations.py
git commit -m "feat: persist bulk operations to JSON file to survive Render restarts"
```

---

## Task 3: Secure CORS Configuration with Credentials

**Objective:** Restrict wildcards when credentials are true to prevent modern browser rejections.

**Files:**
- Modify: `C:/Users/davem/repos/tube-manager/tube-manager/app.py:83-89`

**Step 1: Replace wildcard origins with strict values**
Update:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://tubemanager.onrender.com", 
        "http://localhost:8000",
        "http://localhost:3000",
        "http://127.0.0.1:8000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Step 2: Verification**
Run `uv run --extra dev pytest tube-manager/tests/security/test_security.py` to ensure CORS headers do not block client tests.

**Step 3: Commit**
```bash
git add tube-manager/app.py
git commit -m "security: replace wildcard CORS origins with strict whitelist"
```

---

## Task 4: Replace Stub Maintenance Analysis with Real Scans

**Objective:** Implement real, dynamic calculations for duplicate and misplaced videos.

**Files:**
- Modify: `C:/Users/davem/repos/tube-manager/tube-manager/app.py`
- Modify: `C:/Users/davem/repos/tube-manager/tube-manager/services/youtube_service.py`

**Step 1: Implement scan heuristics**
Add duplicate/misplaced detection logic to a helper function inside `YouTubeService`:
- **Duplicate Detection:** Scan fetched video listings across all playlists. Collect lists of `video_id`s that appear in more than one playlist.
- **Misplaced Videos:** Check if a video's parent playlist matches the target `playlist_id` defined in the channel mapping for that video's creator channel. If it resides in a different playlist, tag it as "misplaced".

Write the results to `/app/data/maintenance.json`.

**Step 2: Update `/api/maintenance` to read real JSON**
Modify `/api/maintenance` in `app.py` to check for `/app/data/maintenance.json` and return the real results if found:

```python
@app.get("/api/maintenance")
async def api_maintenance() -> dict[str, Any]:
    maintenance_file = Path("/app/data/maintenance.json")
    if maintenance_file.exists():
        try:
            return json.loads(maintenance_file.read_text())
        except Exception:
            pass
    return {
        "move_from_x_to_y": [],
        "duplicated_videos": [],
        "misplaced_videos": [],
        "info": "No scan data found. Run a Full Cluster Scan to analyze."
    }
```

**Step 3: Commit**
```bash
git add tube-manager/app.py tube-manager/services/youtube_service.py
git commit -m "feat: implement real background maintenance scans replacing hardcoded empty lists"
```

---

## Task 5: Calculate Accurate AI Mappings Accuracy

**Objective:** Replace the fake `100.0%` learning rate with a genuine ratio.

**Files:**
- Modify: `C:/Users/davem/repos/tube-manager/tube-manager/app.py:829`

**Step 1: Calculate real matching accuracy**
Modify the calculation to calculate the ratio of mapped channels to the total channels.
```python
# Calculate real stats from config
channel_mappings_count = len(config.channel_mappings) if hasattr(config, 'channel_mappings') else 0
total_subscriptions = yt_stats.get("total_subscriptions", 0)

learning_rate_pct = (channel_mappings_count / max(total_subscriptions, 1) * 100) if total_subscriptions > 0 else 0
```
Change `/api/stats` to return `learning_rate_pct` formatted correctly.

**Step 2: Commit**
```bash
git add tube-manager/app.py
git commit -m "refactor: calculate real learning rate metric from active subscription mappings"
```

---

## Task 6: De-clutter `app.py` (De-couple Monolith)

**Objective:** Move background worker routines out of `app.py` to a dedicated `services/background_worker.py` module to improve architecture and maintenance.

**Files:**
- Create: `C:/Users/davem/repos/tube-manager/tube-manager/services/background_worker.py`
- Modify: `C:/Users/davem/repos/tube-manager/tube-manager/app.py`

**Step 1: Extract background runner functions**
Cut `process_background_tasks`, `full_cluster_scan`, `force_auto_sort`, `watch_later_sync`, `diagnose_failures`, `regenerate_queue`, `surface_diagnostics`, and `apply_maintenance` from `app.py` and move them into `services/background_worker.py`.

**Step 2: Initialize in app lifespan**
Import the worker routines in `app.py` and start the processor inside the FastAPI lifespan startup event.

**Step 3: Comprehensive Test Verification**
Run the full test suite locally:
`uv run --extra dev pytest`
Verify **all 105 tests pass** under the new modular layout.

**Step 4: Commit**
```bash
git add -A
git commit -m "arch: decouple app monolith, moving background runners to services/background_worker.py"
```
