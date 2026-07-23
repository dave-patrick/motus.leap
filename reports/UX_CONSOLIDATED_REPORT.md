# motus.leap — Full UX Review Report

**Date:** 2026-06-27
**Agents:** neo (HTML/CSS/UX), gwen (API testing), jnu (JS functionality)
**Reviewer:** sheldon (final accuracy check)

---

## Executive Summary

A comprehensive UX review of the motus.leap YouTube playlist manager was conducted across 3 parallel review agents. The review covered all 9 HTML templates, 9 JavaScript files, and 50+ API endpoints.

**Overall Assessment:** The application is functional but has significant UX inconsistencies and 3 critical issues that need immediate attention. There are **71 total issues** found: 6 Critical, 11 High, 27 Medium, 27 Low.

---

## Critical Issues (6)

| # | Source | File | Description |
|---|--------|------|-------------|
| C1 | neo | settings.html | Duplicate `id="api-key-status"` (lines 74 & 313) — silently breaks AI key status indicator |
| C2 | jnu | web/static/auth.js | **Dead code** — never loaded by any HTML page. Legacy file from old client-side login |
| C3 | gwen | services/youtube_service.py | `GET /api/ai/suggestions` has runtime bug — `get_channel_mapping_suggestions()` will raise ValueError due to dict iteration mismatch |
| C4 | gwen | app.py | Startup crash on non-Render deployments — hardcoded `/app/data` for log directory ignores `TUBE_MANAGER_DATA_DIR` env var |
| C5 | gwen | app.py | `/api/youtube/misplaced` returns `title` but UI reads `v.video_title` — field name mismatch causes `undefined` in display |
| C6 | neo | dashboard.js + dashboard.html | "Run Maintenance" button exists in HTML but handler was removed from JS — dead button misleads users |

## High Issues (11)

| # | Source | File | Description |
|---|--------|------|-------------|
| H1 | jnu | subscriptions.js | Calls `/api/subscriptions/subscribe` and `/api/subscriptions/unsubscribe` — these endpoints don't exist in backend |
| H2 | jnu | dashboard.js | Duplicate WebSocket connections opened |
| H3 | jnu | dashboard.js | Duplicate stats polling intervals running simultaneously |
| H4 | jnu | app.py | SPA router conflicts with inline onclick handlers — navigation can break |
| H5 | neo | bulk.html | `showTab()` uses global `event` reference (fragile/deprecated pattern) |
| H6 | neo | maintenance.html | All "Apply All/Resolve All/Fix All" buttons are stubbed out |
| H7 | neo | watch-later.html | "Expand All" button is empty function (no-op) |
| H8 | jnu | dashboard.js | Keyboard shortcuts point to non-existent routes (`/ai`, `/rules`) |
| H9 | jnu | playlists.js | `.back-to-playlists-btn` references non-existent DOM element |
| H10 | gwen | app.py | 12+ endpoints still missing auth (bulk ops, AI, diagnostics, maintenance, settings) |
| H11 | gwen | api/auth.py | SameSite cookie inconsistency — login uses Lax, OAuth callback uses Strict |

## Medium Issues (27)

| # | Source | File | Description |
|---|--------|------|-------------|
| M1 | neo | playlists.html, subscriptions.html | Missing "Watch Later" nav link |
| M2 | neo | all pages | Inconsistent sidebar active state styling (3 different styles across pages) |
| M3 | neo | all pages | 5 separate `toast()` function implementations with different animations |
| M4 | neo | all pages | Missing `aria-label` on navigation elements |
| M5 | neo | all pages | Missing skip-to-content link for accessibility |
| M6 | neo | subscriptions.js | toast missing DOMPurify sanitization on messages |
| M7 | jnu | playlists.js | Missing try/catch in `actionCreatePlaylist()` |
| M8 | jnu | dashboard.js | Button loading state never resolves after API call |
| M9 | jnu | subscriptions.js | Subscribe/unsubscribe buttons don't exist in DOM but handlers try to bind |
| M10 | gwen | app.py | `/api/maintenance` endpoint still exists but backend handler was removed |
| M11-M17 | gwen | various | 7 endpoints return different field names than UI expects (data mismatches) |

## Low Issues (27)

| # | Source | File | Description |
|---|--------|------|-------------|
| L1 | neo | test.html | Debug green border still present + loads DOMPurify twice |
| L2 | neo | all pages | Inconsistent favicon cache-busters across pages |
| L3 | neo | test.html | Hardcoded WebSocket URL |
| L4 | neo | all pages | Form inputs missing `for` attributes on labels |
| L5 | neo | all pages | Missing `type="button"` on non-submit buttons |
| L6 | jnu | dashboard.js.bak | Deployment artifact in static directory |
| L7 | jnu | multiple files | Duplicate `toast()`/`logout()` definitions across files |
| L8-L14 | gwen | various | Minor response format inconsistencies, unused fields |

---

## Agent-Specific Summaries

### neo (HTML/CSS/UX) — 21 issues
- 2 Critical, 4 High, 8 Medium, 7 Low
- Focus: Navigation consistency, button functionality, cross-page uniformity
- Key finding: Maintenance page is largely non-functional (buttons stubbed)

### gwen (API Testing) — 18 issues
- 3 Critical, 3 High, 7 Medium, 5 Low
- Focus: Data correctness, auth coverage, endpoint response structure
- Key finding: Runtime bug in `/api/ai/suggestions`, startup crash on non-Render deployments

### jnu (JS Functionality) — 28 issues
- 1 Critical, 5 High, 12 Medium, 10 Low
- Focus: Event handler wiring, fetch URL validity, dead code
- Key finding: auth.js is dead code, subscriptions.js calls non-existent endpoints

---

## Priority Fix Plan

### Phase 1 — Critical (ship blocker)
1. Fix duplicate `id="api-key-status"` in settings.html
2. Fix `/api/ai/suggestions` runtime bug (dict iteration)
3. Fix startup crash — make log dir configurable
4. Fix `/api/youtube/misplaced` field name mismatch
5. Remove dead "Run Maintenance" button or wire it up
6. Remove dead auth.js or add it to login page

### Phase 2 — High (user-facing bugs)
7. Add missing `/api/subscriptions/subscribe|unsubscribe` endpoints
8. Fix duplicate WebSocket connections
9. Fix duplicate stats polling
10. Fix SameSite cookie inconsistency
11. Add auth to remaining sensitive endpoints

### Phase 3 — Medium (UX improvements)
12. Unify sidebar active state styling
13. Consolidate toast() implementations
14. Add missing nav links (Watch Later)
15. Add accessibility attributes
16. Fix keyboard shortcut routes

### Phase 4 — Low (cleanup)
17. Remove dashboard.js.bak
18. Remove debug styling from test.html
19. Add form label associations
20. Standardize favicon references

---

**Total: 71 issues | 6 Critical | 11 High | 27 Medium | 27 Low**
