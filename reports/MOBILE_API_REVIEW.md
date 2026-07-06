# motus.leap — Mobile-Specific API Review

**Reviewer:** gwen (research scout)  
**Date:** 2026-06-28  
**Scope:** API endpoints, payload sizes, pagination, image handling, connection efficiency, offline support, PWA features, data usage  

---

## Executive Summary

motus.leap is reasonably well-architected for mobile with good caching, HTTP/2 support, and parallel fetching on the dashboard. However, there are several **HIGH** impact issues: the `/api/youtube/fetch-all` endpoint can return massive payloads (potentially 1MB+), no PWA manifest or service worker exists, images use YouTube's default thumbnails without responsive sizing or lazy loading, and there's no client-side retry logic for failed API calls.

---

## 1. Payload Sizes

### Findings

| Endpoint | Returns | Size Risk | Notes |
|----------|---------|-----------|-------|
| `/api/youtube/fetch-all` | ALL playlists + subscriptions + videos (up to 500 videos × 200 with force_refresh) | **HIGH** | Can exceed 1MB easily with 500 video objects containing titles, descriptions, channel info |
| `/api/playlists` | Full playlist list (all items) | Medium | Bounded by YouTube's 5000 cap; typically 50-200 playlists |
| `/api/subscriptions` | All channels with stats | Medium | One item per subscription; usually <100 |
| `/api/watch-later` | Up to 200 videos | Low-Medium | Single page, max 50 items per YouTube API call |
| `/api/youtube/videos` | Playlist videos | Low | Single playlist scope |

### Compression

**Status: ❌ No compression middleware configured**

- No `GZipMiddleware`, `BrotliMiddleware`, or `CompressionMiddleware` found in `app.py`
- `no_cache_file_response()` sets `Cache-Control: no-store` but no `Content-Encoding` header
- Static files served via `StaticFiles` with no compression

**Impact:** Large JSON responses (especially `fetch-all`) are sent uncompressed. On slow mobile connections, a 500KB+ JSON payload takes significantly longer than necessary.

### Estimated Payload Sizes

A typical `fetch-all` response for a user with:
- 30 playlists × ~200 bytes each = ~6KB
- 50 subscriptions × ~500 bytes each = ~25KB
- 200 videos × ~600 bytes each = ~120KB

**Total: ~150KB uncompressed** — manageable but not trivial on 3G. Users with many playlists and forced refresh (up to 500 videos) could see **300KB-500KB+**. With channel descriptions enabled, could approach **1MB+**.

### Issue 1.1 — Large fetch-all Payload
| Attribute | Value |
|-----------|-------|
| **Impact** | HIGH |
| **Effort** | MEDIUM |
| **Description** | `/api/youtube/fetch-all` returns ALL data in one response. With 500 videos and full metadata, this can be 500KB-1MB+. On slow mobile connections, this blocks the page render. |
| **Suggested Fix** | Implement field selection (sparse fieldsets). Allow `?fields=playlists(id,title),subscriptions(id,title)`. Alternatively, defer video duration data to a secondary request. |

### Issue 1.2 — No Response Compression
| Attribute | Value |
|-----------|-------|
| **Impact** | MEDIUM |
| **Effort** | LOW |
| **Description** | No gzip/brotli compression on API responses. Starlette/FastAPI supports `GZipMiddleware` natively. |
| **Suggested Fix** | Add `from starlette.middleware.gzip import GZipMiddleware` and `app.add_middleware(GZipMiddleware, minimum_size=500)` |

---

## 2. Pagination

### Findings

| Endpoint | Paginates? | Max Page Size | Client-Side Pagination? |
|----------|-----------|---------------|------------------------|
| `/api/youtube/fetch-all` | Server-side only (YouTube API) | N/A — returns ALL | ❌ No |
| `/api/playlists` | Server-side only | 50 (YouTube API max) | ❌ No |
| `/api/subscriptions` | Server-side only | 50 | ❌ No |
| `/api/youtube/videos` | Server-side only | 50 | ❌ No |
| `/api/bulk/operations` | ✅ Yes (limit/offset) | Default 20, unbounded | ✅ Yes |
| `/api/watch-later` | No | Single page | ❌ No |

**Key observation:** `_fetch_all_paginated()` in `youtube_service.py` (line 466) has a `max_items=500` default (`max_items=500` from `_fetch_all_paginated`, but callers pass `max_items=5000`). This means up to **5000 items** can be fetched across 100 API pages — all returned in a single response to the client.

### Issue 2.1 — No Client-Side Pagination for Playlists/Subscriptions
| Attribute | Value |
|-----------|-------|
| **Impact** | HIGH |
| **Effort** | MEDIUM |
| **Description** | All list endpoints return the complete dataset. A user with hundreds of playlists gets all data in one shot, causing long parse/render times on mobile. |
| **Suggested Fix** | Add `?page` and `?page_size` query params. Return `{items, total, page, has_more}` wrapper. Use virtual scrolling or infinite scroll on the client. |

### Issue 2.2 — fetch-all Has No Limits
| Attribute | Value |
|-----------|-------|
| **Impact** | HIGH |
| **Effort** | LOW |
| **Description** | `/api/youtube/fetch-all` accepts no size limits. `force_refresh=true` fetches up to 2000 videos. On mobile, this is a data-hungry operation with no way to scope it down. |
| **Suggested Fix** | Add `?max_videos=100` and `?include_videos=false` params. Let mobile clients request lightweight data. |

---

## 3. Image Handling

### Findings

**No responsive images:**
- Thumbnails come from YouTube's `snippet.thumbnails.default.url` (typically 120×90px)
- No `srcset` or `<picture>` elements anywhere
- Images are rendered at their downloaded size regardless

**No lazy loading:**
- Zero instances of `loading="lazy"` attribute in any HTML or JS-rendered `<img>` tags
- Zero instances of `IntersectionObserver` for image loading
- All thumbnails render immediately in `innerHTML` templates

**No WebP optimization:**
- Thumbnail URLs point directly to YouTube's CDN (`i.ytimg.com`, `yt3.ggpht.com`)
- No client-side image processing or format selection
- Fallback placeholder: `https://picsum.photos/160/90` (external dependency, not optimized)

### Issue 3.1 — No Lazy Loading for Images
| Attribute | Value |
|-----------|-------|
| **Impact** | HIGH |
| **Effort** | LOW |
| **Description** | Playlist and subscription grids render ALL thumbnails immediately. A page with 200 playlist cards loads 200 thumbnail images simultaneously, consuming bandwidth and slowing render on mobile. |
| **Suggested Fix** | Add `loading="lazy"` to all `<img>` tags rendered via JS. Browsers handle lazy loading natively with no JS overhead. |

### Issue 3.2 — No Responsive Images
| Attribute | Value |
|-----------|-------|
| **Impact** | MEDIUM |
| **Effort** | LOW |
| **Description** | YouTube provides multiple thumbnail sizes (default: 120×90, medium: 320×180, high: 480×360, maxres: 1280×720). The app always uses `default` size (tiny on desktop, blurry when scaled up, wasteful on mobile). |
| **Suggested Fix** | Use `medium` or `high` quality for cards, and add `srcset` if serving custom thumbnails. For JS-rendered images, use `?quality=80&width=320` YouTube URL params or proxy through a CDN. |

### Issue 3.3 — picsum.photos as Placeholder
| Attribute | Value |
|-----------|-------|
| **Impact** | MEDIUM |
| **Effort** | LOW |
| **Description** | Missing thumbnails fall back to `https://picsum.photos/160/90` — an external dependency that can fail, adds DNS lookup, and returns random images unrelated to the content. |
| **Suggested Fix** | Generate a simple SVG/CSS placeholder locally, or use a gray div with a video icon. |

---

## 4. Connection Efficiency

### Findings

**HTTP/2: ✅ Supported**
- `core/http_client.py` line 30: `http2=True` — HTTP/2 multiplexing is enabled for outbound YouTube API calls
- **However:** This is for server→YouTube API. The client←server connection depends on the hosting setup (Render.com supports HTTP/2)

**Connection Pooling: ✅ Server-side**
- `AsyncClient` with `max_keepalive_connections=10`, `max_connections=20`, `keepalive_expiry=30.0`
- Connection reuse for YouTube API calls

**Dashboard Page Load: 3 parallel API calls**
```javascript
// dashboard.js line 31
const [plResp, wlResp, subResp] = await Promise.all([
    apiCall('/api/playlists'),
    apiCall('/api/watch-later'),
    apiCall('/api/subscriptions')
]);
```
This is well-optimized — parallel rather than sequential.

**Subscriptions Page Load: 2 parallel calls**
```javascript
// subscriptions.js line 26
const [subResp, mapResp] = await Promise.all([
    fetch('/api/subscriptions'),
    fetch('/api/mappings')
]);
```
Also well-optimized.

**Playlists Page: 1 call, but caches to localStorage**
```javascript
// playlists.js line 14-30
// Uses localStorage cache first, then fetches fresh data
```

### Issue 4.1 — N+1 on list_playlists Change Detection
| Attribute | Value |
|-----------|-------|
| **Impact** | MEDIUM |
| **Effort** | MEDIUM |
| **Description** | `list_playlists()` in `youtube_service.py` line 331-342: if a change is detected (rename/addition/removal), it triggers `fetch_all_data()` which itself makes multiple API calls. So a single client `/api/playlists` call can cascade into: 1 (check playlists) + 1 (check subscriptions) + 1 (fetch playlists) + N (fetch videos for 10-50 playlists) = potentially 15-50 YouTube API calls. |
| **Suggested Fix** | Separate the lightweight check from the full playlists immediately; trigger background sync only when user explicitly requests it or when data is clearly stale (>1hr). |

### Issue 4.2 — No Server-Side Keep-Alive Configuration Documented
| Attribute | Value |
|-----------|-------|
| **Impact** | LOW |
| **Effort** | LOW |
| **Description** | HTTP keep-alive between client and FastAPI server isn't explicitly configured. On mobile, establishing new TCP connections for each API call adds latency. |
| **Suggested Fix** | Uvicorn (the ASGI server) defaults to keep-alive. Verify the hosting proxy (Render) preserves it. No code change needed; add documentation noting the dependency. |

---

## 5. Offline/Weak Connection Handling

### Findings

**Service Worker: ❌ None**
- No service worker registration (`navigator.serviceWorker.register` not found anywhere)
- No `sw.js` file in the project
- No offline fallback page

**HTML Caching: ❌ Aggressively Disabled**
```python
# app.py line 297
"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"
```
Every HTML page is served with `no-store`. This means every navigation requires a network round-trip. On flaky mobile connections, this causes blank screens.

**Server-Side Cache (Memory + Disk): ✅ Good**
- LRU cache with 100-item in-memory and disk persistence
- 10-minute TTL for most data
- 6-hour LRU cache option

**Client-Side Cache (localStorage): ⚠️ Limited**
- `cached_playlists` in localStorage (playlists.js)
- `cached_subscriptions` in localStorage (subscriptions.js)
- Used for initial render, but **not validated** against server state
- No cache versioning or invalidation strategy

**Retry Logic (Client-Side): ⚠️ Minimal**
```javascript
// auth-check.js line 58-64
.catch(() => {
    if (attempt < 1) {
        setTimeout(() => validateToken(attempt + 1), 1500);
    });
    // If retry also fails, leave user on page
});
```
Only `auth-check.js` has retry (1 attempt, 1.5s delay). All other fetch calls have basic `.catch()` but no retry.

**Retry Logic (Server-Side): ✅ Good**
```python
# background_worker.py line 35-62
async def _retry_with_backoff(coro_fn, max_retries=3, base_delay=1.0):
    # Exponential backoff: 1s, 2s, 4s
```

### Issue 5.1 — No Service Worker / Offline Support
| Attribute | Value |
|-----------|-------|
| **Impact** | HIGH |
| **Effort** | MEDIUM |
| **Description** | No service worker means the app is completely unusable offline. On mobile, users commonly lose connectivity temporarily. Even a basic offline shell (cached HTML shell + "you're offline" message) would dramatically improve perceived reliability. |
| **Suggested Fix** | Register a service worker that caches the HTML shell and static assets. Use a cache-first strategy for static files, network-first for API calls. |

### Issue 5.2 — No Retry for Failed API Calls (Client-Side)
| Attribute | Value |
|-----------|-------|
| **Impact** | HIGH |
| **Effort** | LOW |
| **Description** | All API calls (except auth) use simple `fetch().catch()` with no retry. On mobile, transient network failures are common. A dropped connection during `fetch-all` shows a generic error with no automatic recovery. |
| **Suggested Fix** | Implement a client-side fetch wrapper with retry: exponential backoff, max 3 attempts, detect network status via `navigator.onLine`. |

### Issue 5.3 — Aggressive No-Cache Headers Hurt Mobile Performance
| Attribute | Value |
|-----------|-------|
| **Impact** | MEDIUM |
| **Effort** | LOW |
| **Description** | Serving HTML with `Cache-Control: no-store` means mobile browsers can't cache pages locally. Every back-navigation or re-visit requires re-downloading the entire HTML + JS + CSS bundle. |
| **Suggested Fix** | Use `Cache-Control: no-cache` (allows conditional requests with ETag) instead of `no-store` for HTML pages. Cache static assets aggressively with content-hash filenames. |

---

## 6. Mobile-Specific Features

### Findings

| Feature | Status | Notes |
|---------|--------|-------|
| Viewport meta tag | ✅ All pages | `<meta name="viewport" content="width=device-width, initial-scale=1.0">` |
| PWA manifest | ❌ None | No `manifest.json`, no `<link rel="manifest">` |
| Apple mobile web app | ❌ None | No `apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style` |
| Theme color | ❌ None | No `<meta name="theme-color">` anywhere |
| Touch icons | ❌ None | No `apple-touch-icon` links |
| Mobile nav | ✅ Yes | `mobile-nav.js` with responsive sidebar toggle |
| Responsive layout | ✅ Yes | Tailwind responsive classes (`md:hidden`, etc.) |

### Issue 6.1 — No PWA Manifest
| Attribute | Value |
|-----------|-------|
| **Impact** | MEDIUM |
| **Effort** | LOW |
| **Description** | No PWA manifest means users cannot install the app to their home screen. On mobile, this is a key differentiator between a "website" and an "app-like experience." |
| **Suggested Fix** | Create a `manifest.json` with app name, icons (192px, 512px), `display: standalone`, `start_url: /dashboard`. Link it in every HTML page. |

### Issue 6.2 — No Theme Color Meta Tag
| Attribute | Value |
|-----------|-------|
| **Impact** | LOW |
| **Effort** | LOW |
| **Description** | The dark theme (#0f1115) doesn't extend to the browser chrome (address bar). On mobile, this creates a jarring white/transition flash before the page loads. |
| **Suggested Fix** | Add `<meta name="theme-color" content="#0f1115">` to all pages. Also add `apple-mobile-web-app-status-bar-style: black-translucent`. |

---

## 7. Data Usage

### Typical Page Load API Calls

| Page | API Calls | Parallel? | Data Estimate |
|------|-----------|-----------|----------------|
| Dashboard (initial) | 3 (`/api/playlists`, `/api/watch-later`, `/api/subscriptions`) | ✅ Yes | ~50-100KB |
| Dashboard (cached) | 1 (auth validation only) | N/A | <1KB |
| Playlists page | 1 (`/api/playlists`) + localStorage cache | Yes | ~20-80KB |
| Subscriptions page | 2 (`/api/subscriptions`, `/api/mappings`) | ✅ Yes | ~15-40KB |
| Playlist detail | 1-2 (`/api/youtube/videos` + optional fetch_all) | No | ~30-150KB |
| Settings/Bulk | 2-5 individual calls | Mixed | Variable |

### WebSocket Connection

**Status: ❌ No persistent WebSocket on normal pages**

The WebSocket (`/ws/terminal`) is only used on the dashboard for background task notifications. It's not maintained during normal browsing. When active:
- Ping/pong heartbeat every 30 seconds
- Reconnect logic in dashboard.js (line 69): "WebSocket unresponsive; reconnecting..."

**Battery impact: Low** — WebSocket is only active when the dashboard tab is visible and a background task is running.

### Data Saving Opportunities

### Issue 7.1 — localStorage Cache Not Used Effectively for Offline
| Attribute | Value |
|-----------|-------|
| **Impact** | MEDIUM |
| **Effort** | LOW |
| **Description** | localStorage is used for initial render but updates always trigger fresh API calls. When the user revisits the playlists page on a slow connection, they wait for the API response even though cached data is available (data may be 10+ minutes old but still usable). |
| **Suggested Fix** | Implement stale-while-revalidate pattern: render from localStorage immediately, fetch fresh data in background, update UI incrementally. This gives instant load on repeat visits. |

### Issue 7.2 — No Response Caching on HTTP Layer
| Attribute | Value |
|-----------|-------|
| **Impact** | MEDIUM |
| **Effort** | MEDIUM |
| **Description** | API responses don't include `ETag` or `Last-Modified` headers. The browser cannot make conditional requests, so full data is re-downloaded even if nothing changed. |
| **Suggested Fix** | Add ETag support for cacheable endpoints (`/api/playlists`, `/api/subscriptions`). Use the `cached_at` timestamp to generate ETag. Return `304 Not Modified` when client sends `If-None-Match`. |

### Issue 7.3 — Google Fonts and CDN Dependencies
| Attribute | Value |
|-----------|-------|
| **Impact** | MEDIUM |
| **Effort** | LOW |
| **Description** | Every page loads Google Fonts (`fonts.googleapis.com`, `fonts.gstatic.com`), Font Awesome (`cdnjs.cloudflare.com`), Tailwind CDN (`cdn.tailwindcss.com`), and DOMPurify (`cdnjs.cloudflare.com`). On mobile, each external domain requires DNS + TLS + TCP setup. 5 external domains per page. |
| **Suggested Fix** | Self-host critical assets. Subset fonts (only load weights actually used: 300, 400, 500, 600, 700). Consider replacing Tailwind CDN with a bundled build. |

---

## Summary Priority Matrix

| # | Issue | Impact | Effort | Priority |
|---|-------|--------|--------|----------|
| 2.1 | No client-side pagination | HIGH | MEDIUM | 🔴 P0 |
| 3.1 | No lazy loading for images | HIGH | LOW | 🔴 P0 |
| 5.1 | No service worker / offline | HIGH | MEDIUM | � P0 |
| 5.2 | No retry for failed API calls | HIGH | LOW | 🔴 P0 |
| 1.1 | Large fetch-all payload | HIGH | MEDIUM | 🔴 P0 |
| 2.2 | fetch-all has no limits | HIGH | LOW | 🔴 P0 |
| 1.2 | No response compression | MEDIUM | LOW | 🟡 P1 |
| 3.2 | No responsive images | MEDIUM | LOW | 🟡 P1 |
| 5.3 | Aggressive no-cache headers | MEDIUM | LOW | 🟡 P1 |
| 6.1 | No PWA manifest | MEDIUM | LOW | � P1 |
| 7.1 | localStorage not used for stale-while-revalidate | MEDIUM | LOW | � P1 |
| 7.2 | No ETag/conditional requests | MEDIUM | MEDIUM | 🟡 P1 |
| 7.3 | 5 external CDN dependencies | MEDIUM | LOW | � P1 |
| 4.1 | N+1 on list_playlists change detection | MEDIUM | MEDIUM | � P1 |
| 3.3 | picsum.photos placeholder | MEDIUM | LOW | � P2 |
| 6.2 | No theme-color meta tag | LOW | LOW | ⚪ P2 |
| 4.2 | No keep-alive documentation | LOW | LOW | ⚪ P2 |

---

## Quick Wins (Low Effort, High Impact)

1. **`loading="lazy"` on all images** — single-character change per image tag
2. **Client-side fetch retry wrapper** — ~20 lines of JS, covers all API calls
3. **Add `?include_videos=false` to fetch-all** — prevents massive video payloads
4. **GZipMiddleware** — 2 lines of Python
5. **Theme-color meta tag** — 1 line per HTML page
6. **PWA manifest** — JSON file + 1 link tag per page

---

## Architecture Recommendations for Mobile

1. **Implement a BFF (Backend for Frontend) pattern** — Create mobile-specific endpoints that return only the fields needed for each view, avoiding over-fetching
2. **Add a service worker** — Even a basic one transforms the mobile experience
3. **Implement stale-while-revalidate caching** — Render from localStorage, update from network
4. **Self-host critical assets** — Remove dependency on 5+ external CDN domains
5. **Add ETag support** — 50-80% reduction in data usage for repeat visits
