# JavaScript Code Review Report — motus.leap Frontend

**Reviewer:** jnu (lightweight coder)  
**Date:** 2026-06-27  
**Scope:** All JS files in `/opt/data/motus.leap/tube-manager/web/static/`

---

## Files Reviewed

| File | Lines | Served On |
|------|-------|-----------|
| `dashboard.js` | 152 | `dashboard.html` only |
| `dashboard.js.bak` | 192 | **NOT served** (backup) |
| `playlists.js` | 316 | `playlists.html` only |
| `playlist.js` | 519 | `playlist.html` only |
| `auth-check.js` | 68 | All pages except `auth.html` |
| `auth.js` | 196 | **NOT served by any HTML** |
| `subscriptions.js` | 172 | `subscriptions.html` only |
| `mobile-nav.js` | 38 | All pages |
| `ux-enhancements.js` | 1210 | Most pages (not `subscriptions.html`) |
| `global_scripts.js` | 27 | `playlists.html`, `playlist.html` |

---

## 1. dashboard.js

**Served on:** `dashboard.html` (line 164)

### Event Listeners

| Line | Target | Event | Element Exists? | Notes |
|------|--------|-------|-----------------|-------|
| 115 | `#btn-fetch-all` | click | ✅ Yes (dashboard.html:116) | Calls `callAction('sync_playlists')` |
| 116 | `#btn-watch-later` | click | ✅ Yes (dashboard.html:117) | Calls `callAction('sync_watch_later')` |
| 118 | `#btn-cancel` | click | ✅ Yes (dashboard.html:143) | POSTs to `/api/action/cancel` |
| 128 | `#btn-copy-console` | click | ✅ Yes (dashboard.html:150) | Clipboard copy |
| 133 | `#btn-export-console` | click | ✅ Yes (dashboard.html:151) | Downloads text file |
| 145 | `#btn-clear-console` | click | ✅ Yes (dashboard.html:152) | Clears console |
| 150 | `document` | DOMContentLoaded | ✅ | Init: loadStats + connectWebSocket |

### fetch/AJAX Calls

| Line | URL | Method | Endpoint Exists? | Error Handling |
|------|-----|--------|-------------------|----------------|
| 18-27 | `/api/playlists`, `/api/watch-later`, `/api/subscriptions` | GET (via apiCall) | ✅ All exist | ✅ try/catch in `loadStats()` |
| 58 | `/ws/terminal?token=...` | WebSocket | ✅ WS endpoint | ✅ onerror/onclose handlers |
| 106 | `/api/action` | POST | ✅ Line 1388 app.py | ✅ try/catch |
| 120 | `/api/action/cancel` | POST | ✅ Line 1428 app.py | ✅ try/catch |

### DOM Manipulation

| Line | Target ID | Valid? | Operation |
|------|-----------|--------|-----------|
| 13-14 | `#console-output` | ✅ | appendChild + scrollTop |
| 39-48 | `#stat-*` | ✅ All exist | textContent |
| 146 | `#console-output` | ✅ | innerHTML = '' |

### Error Handling
- ✅ `loadStats()` has full try/catch
- ✅ `callAction()` has try/catch
- ✅ Cancel handler has try/catch
- ✅ WebSocket has onerror/onclose with reconnect

### Issues Found

| # | Severity | Line | Description |
|---|----------|------|-------------|
| D1 | **Medium** | 58 | WebSocket reconnect happens after 3s with no backoff escalation. Under sustained outage, this creates tight reconnect loops. |
| D2 | **Low** | 2 | Token read from `localStorage` at module scope. If token updates later, `apiCall` uses the old value (but since it's a `const`, re-login needed). |
| D3 | **Low** | 64 | `ws.send()` readyState check is good, but `clearInterval(pingInterval)` in onclose happens every close — even during intentional close from `connectWebSocket()`. Minor: first call to `connectWebSocket()` also triggers `ws.close()` on null which is safe. |

---

## 2. dashboard.js.bak (Backup Comparison)

**NOT served.** This is the old version. Key differences from active `dashboard.js`:

| Feature | Old (.bak) | New (active) |
|---------|-----------|--------------|
| Token refresh | Has `/api/auth/refresh` call | **Removed** — relies on auth-check.js in `<head>` |
| Stats polling | `setInterval` every 2 min | **Single loadStats() call**, no polling |
| Stats source | `/api/stats` | `/api/playlists`, `/api/watch-later`, `/api/subscriptions` |
| Security check | `checkSecurityStatus()` | **Removed** |
| User avatar | `loadUserAvatar()` | **Removed** |
| Toast function | Full implementation with DOMPurify | **Not in dashboard.js** (relies on global) |
| Stat elements | `#pending-data`, `#pending-still`, `#pending-ai`, `#ai-rate`, `#ai-rates`, `#last-scan`, `#app-status`, `#status-label` | **Not referenced** (removed from JS) |
| Action buttons | `.action-btn` dataset handlers | Replaced with individual button handlers |

### Issues

| # | Severity | Description |
|---|----------|-------------|
| B1 | **Low** | `.bak` file is unnecessary deployment artifact. Could be confusing if accidentally served. |
| B2 | **Medium** | Old `.bak` calls `checkSecurityStatus()` hitting `/api/auth/security/status` which **does not exist** as an endpoint (only found in settings.html inline JS, NOT in app.py). This would 404 on every dashboard load if the .bak were active. |
| B3 | **Low** | Old `.bak` references DOM elements (`#pending-data`, `#pending-still`, `#pending-ai`, `#ai-rate`, `#ai-rates`, `#last-scan`, `#status-label`, `#app-status`, `#user-avatar`) that **don't exist** in current `dashboard.html`. Would cause null-reference errors. |

---

## 3. playlists.js

**Served on:** `playlists.html` (line 104)

### Event Listeners

This file has **zero `addEventListener` calls**. All event handling is via inline `onclick` in dynamically-generated HTML.

| Line | Target Pattern | Event | Notes |
|------|---------------|-------|-------|
| 34 | `<button>` (injected) | onclick=`actionCreatePlaylist()` | ✅ Works |
| 78 | `<div>` card | onclick=`window.location.href='/playlist/...'` | ✅ Works |
| 81 | "YouTube" button | onclick=`openPlaylist(...)` | ✅ Works |
| 85 | Rescan button | onclick=`rescanPlaylist(...)` | ✅ Works |
| 87 | Manage button | onclick=`openManagePlaylistModal(...)` | ✅ Works |

### fetch/AJAX Calls

| Line | URL | Method | Endpoint Exists? | Error Handling |
|------|-----|--------|-------------------|----------------|
| 45 | `/api/playlists` | GET | ✅ Line 734 app.py | ✅ try/catch, renders error |
| 108 | `/api/youtube/videos?playlist_id=...&force_refresh=true` | GET | ✅ Line 640 app.py | ✅ try/catch |
| 150 | `/api/youtube/playlists/delete` | POST | ✅ Line 794 app.py | ✅ try/catch |
| 200 | `/api/youtube/playlists/rename` | POST | ✅ Line 742 app.py | ✅ try/catch |
| 225 | `/api/youtube/playlists/duplicate` | POST | ✅ Line 901 app.py | ✅ try/catch |
| 248 | `/api/youtube/playlists/create` | POST | ✅ Line 837 app.py | ⚠️ Only `resp.ok` check, no try/catch |
| 261 | `/api/youtube/playlists/delete` | POST | ✅ Line 794 app.py | ✅ try/catch |

### DOM Manipulation

| Line | Target ID | Valid? | Operation |
|------|-----------|--------|-----------|
| 34 | `#playlists-skeleton` | ✅ | insertAdjacentHTML beforebegin |
| 64 | `#playlists-list` | ✅ | innerHTML |

### Navigation
- Line 78: `window.location.href='/playlist/${p.id}'` — ✅ Routes to `/playlist/{id}`, valid per routing

### Issues Found

| # | Severity | Line | Description |
|---|----------|------|-------------|
| P1 | **Medium** | 248 | `actionCreatePlaylist()` has **NO try/catch** around the fetch. Network errors are unhandled (silent failure). |
| P2 | **Medium** | 313 | `syncPlaylists()` references `e.target` but the button has no event listener attached from this file — it relies on the onclick attribute being set elsewhere. If `syncPlaylists` is called without an event, `e.target` will be undefined → TypeError. |
| P3 | **Low** | 34 | `insertAdjacentHTML` injects a button on **every call** to `loadPlaylists()`. Since `loadPlaylists()` is called on rescan and after create/rename/delete, multiple "New Playlist" buttons accumulate. |
| P4 | **Low** | 65 | Error message references `DOMPurify.sanitize()` but if DOMPurify fails to load, this crashes. The dependency chain is: global_scripts.js → DOMPurify loaded via CSP-allowed CDN. |
| P5 | **Medium** | 87 | Template literal with `\`${p.title.replace(/\'/g, \"\\\\'\")}\`` in onclick handler. Apostrophe escaping is handled but backticks in playlist titles would break the JS. |

---

## 4. playlist.js

**Served on:** `playlist.html` (line 132)

### Event Listeners (via `initPlaylistPage`, line 493)

| Line | Target ID | Event | Element Exists? |
|------|-----------|-------|-----------------|
| 501 | `#rescan-playlist-btn` | click | ✅ (playlist.html:79) |
| 502 | `#btn-scan-dup` | click | ✅ (playlist.html:80) |
| 503 | `#btn-scan-mis` | click | ✅ (playlist.html:81) |
| 504 | `#delete-duplicates-btn` | click | ✅ (playlist.html:93) |
| 505 | `#move-misplaced-btn` | click | ✅ (playlist.html:96) |
| 506 | `#scan-filter` | change | ✅ (playlist.html:100) |
| 509 | `.back-to-playlists-btn` | click | ⚠️ **NOT FOUND** in playlist.html |

### fetch/AJAX Calls

| Line | URL | Method | Endpoint Exists? | Error Handling |
|------|-----|--------|-------------------|----------------|
| 28 | `/api/youtube/videos?playlist_id=...&force_refresh=true` | GET | ✅ | ✅ try/catch |
| 71 | `/api/playlists` | GET | ✅ | ⚠️ No explicit catch on this one |
| 94 | `/api/youtube/videos?playlist_id=...` | GET | ✅ | ✅ try/catch |
| 197 | `/api/bulk/move` | POST | ✅ api/bulk_operations.py:182 | ✅ try/catch |
| 256 | `/api/youtube/misplaced?playlist_id=...` | GET | ✅ Line 668 app.py | ✅ try/catch |
| 412 | `/api/bulk/delete` | POST | ✅ api/bulk_operations.py:219 | ✅ try/catch |
| 460 | `/api/bulk/move` | POST | ✅ | ✅ try/catch |

### Issues Found

| # | Severity | Line | Description |
|---|----------|------|-------------|
| PJ1 | **High** | 509 | `.back-to-playlists-btn` — **element does NOT exist** in `playlist.html`. Optional chaining (`?.`) prevents crash but the "Back to Playlists" button is non-functional. |
| PJ2 | **Medium** | 71-91 | First fetch (`/api/playlists`) has NO try/catch. If it fails, the second fetch runs anyway, and `allPlaylists` stays `[]` silently. |
| PJ3 | **Low** | 78-79 | `playlistId` extracted from URL path. If URL is `/playlist/` (no ID), `playlistId` = `"Playlist"` which would cause API calls with invalid ID. |
| PJ4 | **Low** | 462 | `rescanPlaylist()` declares `playlistId` from window.location but it's scoped per-load. If SPA navigates to a different playlist, the old closure value persists until full reload. |

---

## 5. auth-check.js

**Served on:** All pages except `auth.html` (10 pages)

### Event Listeners
**None.** This is a self-invoking function.

### fetch/AJAX Calls

| Line | URL | Method | Endpoint Exists? | Error Handling |
|------|-----|--------|-------------------|----------------|
| 44 | `/api/auth/me` | GET | ✅ api/auth.py | ✅ .then/.catch |
| 61 | (retry) `/api/auth/me` | GET | ✅ | ✅ setTimeout retry |

### Logic Flow
1. Parse URL fragment for OAuth token → store in localStorage + cookie
2. Read token from cookie or localStorage
3. If no token → redirect to `/auth`
4. Sync localStorage → cookie
5. Validate token via `/api/auth/me`
6. On 401 → clear and redirect to `/auth`
7. On network error → retry once after 1.5s

### Issues Found

| # | Severity | Line | Description |
|---|----------|------|-------------|
| AC1 | **Medium** | 7 | Sets cookie without `Secure` flag. If served over HTTPS (production), cookies should have `Secure;` attribute. |
| AC2 | **Low** | 58 | On network error (e.g., Render cold start), the retry leaves the user on the page with no token. No visual indicator that auth is pending. |

---

## 6. auth.js

**⚠️ NOT SERVED by any HTML file.** This is dead code.

### Analysis
- Defines `handleLogin()`, `handleRegister()`, `handleGoogleLogin()`, `showForm()`, `logout()`
- References DOM elements: `#login-form`, `#register-form`, `#login-tab`, `#register-tab`, `#google-login-btn`, `#login-btn`, `#register-account-btn`, `#login-email`, `#login-password`, `#register-username`, `#register-email`, `#register-password`, `#login-error`, `#register-error`
- **None of these elements exist** in `auth.html` (which is a simple status/redirect page)

### Issues

| # | Severity | Description |
|---|----------|-------------|
| AJ1 | **Critical** | `auth.js` is **dead code** — never loaded by any HTML page. The login/register UI it expects doesn't exist. The actual auth flow is handled by `auth.html` (a simple callback page) + server-side rendering. |
| AJ2 | **Medium** | If someone were to serve this file, `checkSession()` (line 115) runs immediately and redirects to `/dashboard` if valid — but this would race with `auth-check.js` which does the same. |

---

## 7. subscriptions.js

**Served on:** `subscriptions.html` (line 101)

### Event Listeners
**None.** All via inline onclick in generated HTML.

### fetch/AJAX Calls

| Line | URL | Method | Endpoint Exists? | Error Handling |
|------|-----|--------|-------------------|----------------|
| 27 | `/api/subscriptions` | GET | ✅ Line 999 app.py | ✅ try/catch |
| 28 | `/api/mappings` | GET | ✅ Line 1069 app.py | ✅ .catch(() => null) |
| 91 | `/api/mappings` | GET | ✅ | ✅ .catch |
| 93 | `/api/mappings` | POST | ✅ Line 1098 app.py | ✅ try/catch |
| 122 | `/api/maintenance` | GET | ✅ Line 1011 app.py | ✅ try/catch |
| 154 | `/api/subscriptions/subscribe` | POST | ⚠️ **NOT FOUND** | ⚠️ Only `alert()` on failure |
| 165 | `/api/subscriptions/unsubscribe` | POST | ⚠️ **NOT FOUND** | ⚠️ Only `alert()` on failure |

### Issues Found

| # | Severity | Line | Description |
|---|----------|------|-------------|
| SJ1 | **High** | 154 | `/api/subscriptions/subscribe` — **endpoint does NOT exist** in app.py. The `actionSubscribe()` function will always fail. |
| SJ2 | **High** | 165 | `/api/subscriptions/unsubscribe` — **endpoint does NOT exist** in app.py. The `actionUnsubscribe()` function will always fail. |
| SJ3 | **Medium** | 152 | Regex for channel ID extraction: `/([A-Za-z0-9_-]{20,})/` — YouTube channel IDs are exactly 24 chars. This regex would also match long video IDs or other URL segments. |
| SJ4 | **Low** | 159 | `if (resp.ok) refreshSubscriptions()` — no error feedback on failure, just silent retry. |

---

## 8. mobile-nav.js

**Served on:** All 9 pages

### Event Listeners

| Line | Target | Event | Element Exists? |
|------|--------|-------|-----------------|
| 24 | `#sidebar-toggle` | click | ✅ All pages |
| 25 | `#mobile-overlay` | click | ✅ All pages |
| 28 | `document` | keydown (Escape) | ✅ |
| 33-37 | `sidebar a` | click | ✅ (links exist in aside) |

### Logic
- Guards: `if (!sidebar || !overlay || !toggle) return;` — safe
- Exposes `window.openMobileSidebar` / `window.closeMobileSidebar` — used by inline onclick in HTML
- Closes sidebar on link click (mobile only)

### Issues

| # | Severity | Line | Description |
|---|----------|------|-------------|
| MN1 | **Low** | 33-37 | Sidebar link click handler fires on ALL clicks including middle-click / ctrl+click. Should only close for actual navigations. |

---

## 9. ux-enhancements.js

**Served on:** 7 pages (not `subscriptions.html`, not `settings.html`)

### Event Listeners

| Line | Target | Event | Notes |
|------|--------|-------|-------|
| 274 | `document` | keydown | Keyboard shortcuts |
| 646-651 | `button[data-action]` | click | Loading state on action buttons |
| 663 | `document` | DOMContentLoaded | `initUXEnhancements()` |
| 821 | `document` | DOMContentLoaded | `initSystemActivityController()` |
| 821 | `document` | visibilitychange | Pause polling |
| 821 | `window` | beforeunload | Stop polling |
| 900 | `document` | click (capture) | SPA link interception |
| 931 | `window` | popstate | SPA back/forward |
| 1023 | `document` | visibilitychange | Pause polling (duplicate) |
| 1023 | `window` | beforeunload | Stop polling (duplicate) |
| 1203 | `document` | DOMContentLoaded | `initGlobalAgentDrawer()` |

### fetch/AJAX Calls

| Line | URL | Method | Endpoint Exists? | Error Handling |
|------|-----|--------|-------------------|----------------|
| 756 | `/api/stats` | GET | ✅ Line 691 app.py | ✅ try/catch |
| 1088 | `/api/stats` | GET | ✅ | ✅ try/catch |
| 1162 | `/api/action/cancel` | POST | ✅ | ✅ try/catch |

### Issues Found

| # | Severity | Line | Description |
|---|----------|------|-------------|
| UX1 | **High** | 787-818 + 1025-1152 | **DUPLICATE code**: `initSystemActivityController()` (line 670-818) and `startAgentActivityTracker()` (line 1025-1152) both poll `/api/stats` with `setInterval`. Both register `visibilitychange` and `beforeunload` listeners. Both are initialized on `DOMContentLoaded`. This means **4 stats polls** are running simultaneously. |
| UX2 | **Medium** | 900-928 | SPA router intercepts ALL clicks in capture phase. The `onclick` handler on `[onclick]` elements uses `e.stopPropagation()` but the SPA router calls `e.preventDefault()` + `e.stopPropagation()` BEFORE the inline handler fires. This means **inline onclick handlers on `[onclick]` elements never execute** — they're overridden by the SPA router. |
| UX3 | **Medium** | 905 | SPA router excludes `/auth` and `/oauth` but NOT `/auth.html` directly. If someone links to `/auth` it works, but the exclusion check is `href.startsWith('/auth')` which also blocks any route starting with "auth" (e.g., `/authority`). |
| UX4 | **Low** | 323 | Keyboard shortcut `g+a` navigates to `/ai` — but there's no `/ai` route in the app (no `ai.html`). This would 404. |
| UX5 | **Low** | 313 | Keyboard shortcut `g+r` navigates to `/rules` — but there's no `/rules` route. Would 404. |
| UX6 | **Medium** | 646-651 | `showButtonLoading` is called on `button[data-action]` click but `hideButtonLoading` is never called — there's no completion callback. Buttons stay in loading state forever. |
| UX7 | **Low** | 1057 | `innerHTML` with `text` from WebSocket message. If `text` contains HTML, it'll be rendered. Should use `textContent` or sanitize. |
| UX8 | **Medium** | 1162 | `cancelCurrentTask` sends POST to `/api/action/cancel` with no body. The active `dashboard.js` sends `JSON.stringify({})` — inconsistency, but likely both work. |

---

## 10. global_scripts.js

**Served on:** `playlists.html`, `playlist.html`

### Functions Defined

| Function | Lines | Called? |
|----------|-------|---------|
| `toast()` | 1-16 | ✅ Called by playlists.js, playlist.js, subscriptions.js |
| `createToastContainer()` | 13-19 | ✅ Called by toast() |
| `logoutUser()` | 21-28 | ⚠️ **Never called** from any JS file |

### Issues

| # | Severity | Line | Description |
|---|----------|------|-------------|
| GS1 | **Low** | 13 | `toast()` does NOT sanitize the message — `el.innerHTML = ...${message}`. Other files (playlists.js, subscriptions.js) call `toast(DOMPurify.sanitize(...))` before passing, but if anyone calls `toast()` directly with user input, it's an XSS vector. |
| GS2 | **Low** | 21 | `logoutUser()` is defined but never called. `auth-check.js` defines `window.logout` and `dashboard.js.bak` defines `logout()` — this is a third implementation. |

---

## Cross-Cutting Issues

### CSP & Script Loading

| # | Severity | Description |
|---|----------|-------------|
| CC1 | **Medium** | `playlists.html` CSP explicitly allows specific scripts. Other pages (e.g., `dashboard.html`, `playlist.html`) do NOT have CSP meta tags — they rely on server defaults. If the server sends restrictive CSP headers, inline scripts/handlers will break. |
| CC2 | **Low** | `ux-enhancements.js` is loaded on 7 pages but performs heavy DOM manipulation (SPA router, keyboard shortcuts, agent drawer) on ALL of them. On pages that don't need these features (e.g., `bulk.html`), this is unnecessary overhead. |

### Duplicate Function Definitions

| # | Severity | Description |
|---|----------|-------------|
| DF1 | **High** | `toast()` is defined in **3 files**: `global_scripts.js`, `ux-enhancements.js` (as `showSuccessToast`/`showInfoToast`/`showErrorToast` — different names but same purpose), and `dashboard.js.bak`. Since `global_scripts.js` loads on only 2 pages, other pages have no `toast()` unless `ux-enhancements.js` provides alternatives. |
| DF2 | **Medium** | `logout()` / `logoutUser()` / `window.logout` defined in 3 places with different implementations. |

### WebSocket Connections

| # | Severity | Description |
|---|----------|-------------|
| WS1 | **High** | **Two separate WebSocket connections** to `/ws/terminal` are opened on pages that load both `dashboard.js` and `ux-enhancements.js`: `dashboard.js` opens one (line 58), and `ux-enhancements.js` `startAgentActivityTracker()` opens another (line 1035). This doubles WebSocket overhead. |

---

## Summary by Severity

| Severity | Count | Key Issues |
|----------|-------|------------|
| **Critical** | 1 | `auth.js` is dead code, never loaded |
| **High** | 5 | Missing API endpoints (subscribe/unsubscribe), duplicate polling, SPA router overriding inline onclick, duplicate WebSocket connections, `.back-to-playlists-btn` missing element |
| **Medium** | 12 | Missing try/catch, button loading never resolves, innerHTML XSS surface, keyboard shortcuts to non-existent routes, token cookie without Secure flag, SPA click interception conflicts, channel ID regex |
| **Low** | 10 | Dead `logoutUser()`, unused `auth.js` functions, multiple toast implementations, minor edge cases |

---

## Recommendations (Priority)

1. **Remove `auth.js`** — it's dead code that could cause confusion
2. **Remove `dashboard.js.bak`** — deployment artifact
3. **Fix `/api/subscriptions/subscribe` and `/api/subscriptions/unsubscribe`** endpoints or remove the UI buttons
4. **Deduplicate WebSocket** — use a shared module or check `window._wsConnection` before opening
5. **Fix duplicate stats polling** — `initSystemActivityController` vs `startAgentActivityTracker`
6. **Fix SPA router vs inline onclick conflict** — the capture-phase handler prevents inline onclick from firing
7. **Add try/catch to `actionCreatePlaylist()`** in playlists.js
8. **Add `.back-to-playlists-btn`** to `playlist.html` or remove the handler
