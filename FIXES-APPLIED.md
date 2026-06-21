# Motus.leap — Automated Fixes Applied

**Date:** 2026-06-21  
**Applied by:** Automated sweep (hotfix run)  
**Severity:** CRITICAL + HIGH

---

## Changes Made

| # | Issue | File | Change |
|---|-------|------|--------|
| 1 | `log` used before definition | `tube-manager/app.py` | Moved `import logging`, `from core.logger import setup_logging`, `log = logging.getLogger(__name__)` immediately after `load_dotenv()` |
| 2 | Missing dependency | `tube-manager/reqs.txt` | Added `python-dotenv>=1.0.0` |
| 3 | Exposed OAuth Client ID | `tube-manager/app.py` | Removed hardcoded Google OAuth Client ID from HTML error page; replaced with generic prompt to check Settings |
| 4 | Undefined `configured_id` | `tube-manager/services/background_worker.py` | Replaced with `self.channel_id` fallback chain |
| 5 | Missing `videos` attribute | `tube-manager/services/background_worker.py` | Guarded with `getattr(self.youtube_service, "videos", [])` |
| 6 | Duplicate `api_user()` | `tube-manager/app.py` | Removed second definition, kept the first |
| 7 | Missing `JSONResponse` | `tube-manager/app.py` | Added `from fastapi.responses import JSONResponse` |
| 8 | `_get_client()` return not checked | `tube-manager/app.py` | Added `if google_client is None: raise HTTPException(500)` in rename/delete/duplicate endpoints |
| 9 | Removed FastAPI lifespan API | `tube-manager/app.py` | Replaced `app.router.lifespan_context = lifespan` with `app = FastAPI(lifespan=lifespan)` |
| 10 | Broken DI in bulk ops | `tube-manager/api/bulk_operations.py` | Replaced `ops_storage = Depends(get_operations_storage)` with `ops_storage = None` in all `process_bulk_*` background task signatures |
| 11 | Bad test import | `tube-manager/tests/conftest.py` | Removed non-exported `youtube_service` from `from app` import |

---

## Verification

Run:

```bash
python3 -c "from dotenv import load_dotenv; print('dotenv OK')"
python3 -c "from fastapi.responses import JSONResponse; print('JSONResponse OK')"
python3 -m pytest tube-manager/tests/
```
