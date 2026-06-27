# motus.leap — Performance, Backend & Security Review

**Date:** 2026-06-27
**Agents:** neo (Performance), gwen (Backend), jnu (Security)
**Accuracy Review:** sheldon (pending)

---

## Executive Summary

A comprehensive review of the motus.leap backend was conducted across 3 parallel agents covering performance/efficiency, backend functionality, and security.

**Overall Assessment:** The application works for the happy path but has significant technical debt. **50 total issues** found: 7 Critical, 16 High, 16 Medium, 11 Low.

---

## Agent Results Summary

| Agent | Issues | Focus |
|-------|--------|-------|
| 🔧 neo | 17 (3H/9M/5L) | Performance & Efficiency |
| 🔍 gwen | 12 (3H/5M/4L) | Backend Functionality |
| 🔒 jnu | 21 (4H/6M/5L) | Security |
| **Total unique** | **50** | |

---

## Critical Issues (7)

| # | Source | File | Description | Impact |
|---|--------|------|-------------|--------|
| C1 | gwen | services/ai_classifier.py | Missing `import asyncio` — AI classify endpoint crashes at runtime | AI features broken |
| C2 | gwen | services/background_worker.py | `_get_cached`/`_set_cached` missing from YouTubeService — Watch Later channel cache silently fails | Data matching degraded |
| C3 | jnu | app.py | 10+ sensitive API endpoints have no authentication (settings, diagnostics, AI memory, maintenance) | Data exposure |
| C4 | jnu | app.py | WebSocket endpoint `/ws/terminal` has no authentication | Unauthorized access |
| C5 | jnu | app.py | No HSTS header — vulnerable to downgrade attacks | Transport security |
| C6 | jnu | api/youtube.py | No video ID validation — accepts any string | Injection risk |
| C7 | neo | api/auth.py | `_save_sessions()` is synchronous — blocks event loop on every login/logout | Performance blocker |

## High Issues (16)

| # | Source | File | Description |
|---|--------|------|-------------|
| H1 | jnu | api/auth.py | Weak default admin password ("admin") |
| H2 | jnu | config.json | Plaintext secrets stored on disk (client_secret, API keys) |
| H3 | jnu | api/auth.py | Token refresh doesn't invalidate old tokens — replay attacks possible |
| H4 | jnu | api/auth.py | No token revocation on password change |
| H5 | jnu | app.py | SSRF in webhook endpoint — can hit internal URLs |
| H6 | jnu | app.py | No bulk payload size limits — DoS risk |
| H7 | jnu | core/security.py | CSRF `verify_origin` bypassable by stripping Origin header |
| H8 | jnu | api/youtube.py | SSRF in AI custom endpoint URL |
| H9 | jnu | app.py | XSS in OAuth error page (user content rendered unsanitized) |
| H10 | jnu | api/auth.py | Cookie Secure flag misconfiguration (checks VERCEL_ENV not RENDER) |
| H11 | neo | core/lru_cache.py | `cleanup_stale()` never invoked — stale entries accumulate forever |
| H12 | neo | services/ai_classifier.py | Synchronous `httpx.post` blocks event loop |
| H13 | neo | api/auth.py | Per-request file writes with no debouncing |
| H14 | gwen | app.py | `/api/watch-later` POST has no auth dependency |
| H15 | gwen | app.py | WebSocket terminal has no auth |
| H16 | gwen | services/background_worker.py | `cancel_current_task` race condition — scan can run minutes after cancel |

## Medium Issues (16)

| # | Source | File | Description |
|---|--------|------|-------------|
| M1 | jnu | app.py | No idle session timeout |
| M2 | jnu | core/limiter.py | No rate limits on read endpoints |
| M3 | jnu | app.py | Server header discloses framework info |
| M4 | jnu | api/auth.py | No CSRF token protection |
| M5 | jnu | app.py | CORS rate-limit integration issues |
| M6 | neo | services/youtube_service.py | Sync `glob()` in disk cache cleanup blocks event loop |
| M7 | neo | app.py | Blocking `read_text()` in maintenance endpoint |
| M8 | neo | services/ai_classifier.py | New `httpx.Client` created per AI call — no connection reuse |
| M9 | neo | services/background_worker.py | Operations file written every 10 items — excessive I/O |
| M10 | neo | app.py | Sequential WebSocket broadcast to all users |
| M11 | neo | api/auth.py | Unbounded `sessions` dict growth |
| M12 | neo | api/bulk_operations.py | Unbounded operations dict growth |
| M13 | gwen | app.py | No max size limit on bulk request payloads |
| M14 | gwen | app.py | Frontend never polls bulk operation progress |
| M15 | gwen | services/background_worker.py | `scan_duplicates` uses `getattr(self.youtube_service, "videos", [])` — attribute doesn't exist |
| M16 | gwen | app.py | Inconsistent error response formats across endpoints |

## Low Issues (11)

| # | Source | Description |
|---|--------|-------------|
| L1 | neo | Double SHA-256 hashing in cache keys — unnecessary |
| L2 | neo | Unclosed sync httpx.Client in youtube_client |
| L3 | neo | Conservative HTTP pool limits |
| L4 | neo | O(N) list.remove in WebSocket disconnect cleanup |
| L5 | neo | No pagination on list_users admin endpoint |
| L6 | gwen | `/api/system/logs` is a stub returning empty array |
| L7 | gwen | `ai_classify_videos` creates new YouTubeService per request |
| L8 | jnu | XSS test payload in config.json |
| L9 | jnu | Debug logging near token operations |
| L10 | jnu | No CSRF token mechanism |
| L11 | jnu | Missing `type="button"` on some non-submit buttons |

---

## Cross-Cutting Priorities

### 🔴 Immediate (ship blocker)
1. **Add `import asyncio` to ai_classifier.py** — entire AI feature is broken
2. **Add auth to sensitive endpoints** — data exposure risk
3. **Add auth to WebSocket** — unauthorized access
4. **Fix `_save_sessions()` sync blocking** — performance blocker

### 🟠 High (this sprint)
5. **Add `_get_cached`/`_set_cached` to YouTubeService** — Watch Later matching broken
6. **Add HSTS header** — transport security
7. **Add video ID validation** — injection prevention
8. **Add bulk payload limits** — DoS prevention
9. **Fix token refresh to invalidate old tokens** — session security
10. **Fix `cleanup_stale()` invocation** — memory leak

### 🟡 Medium (next sprint)
11. Add idle session timeout
12. Fix SSRF in webhook/AI endpoints
13. Add CSRF token protection
14. Fix cookie Secure flag for Render
15. Unify error response formats
16. Add rate limits to read endpoints

---

**Total: 50 issues | 7 Critical | 16 High | 16 Medium | 11 Low**
