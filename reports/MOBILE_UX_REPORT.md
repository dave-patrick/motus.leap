# Mobile-Specific UX Review — motus.leap

**Reviewer:** jnu (lightweight coder)  
**Date:** 2026-06-28  
**Scope:** `/opt/data/motus.leap/tube-manager/web/` — all frontend HTML, JS, and CSS

---

## Executive Summary

The motus.leap frontend has a reasonable baseline mobile experience — viewport meta tag is present, a mobile sidebar nav exists, skeleton loaders are used, and responsive grid classes are applied. However, there are **15 concrete mobile-specific issues** ranging from touch-unfriendly interactions to missing network-aware patterns. 5 are HIGH impact.

---

## 1. Touch Interactions

### Issue 1.1: SPA Router Intercepts ALL Clicks Including Touch
| Attribute | Value |
|-----------|-------|
| **Impact** | 🔴 HIGH |
| **Effort** | 🟡 MEDIUM |
| **File** | `web/static/ux-enhancements.js` lines 900–928 |

**Problem:** The SPA router registers a `click` event listener in capture phase on `document`. On mobile, `click` events fire ~300ms after touch (no delay with `touch-action: manipulation`, but none is set). More critically, the interceptor walks up the DOM looking for `[onclick]` attributes containing `window.location.href=`, which catches any element — including video checkboxes, dropdowns, and buttons that should natively perform their function. The `e.preventDefault()` + `e.stopPropagation()` can interfere with touch-driven native behaviors.

**Fix:**
```js
// Add touch-action: manipulation to eliminate 300ms delay
// In CSS: button, a, [onclick] { touch-action: manipulation; }

// In the click interceptor, exclude interactive elements:
if (e.target.closest('input, select, textarea, [role="button"]')) return;
```

---

### Issue 1.2: Playlist Grid Cards Use `onclick` with No Touch Feedback
| Attribute | Value |
|-----------|-------|
| **Impact** | 🟡 MEDIUM |
| **Effort** | 🟢 LOW |
| **File** | `web/static/playlists.js` line 78 |

**Problem:** Playlist cards use inline `onclick="window.location.href=..."` with no `touch-action: manipulation` and no `:active` CSS state. On mobile, users see no visual feedback when tapping a card — it just sits there for 300ms before navigating.

**Fix:** Add to CSS:
```css
.bento-card[onclick] { 
  cursor: pointer; 
  touch-action: manipulation; 
  -webkit-tap-highlight-color: rgba(47, 143, 201, 0.3);
}
.bento-card[onclick]:active { 
  transform: scale(0.98); 
  opacity: 0.9; 
}
```

---

### Issue 1.3: Hover States Are Primary Feedback Mechanism
| Attribute | Value |
|-----------|-------|
| **Impact** | 🟡 MEDIUM |
| **Effort** | 🟢 LOW |
| **Files** | Multiple CSS files |

**Problem:** Throughout the CSS, `:hover` is the primary (sometimes only) state for indicating interactivity:
- `.nav-item:not(.active):hover { background-color: #2a2f3a; }`
- `.bento-card:hover { border-color: ... }`
- `.video-row:hover { background-color: #20242c; }`

On mobile, `:hover` either doesn't fire or fires erratically (sticky hover on iOS Safari). Users get no feedback that an element is tappable.

**Fix:** Replace or supplement `:hover` with `:active` and `:focus-visible`:
```css
.nav-item:active, .nav-item:focus-visible { background-color: #2a2f3a; }
.bento-card:active { border-color: #2a7db8; }
```

---

### Issue 1.4: Subscription Mapping Input Is Tiny on Mobile
| Attribute | Value |
|-----------|-------|
| **Impact** | 🔴 HIGH |
| **Effort** | 🟢 LOW |
| **File** | `web/static/subscriptions.js` line 81 |

**Problem:** The playlist mapping input in subscriptions uses `class="... w-28"` (112px wide). On a 375px-wide phone, with the channel thumbnail and name taking space, this input is extremely cramped. The "Map" button at `px-3 py-1.5` is also below the recommended 44×44px touch target.

**Fix:**
```html
<!-- Change w-28 to w-full on mobile, or at minimum w-36 -->
<input type="text" class="... w-36 sm:w-28 ...">
<!-- Ensure buttons meet 44px minimum touch target -->
<button class="... min-h-[44px] ...">Map</button>
```

---

## 2. JavaScript Performance

### Issue 2.1: Multiple Competing `setInterval` Pollers
| Attribute | Value |
|-----------|-------|
| **Impact** | 🔴 HIGH |
| **Effort** | 🟡 MEDIUM |
| **Files** | `ux-enhancements.js`, `settings.html`, `bulk.html` |

**Problem:** On some pages, multiple independent `setInterval` timers run simultaneously:
- `ux-enhancements.js`: `pollStats()` every 30s (line 792)
- `ux-enhancements.js`: `startProgress()` every 1s (line 714)
- `settings.html`: `loadDashboardStats()` every 30s (line 980)
- `bulk.html`: `refreshOperations()` every 5s (line 449)

On mobile CPUs (especially mid-range Android), this means 4+ active timers doing DOM manipulation and fetch calls simultaneously. This drains battery and causes jank during scrolling.

**Fix:** Consolidate into a single page-scoped polling manager that uses `visibilitychange` to pause and batches all status requests into one endpoint.

---

### Issue 2.2: WebSocket Reconnection Has No Backoff or Network Awareness
| Attribute | Value |
|-----------|-------|
| **Impact** | 🟡 MEDIUM |
| **Effort** | 🟡 MEDIUM |
| **Files** | `dashboard.js` line 99, `ux-enhancements.js` line 1081 |

**Problem:** Both WebSocket connections use a fixed `setTimeout(reconnect, 3000)` or `5000` with no exponential backoff. On mobile, when a user switches from WiFi to cellular, the connection drops and the fixed delay doesn't account for the time the radio takes to re-establish. There's no `navigator.onLine` listener.

**Fix:**
```js
let reconnectDelay = 3000;
ws.onclose = () => {
  clearInterval(pingInterval);
  reconnectDelay = Math.min(reconnectDelay * 2, 30000); // exponential backoff
  setTimeout(connectWS, reconnectDelay);
};
ws.onopen = () => {
  reconnectDelay = 3000; // reset on success
  // ...
};

// Listen for network recovery
window.addEventListener('online', () => {
  if (ws.readyState !== WebSocket.OPEN) connectWS();
});
```

---

### Issue 2.3: SPA Router Re-Dispatches DOMContentLoaded Causing Duplicate Init
| Attribute | Value |
|-----------|-------|
| **Impact** | 🟡 MEDIUM |
| **Effort** | 🟢 LOW |
| **File** | `web/static/ux-enhancements.js` lines 889–891 |

**Problem:** After SPA navigation, the router fires `DOMContentLoaded` manually via `setTimeout(() => document.dispatchEvent(new Event('DOMContentLoaded')), 50)`. Many page scripts check `document.readyState === 'loading'` and if false, call init directly. This means on SPA navigation, some scripts run twice — once from the inline script execution and once from the re-dispatched event, creating duplicate event listeners and interval timers.

**Fix:** Use a custom event name (e.g., `'spa-navigate-complete'`) instead of re-dispatching `DOMContentLoaded`.

---

## 3. Input Experience

### Issue 3.1: No Input Type Optimization for Mobile Keyboards
| Attribute | Value |
|-----------|-------|
| **Impact** | 🟡 MEDIUM |
| **Effort** | 🟢 LOW |
| **Files** | `subscriptions.html`, `settings.html`, `playlists.html` |

**Problem:** Several inputs that would benefit from specialized mobile keyboards use generic `type="text"`:
- Channel ID input in `subscriptions.html` (line 71): `type="text"` — should use `type="text"` with `inputmode="url"` and `autocomplete="off"` since it's a URL/ID
- Playlist title inputs: Could benefit from `autocomplete="off"` and `enterkeyhint="done"`
- The search inputs in `ux-enhancements.js` (line 554): `input[type="search"]` is correct but missing `enterkeyhint="search"`

**Fix:**
```html
<input type="text" inputmode="url" autocomplete="off" 
       placeholder="UCxxxx... or channel link"
       enterkeyhint="go">
```

---

### Issue 3.2: Modals Don't Handle On-Screen Keyboard
| Attribute | Value |
|-----------|-------|
| **Impact** | 🟡 MEDIUM |
| **Effort** | 🟡 MEDIUM |
| **Files** | `playlists.html`, `subscriptions.html`, `bulk.html` |

**Problem:** All modals use `position: fixed` with `top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2` centering. When the on-screen keyboard opens on mobile, it covers the modal entirely. Inputs at the bottom of modals become invisible. There's no scroll-into-view behavior on focus.

**Fix:**
```css
@media (max-width: 768px) {
  .modal-content {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    transform: none;
    max-height: 80vh;
    overflow-y: auto;
    border-radius: 12px 12px 0 0;
  }
}
```
```js
// Scroll input into view on focus
input.addEventListener('focus', () => {
  setTimeout(() => input.scrollIntoView({block: 'center'}), 300);
});
```

---

### Issue 3.3: `prompt()` and `alert()` Usage on Mobile
| Attribute | Value |
|-----------|-------|
| **Impact** | 🟢 LOW |
| **Effort** | 🟡 MEDIUM |
| **Files** | `playlists.js`, `subscriptions.js` |

**Problem:** Multiple actions use `prompt()` and `alert()`:
- `playlists.js` line 195: `prompt('Rename Playlist - Enter new title:', currentTitle)`
- `playlists.js` line 220: `prompt('Duplicate Playlist - Enter name for duplicate:', ...)`
- `subscriptions.js` line 150: `prompt("Channel ID or URL:")`

On mobile, `prompt()` shows a native dialog that's jarring, can't be styled, and breaks the app-like feel. It also blocks the main thread.

**Fix:** Replace with inline modal forms using the existing modal pattern.

---

## 4. Scrolling Performance

### Issue 4.1: No Virtual Scrolling for Long Video Lists
| Attribute | Value |
|-----------|-------|
| **Impact** | 🟡 MEDIUM |
| **Effort** | 🔴 HIGH |
| **File** | `web/static/playlist.js` lines 132–160 |

**Problem:** `renderVideos()` renders ALL videos in a playlist as a single HTML string. For playlists with 100+ videos (common on YouTube), this creates hundreds of DOM nodes with images, causing scroll jank on mid-range mobile devices. The `videos-container` has no virtualization.

**Fix:** Implement a simple windowed renderer that only renders visible items plus a buffer, using `IntersectionObserver` or a scroll-position-based approach. Libraries like `vue-virtual-scroller` or a lightweight custom solution would work.

---

### Issue 4.2: Playlist Grid Has Too Many Columns on Mobile
| Attribute | Value |
|-----------|-------|
| **Impact** | 🟢 LOW |
| **Effort** | 🟢 LOW |
| **File** | `web/playlists.html` line 57 |

**Problem:** The playlist grid uses `grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 2xl:grid-cols-12`. At 320px viewport width with 3 columns, each card is ~90px wide — too small to read thumbnails or titles comfortably.

**Fix:** Change to `grid-cols-1 sm:grid-cols-2 md:grid-cols-3 ...` for better mobile readability.

---

## 5. Gesture Support

### Issue 5.1: No Pull-to-Refresh
| Attribute | Value |
|-----------|-------|
| **Impact** | 🟡 MEDIUM |
| **Effort** | 🟡 MEDIUM |
| **Scope** | All data-displaying pages |

**Problem:** On mobile, users expect to pull down to refresh data. Currently, the only way to refresh is tapping a button. The SPA router's `fetch()` + DOM replacement also breaks the native browser pull-to-refresh behavior.

**Fix:** Implement a touch-based pull-to-refresh using `touchstart`/`touchend` on the main content area, or at minimum add a visible "Pull to refresh" hint.

---

### Issue 5.2: No Swipe-to-Delete or Swipe Actions on List Items
| Attribute | Value |
|-----------|-------|
| **Impact** | 🟢 LOW |
| **Effort** | 🟡 MEDIUM |
| **File** | `web/static/playlist.js` |

**Problem:** Video rows in playlists require checkbox selection + bulk action. On mobile, swipe-to-delete or swipe-to-move would be more ergonomic than tiny checkboxes.

**Fix:** Consider adding swipe gesture handlers to video rows, or at minimum increase checkbox touch targets to 44×44px.

---

## 6. Network-Aware Features

### Issue 6.1: No Retry Mechanism for Failed Fetches
| Attribute | Value |
|-----------|-------|
| **Impact** | 🔴 HIGH |
| **Effort** | 🟡 MEDIUM |
| **Files** | `subscriptions.js`, `playlists.js`, `playlist.js` |

**Problem:** All fetch calls use simple `try/catch` with a toast notification but no retry. On mobile, transient network failures are extremely common (tunneling through elevators, switching networks, carrier NAT timeouts). The user sees "Network error" with no way to retry except pulling down to reload the entire page.

**Fix:** Add a retry wrapper:
```js
async function fetchWithRetry(url, options = {}, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const resp = await fetch(url, options);
      if (resp.ok || resp.status === 401 || resp.status === 403) return resp;
      if (i === maxRetries - 1) return resp;
    } catch (e) {
      if (i === maxRetries - 1) throw e;
      await new Promise(r => setTimeout(r, 1000 * (i + 1)));
    }
  }
}
```

---

### Issue 6.2: No Offline State or Service Worker
| Attribute | Value |
|-----------|-------|
| **Impact** | 🟡 MEDIUM |
| **Effort** | 🔴 HIGH |
| **Scope** | Application-wide |

**Problem:** There's no service worker, no offline fallback, and no `navigator.onLine` listener. When a user loses connection, the app shows cryptic WebSocket errors and failed fetch messages with no indication that the network is the issue vs. a server error.

**Fix:** At minimum, add a network status banner. Ideally, register a service worker for static asset caching.

---

## 7. Mobile Browser Quirks

### Issue 7.1: No Safe Area Insets (iOS Notch/Home Indicator)
| Attribute | Value |
|-----------|-------|
| **Impact** | 🔴 HIGH |
| **Effort** | 🟢 LOW |
| **Scope** | All HTML pages |

**Problem:** The fixed sidebar (`position: fixed; inset-y-0; left-0`), the fixed agent drawer (`position: fixed; bottom-0`), and the fixed toast container (`position: fixed; top-4`) do NOT respect iOS safe area insets. On iPhones with notch/Dynamic Island:
- The sidebar toggle button is hidden behind the status bar
- The agent drawer is partially hidden behind the home indicator
- Toast notifications overlap the status bar

**Fix:** Add `env(safe-area-inset-*)` padding:
```css
#sidebar-toggle { top: max(0.75rem, env(safe-area-inset-top)); }
#mobile-sidebar { padding-top: env(safe-area-inset-top); padding-bottom: env(safe-area-inset-bottom); }
#global-agent-drawer { bottom: env(safe-area-inset-bottom, 0); }
#toast-container { top: max(1rem, env(safe-area-inset-top)); }
```

---

### Issue 7.2: `100vh` Issue on Mobile Browsers
| Attribute | Value |
|-----------|-------|
| **Impact** | 🟡 MEDIUM |
| **Effort** | 🟢 LOW |
| **File** | `web/auth.html` line 10 |

**Problem:** `auth.html` uses `min-height: 100vh` for the centered container. On mobile browsers (iOS Safari, Chrome Android), `100vh` includes the browser's address bar height, causing the content to be slightly scrollable or the bottom to be hidden behind the browser UI.

**Fix:** Use `min-height: 100dvh` (dynamic viewport height) or `min-height: -webkit-fill-available` as fallback:
```css
.container { min-height: 100vh; min-height: 100dvh; }
```

---

### Issue 7.3: Body Scroll Lock Without Scroll Chain Prevention
| Attribute | Value |
|-----------|-------|
| **Impact** | 🟡 MEDIUM |
| **Effort** | 🟢 LOW |
| **File** | `web/static/mobile-nav.js` |

**Problem:** When the mobile sidebar opens, `document.body.style.overflow = 'hidden'` is set. However, on iOS Safari, this alone doesn't prevent scroll chaining — the page still scrolls when reaching the top/bottom of the sidebar. Also, there's no `overscroll-behavior: contain` on the sidebar itself.

**Fix:**
```css
#mobile-sidebar { overscroll-behavior: contain; }
body.sidebar-open { 
  overflow: hidden; 
  position: fixed; 
  width: 100%; 
  top: var(--scroll-y); 
}
```

---

### Issue 7.4: No `-webkit-tap-highlight-color` Set
| Attribute | Value |
|-----------|-------|
| **Impact** | 🟢 LOW |
| **Effort** | 🟢 LOW |
| **Scope** | Global |

**Problem:** On iOS Safari, all tapable elements show a default gray highlight. The app's dark theme makes this highlight very jarring.

**Fix:**
```css
* { -webkit-tap-highlight-color: rgba(47, 143, 201, 0.2); }
```

---

## Summary Table

| # | Issue | Impact | Effort | Category |
|---|-------|--------|--------|----------|
| 1.1 | SPA router intercepts all clicks | HIGH | MEDIUM | Touch |
| 1.2 | No touch feedback on cards | MEDIUM | LOW | Touch |
| 1.3 | Hover-only states | MEDIUM | LOW | Touch |
| 1.4 | Tiny subscription input | HIGH | LOW | Touch |
| 2.1 | Multiple competing intervals | HIGH | MEDIUM | Performance |
| 2.2 | No WS backoff/network awareness | MEDIUM | MEDIUM | Performance |
| 2.3 | Duplicate DOMContentLoaded dispatch | MEDIUM | LOW | Performance |
| 3.1 | No inputmode/enterkeyhint | MEDIUM | LOW | Input |
| 3.2 | Modals hidden by keyboard | MEDIUM | MEDIUM | Input |
| 3.3 | Native prompt()/alert() | LOW | MEDIUM | Input |
| 4.1 | No virtual scrolling | MEDIUM | HIGH | Scrolling |
| 4.2 | Too many grid columns on mobile | LOW | LOW | Scrolling |
| 5.1 | No pull-to-refresh | MEDIUM | MEDIUM | Gestures |
| 5.2 | No swipe actions | LOW | MEDIUM | Gestures |
| 6.1 | No fetch retry mechanism | HIGH | MEDIUM | Network |
| 6.2 | No offline handling | MEDIUM | HIGH | Network |
| 7.1 | No safe area insets | HIGH | LOW | Browser Quirk |
| 7.2 | 100vh mobile browser bug | MEDIUM | LOW | Browser Quirk |
| 7.3 | Scroll chain not prevented | MEDIUM | LOW | Browser Quirk |
| 7.4 | Default tap highlight | LOW | LOW | Browser Quirk |

---

## Priority Recommendations (Quick Wins)

1. **Safe area insets** (7.1) — 5 minutes, huge iOS improvement
2. **Touch-action + active states** (1.2, 1.3) — 10 minutes
3. **100dvh fix** (7.2) — 2 minutes
4. **Tiny input fix** (1.4) — 2 minutes
5. **Fetch retry wrapper** (6.1) — 15 minutes
6. **WebSocket backoff + online listener** (2.2) — 15 minutes
7. **Consolidate polling intervals** (2.1) — 30 minutes
8. **Modal keyboard handling** (3.2) — 30 minutes
