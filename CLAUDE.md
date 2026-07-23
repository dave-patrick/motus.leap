---
tags: [motus.leap, project, claude-code]
---

# motus.leap — Project Context for Claude Code

## What is this?
motus.leap is an Automated YouTube Playlist Maintainer — a FastAPI web app for organizing playlists, watching patterns, and repeated YouTube viewing sessions.

## Repo location
`/opt/data/motus.leap/tube-manager/`

## Key commands
- `cd /opt/data/motus.leap/tube-manager`
- `source .venv/bin/activate`
- `python3 -m pytest tests/ -q` — run full test suite
- `uvicorn app:app --host 0.0.0.0 --port 8000 --reload` — dev server

## Architecture
- `app.py` — main FastAPI entry (1778 lines)
- `api/` — REST endpoints (auth, bulk_operations, config, mappings, youtube, websocket)
- `services/` — YouTube client wrapper, AI classifier, background worker
- `core/` — HTTP client, LRU cache, config manager, security/rate limiting
- `models/` — data types
- `web/` — frontend HTML/JS

## Test results (baseline)
- **106 passed, 0 failed** (after fixing test infra: data dir env var, psutil dep)
- Coverage: unit, integration, security, load tests

## Recently fixed (2026-06-27)
- YouTubeService data dir now uses TUBE_MANAGER_DATA_DIR env var (was hardcoded /app/data)
- get_client() return None bug — unreachable code after unconditional return
- conftest.py sets temp TUBE_MANAGER_DATA_DIR for test isolation
- All 11 CRITICAL/HIGH code review fixes verified as applied

## What needs doing
1. Improve cache cleanup robustness (LRU eviction + stale disk cache cleanup) 
2. Keep YouTube cleanup workflow stable (error handling, retry logic)
3. Add verifiable test coverage for bug fixes
4. Remove obsolete surfaces from retirement plan (regenerate_queue, surface_diagnostics, apply_maintenance stubs)

## Code review findings — already applied
All CRITICAL + HIGH issues fixed on 2026-06-21. MEDIUM items (CSP, Dockerfile non-root, timeouts, error leaking, dotenv safety) verified as already in codebase.

## Deploy
- Live: https://tubemanager.onrender.com
- GitHub: https://github.com/dave-patrick/motus.leap
