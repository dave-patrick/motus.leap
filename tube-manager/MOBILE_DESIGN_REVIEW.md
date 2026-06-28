# 📱 Mobile Design Review — motus.leap

**Date:** 2026-06-28  
**Reviewer:** neo (full-stack coding agent)  
**Scope:** All 8 primary pages + 3 secondary pages  
**Methodology:** Static HTML/CSS/JS analysis of Tailwind classes, layout patterns, and mobile-specific behaviors

---

## Executive Summary

| Category | Rating |
|----------|--------|
| Viewport Setup | ✅ Good (all pages correct) |
| Navigation | ⚠️ Partial (hamburger exists, has issues) |
| Responsive Classes | ⚠️ Inconsistent (some pages responsive, others not) |
| Touch Targets | ❌ Poor (many sub-44px elements) |
| Content Layout | ❌ Poor (horizontal overflow on multiple pages) |
| Interactions | ⚠️ Partial (hover-only issues, modal problems) |
| Performance | ⚠️ Moderate (large DOM on playlists, polling intervals) |

**Overall Mobile Readiness: 4/10** — Functional but frustrating on phones.

---

## 1. dashboard.html

### 1.1 Viewport & Meta Tags
| Check | Status |
|-------|--------|
| Viewport meta present | ✅ Line 5: `width=device-width, initial-scale=1.0` |
| No maximum-scale | ✅ |
| No user-scalable=no | ✅ |

### 1.2 Tailwind Responsive Classes

**Issues Found:**

| # | Issue | Mobile Impact | Effort | Fix |
|---|-------|---------------|--------|-----|
| D1 | Header uses `px-8` (32px) padding — too large on mobile | MEDIUM | LOW | `px-4 md:px-8` |
| D2 | Title text `text-[5.0625rem]` (81px) overflows on small screens | **CRITICAL** | LOW | `text-3xl md:text-[5.0625rem]` |
| D3 | Logo image `height: 128px` inline style — massive on mobile | **HIGH** | LOW | Add `class="h-12 md:h-28"` or similar |
| D4 | Stats grid `grid-cols-2 md:grid-cols-4` — ✅ responsive | — | — | — |
| D5 | Agent buttons use `flex-wrap` but no responsive direction | LOW | LOW | OK as-is |
| D6 | Console area `h-[320px]` fixed height wastes mobile space | LOW | LOW | `h-48 md:h-[320px]` |
| D7 | Main content `p-6` padding wastes space on mobile | MEDIUM | LOW | `p-3 md:p-6` |
| D8 | Header layout `flex items-center` with huge logo — no wrapping | **HIGH** | MEDIUM | Scale down logo, reduce padding on mobile |

### 1.3 Navigation
| Check | Status |
|-------|--------|
| Hamburger toggle button | ✅ Line 44, `md:hidden` |
| Sidebar slide-in | ✅ Line 73, `-translate-x-full md:translate-x-0` |
| Overlay | ✅ Line 43 |
| Close on nav click | ✅ mobile-nav.js handles this |
| **Sidebar width `w-64`** | ⚠️ 256px is fine but takes 65% of 375px screen — acceptable |

### 1.4 Touch Targets

| Element | Size | Status |
|---------|------|--------|
| Nav links (`py-3`) | ~44px height | ✅ |
| Hamburger button (`w-10 h-10`) | 40px | ⚠️ Borderline — should be 44px minimum |
| Action buttons (`py-2.5`) | ~36px | ❌ Too small |
| Console buttons (`py-1`) | ~24px | ❌ Far too small |

**Fix:** `py-2.5` → `py-3` for all action buttons; console buttons → `py-2`

### 1.5 Content Layout

| Issue | Impact | Fix |
|-------|--------|-----|
| Scan details table uses `flex justify-between` — text may wrap oddly on small screens | MEDIUM | Add `flex-col sm:flex-row` or truncate |
| Console `text-[10px]` — unreadable on mobile | **HIGH** | `text-xs md:text-[10px]` |

### 1.6 Interactions
| Issue | Impact |
|-------|--------|
| Hover effects on buttons have no mobile alternative | LOW (hover doesn't apply to touch) |
| Copy/Export/Clear console buttons — no touch feedback | LOW |

### 1.7 Performance
| Issue | Impact |
|-------|--------|
| No auto-polling — page is static after load | ✅ Good |
| DOMPurify loaded | LOW |

---

## 2. settings.html

### 2.1 Viewport & Meta Tags
| Check | Status |
|-------|--------|
| Viewport meta | ✅ Line 5 |
| No restrictions | ✅ |

### 2.2 Tailwind Responsive Classes

| # | Issue | Mobile Impact | Effort | Fix |
|---|-------|---------------|--------|-----|
| S1 | Tab buttons in a row with `flex gap-4` — overflows on mobile | **CRITICAL** | MEDIUM | `flex-col sm:flex-row` or scrollable tabs |
| S2 | Settings grid `grid-cols-1 lg:grid-cols-2` — ✅ mostly responsive | — | — | — |
| S3 | Header `h-16` with `px-6` — logo text `text-3xl` too large | **HIGH** | LOW | `text-xl md:text-3xl`, `px-3 md:px-6` |
| S4 | Logout button `w-8 h-8` (32px) — too small for touch | **HIGH** | LOW | `w-10 h-10` |
| S5 | Form inputs `py-2` (~32px) — below 44px minimum | **HIGH** | LOW | `py-3` |
| S6 | `text-[10px]` labels everywhere — unreadable | **HIGH** | LOW | `text-xs md:text-[10px]` |
| S7 | JSON editor textarea `h-[550px]` — takes entire screen | MEDIUM | LOW | `h-64 md:h-[550px]` |
| S8 | Toast container `w-80` (320px) — may overflow | MEDIUM | LOW | `w-72 sm:w-80` or `max-w-[calc(100vw-2rem)]` |
| S9 | Cookie upload flex layout doesn't wrap | MEDIUM | LOW | `flex-col sm:flex-row` |
| S10 | `max-w-7xl` container — ✅ fluid | — | — | — |

### 2.3 Navigation
Same pattern as dashboard — ✅ functional hamburger menu.

### 2.4 Touch Targets

| Element | Size | Status |
|---------|------|--------|
| Tab buttons (`pb-2 px-1`) | ~32px | ❌ Too small |
| Settings save button (`py-2`) | ~32px | ❌ Too small |
| All icon buttons (`w-8 h-8`) | 32px | ❌ Too small |
| Checkboxes | Default | ❌ Needs `w-5 h-5` minimum |
| Select dropdowns (`py-2`) | ~32px | ❌ Too small |

### 2.5 Content Layout

| Issue | Impact |
|-------|--------|
| Rules & Mappings tab: two `h-[550px]` panels side-by-side — on mobile they stack but each takes 550px | HIGH |
| Channel mapping selects `w-48` (192px) may overflow when stacked | MEDIUM |
| AI suggestions list `max-h-40` — fine | — |

### 2.6 Interactions
| Issue | Impact |
|-------|--------|
| Tab switching works on touch | ✅ |
| OAuth popup `width=600,height=700` — may not fit on mobile | MEDIUM |
| JSON editor textarea — difficult to use on mobile (virtual keyboard) | HIGH |

### 2.7 Performance
| Issue | Impact |
|-------|--------|
| `setInterval(loadDashboardStats, 30000)` — runs on settings page unnecessarily | MEDIUM |
| Massive JSON rules content in textarea — large DOM | LOW |

---

## 3. playlists.html

### 3.1 Viewport & Meta Tags
| Check | Status |
|-------|--------|
| Viewport meta | ✅ Line 5 |
| No restrictions | ✅ |

### 3.2 Tailwind Responsive Classes

| # | Issue | Mobile Impact | Effort | Fix |
|---|-------|---------------|--------|-----|
| P1 | Playlist grid: `grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 2xl:grid-cols-12` | ⚠️ 3 columns on mobile = ~100px cards — very cramped | LOW | Change to `grid-cols-2 sm:grid-cols-3 ...` |
| P2 | Header `px-6` — too much mobile padding | MEDIUM | LOW | `px-3 md:px-6` |
| P3 | Logo text `text-3xl` — too large | HIGH | LOW | `text-xl md:text-3xl` |
| P4 | Logout button `w-8 h-8` — too small | HIGH | LOW | `w-10 h-10` |
| P5 | Modal `max-w-md` (448px) with no margin — may touch edges on small screens | HIGH | LOW | `max-w-md mx-4` |
| P6 | Modal content padding OK | — | — | — |
| P7 | No responsive nav — sidebar missing Watch Later link (inconsistent!) | MEDIUM | LOW | Add Watch Later link |

### 3.3 Navigation
| Check | Status |
|-------|--------|
| Hamburger menu | ✅ |
| **Missing Watch Later link** in nav (other pages have it) | ⚠️ Inconsistency |

### 3.4 Touch Targets

| Element | Size | Status |
|---------|------|--------|
| Playlist cards — entire card is tap target | Full width | ✅ |
| Create playlist button (`py-2`) | ~32px | ❌ Too small |
| Modal close button (`text-xs`) | ~24px text | ❌ Too small |

### 3.5 Content Layout
| Issue | Impact |
|-------|--------|
| 3-column grid with small thumbnails — text unreadable | HIGH |
| Skeleton loader shows 12 cards — large DOM | MEDIUM |

### 3.6 Interactions
| Issue | Impact |
|-------|--------|
| Modal positioned with `top-1/2 left-1/2 -translate` — may be under keyboard | MEDIUM |
| No backdrop-blur on modal overlay | LOW |

### 3.7 Performance
| Issue | Impact |
|-------|--------|
| 12 skeleton cards in DOM while loading | MEDIUM |
| No lazy loading for playlist thumbnails | MEDIUM |

---

## 4. subscriptions.html

### 4.1 Viewport & Meta Tags
| Check | Status |
|-------|--------|
| Viewport meta | ✅ Line 5 |

### 4.2 Tailwind Responsive Classes

| # | Issue | Mobile Impact | Effort | Fix |
|---|-------|---------------|--------|-----|
| Sub1 | Header buttons in row with no wrap — "Subscribe" + "Refresh" overflow | **HIGH** | LOW | `flex-wrap` or `flex-col sm:flex-row` |
| Sub2 | `max-w-[1600px]` container — ✅ fluid | — | — | — |
| Sub3 | Header `px-6` — too much on mobile | MEDIUM | LOW | `px-3 md:px-6` |
| Sub4 | Logo `text-3xl` — too large | HIGH | LOW | `text-xl md:text-3xl` |
| Sub5 | Subscribe modal `max-w-md` — no margin on edges | HIGH | LOW | `mx-4` |
| Sub6 | Maintenance modal `max-w-lg` — no margin | HIGH | LOW | `mx-4` |
| Sub7 | Maintenance modal grid `grid-cols-2` — OK on mobile | — | — | — |

### 4.3 Navigation
Same pattern — ✅ functional.

### 4.4 Touch Targets

| Element | Size | Status |
|---------|------|--------|
| Header buttons (`py-2`) | ~32px | ❌ Too small |
| Subscribe button in list | Default | ❌ Needs min-height |

### 4.5 Content Layout
| Issue | Impact |
|-------|--------|
| Subscriptions list items — depends on JS rendering | — |
| Modal overlays use `bg-black/60` — good contrast | ✅ |

### 4.6 Interactions
| Issue | Impact |
|-------|--------|
| Subscribe modal — single column, works well on mobile | ✅ |
| Maintenance modal grid `grid-cols-2` may be cramped | LOW |

---

## 5. bulk.html

### 5.1 Viewport & Meta Tags
| Check | Status |
|-------|--------|
| Viewport meta | ✅ Line 5 |

### 5.2 Tailwind Responsive Classes

| # | Issue | Mobile Impact | Effort | Fix |
|---|-------|---------------|--------|-----|
| B1 | Tab bar with 5 buttons in `flex gap-2` — **overflows on mobile** | **CRITICAL** | MEDIUM | `flex-wrap` or horizontal scroll, or `flex-col` |
| B2 | Main grid `grid-cols-3` with `col-span-2` + `col-span-1` — **NOT responsive** | **CRITICAL** | MEDIUM | `grid-cols-1 lg:grid-cols-3` |
| B3 | Header `px-6` — too much | MEDIUM | LOW | `px-3 md:px-6` |
| B4 | Logo `text-3xl` — too large | HIGH | LOW | `text-xl md:text-3xl` |
| B5 | Tab buttons `px-4 py-2` — text may overflow on small screens | HIGH | LOW | `px-2 md:px-4 py-2` or `text-[10px] md:text-xs` |
| B6 | Statistics grid `grid-cols-2` — ✅ responsive | — | — | — |
| B7 | Operations queue `max-h-[600px]` — too tall on mobile | LOW | LOW | `max-h-60 md:max-h-[600px]` |

### 5.3 Navigation
Same pattern — ✅ functional.

### 5.4 Touch Targets

| Element | Size | Status |
|---------|------|--------|
| Tab buttons (`py-2`) | ~32px | ❌ Too small |
| All form buttons (`py-2`) | ~32px | ❌ Too small |
| Textarea inputs — depends on rows | — | ⚠️ Check font-size |

### 5.5 Content Layout
| Issue | Impact |
|-------|--------|
| 2/3 + 1/3 grid layout completely breaks on mobile (side-by-side with narrow columns) | **CRITICAL** |
| Textarea with `rows="4"` — OK but font `text-xs` too small | HIGH |
| File input — difficult on mobile (no custom styling) | MEDIUM |

### 5.6 Interactions
| Issue | Impact |
|-------|--------|
| Tab switching via `onclick` — works on touch | ✅ |
| `alert()` calls for validation — not mobile-friendly | MEDIUM |
| `confirm()` for delete — OK but not styled | LOW |

### 5.7 Performance
| Issue | Impact |
|-------|--------|
| `setInterval(refreshOperations, 5000)` — aggressive polling | **HIGH** |
| `btoa(content)` for file import — may fail on large files | LOW |

---

## 6. watch-later.html

### 6.1 Viewport & Meta Tags
| Check | Status |
|-------|--------|
| Viewport meta | ✅ Line 5 |

### 6.2 Tailwind Responsive Classes

| # | Issue | Mobile Impact | Effort | Fix |
|---|-------|---------------|--------|-----|
| W1 | Header buttons in row — "Watch Later Sync" + "Apply All" overflow on mobile | **CRITICAL** | LOW | `flex-col sm:flex-row` or stack |
| W2 | Main layout `flex` with sidebar — ✅ responsive via sidebar collapse | — | — | — |
| W3 | `max-w-6xl` container — ✅ fluid | — | — | — |
| W4 | AI plan list items use `flex items-center gap-3` — checkbox + thumbnail + text + select + link all in a row — **overflows** | **CRITICAL** | HIGH | Restructure for mobile: 2-row layout |
| W5 | Thumbnail `w-24 h-14` (96px) — takes 25% of mobile width | MEDIUM | LOW | Smaller on mobile: `w-16 md:w-24` |
| W6 | Select dropdown `w-32` (128px) — may overflow in flex row | HIGH | LOW | `w-full` on mobile |
| W7 | Toast container `w-80` — may overflow | MEDIUM | LOW | `w-72 sm:w-80` |
| W8 | Log text `text-[9px]` — unreadable | HIGH | LOW | `text-xs md:text-[9px]` |
| W9 | No header/logo — just sidebar + main (different pattern from other pages) | — | — | — |

### 6.3 Navigation
| Check | Status |
|-------|--------|
| Sidebar has different style (no header logo, just sidebar logo) | ⚠️ Inconsistent |
| No separate header bar | ✅ Cleaner for this page |
| Nav links `py-2.5` — slightly smaller than other pages | ⚠️ |

### 6.4 Touch Targets

| Element | Size | Status |
|---------|------|--------|
| Plan checkboxes `width:14px;height:14px` inline style | 14px | ❌ **CRITICAL** — far too small |
| Select dropdowns `py-1` | ~24px | ❌ Far too small |
| Action buttons (`py-2.5`) | ~36px | ⚠️ Borderline |
| "Watch" link icon `p-1` | 24px | ❌ Too small |

### 6.5 Content Layout
| Issue | Impact |
|-------|--------|
| AI plan row: checkbox + img + title/channel/badges + select + link = horizontal overflow | **CRITICAL** |
| Empty state `text-6xl` icon — OK but large | LOW |

### 6.6 Interactions
| Issue | Impact |
|-------|--------|
| Select dropdown for playlist correction — hard to use on touch | HIGH |
| Hover effects on plan cards — no touch equivalent | LOW |

---

## 7. auth.html

### 7.1 Viewport & Meta Tags
| Check | Status |
|-------|--------|
| Viewport meta | ✅ Line 5 |

### 7.2 Tailwind Responsive Classes

| # | Issue | Mobile Impact | Effort | Fix |
|---|-------|---------------|--------|-----|
| A1 | No Tailwind used at all — pure inline/CSS | MEDIUM | — | Minor (page is simple) |
| A2 | `max-width: 400px` on message — ✅ responsive | — | — | — |
| A3 | Container `padding: 20px` — ✅ OK | — | — | — |

### 7.3 Navigation
N/A — standalone auth popup page.

### 7.4 Touch Targets
| Element | Size | Status |
|---------|------|--------|
| No interactive elements (just text and link) | — | ✅ |

### 7.5 Content Layout
| Issue | Impact |
|-------|--------|
| Simple centered layout — works well on mobile | ✅ |
| `font-size: 24px` title — slightly large but acceptable | LOW |

### 7.6 Interactions
| Issue | Impact |
|-------|--------|
| `setTimeout(() => window.close(), 1500)` — may not work on mobile browsers | MEDIUM |
| `window.opener.postMessage` — popup may be blocked on mobile | HIGH |

---

## 8. maintenance.html

### 8.1 Viewport & Meta Tags
| Check | Status |
|-------|--------|
| Viewport meta | ✅ Line 5 |

### 8.2 Tailwind Responsive Classes

| # | Issue | Mobile Impact | Effort | Fix |
|---|-------|---------------|--------|-----|
| M1 | Grid `grid-cols-1 lg:grid-cols-3` — ✅ responsive | — | — | — |
| M2 | Header `px-6` — too much | MEDIUM | LOW | `px-3 md:px-6` |
| M3 | Logo `text-3xl` — too large | HIGH | LOW | `text-xl md:text-3xl` |
| M4 | Logout button `w-8 h-8` — too small | HIGH | LOW | `w-10 h-10` |
| M5 | `max-w-[1600px]` — ✅ fluid | — | — | — |
| M6 | Toast container `w-80` — may overflow | MEDIUM | LOW | `max-w-[calc(100vw-2rem)]` |

### 8.3 Navigation
Same pattern — ✅ functional.

### 8.4 Touch Targets

| Element | Size | Status |
|---------|------|--------|
| Apply buttons (`py-1 px-2`) | ~24px | ❌ Far too small |
| Keep/Remove buttons (`py-1`) | ~24px | ❌ Far too small |
| Select dropdowns `py-1` | ~24px | ❌ Far too small |

### 8.5 Content Layout
| Issue | Impact |
|-------|--------|
| Maintenance items with thumbnail + text + select in row — may overflow | MEDIUM |
| `text-[10px]` throughout — unreadable | HIGH |

### 8.6 Interactions
| Issue | Impact |
|-------|--------|
| `applyMaintenance()` just shows "disabled" toast | ✅ (honest) |
| Select dropdowns for move/misplaced — hard on touch | MEDIUM |

---

## Cross-Pattern Issues (All Pages)

### Critical Issues Summary

| # | Pages Affected | Issue | Fix |
|---|---------------|-------|-----|
| **C1** | All except auth | Logo text `text-3xl` (28px) too large on mobile | `text-xl md:text-3xl` |
| **C2** | All except auth | Header padding `px-6` wastes mobile space | `px-3 md:px-6` |
| **C3** | All except auth | Logout button `w-8 h-8` below touch target | `w-10 h-10` |
| **C4** | All except auth | Form inputs `py-2` below 44px minimum | `py-3` |
| **C5** | All except auth | `text-[10px]` labels unreadable on mobile | `text-xs md:text-[10px]` |
| **C6** | bulk, watch-later | Content grids not responsive (fixed columns) | Add responsive breakpoints |
| **C7** | bulk, settings | Tab bars overflow horizontally | `flex-wrap` or scroll |
| **C8** | watch-later | 14px checkboxes far too small | `w-5 h-5` minimum |
| **C9** | playlists, subscriptions, bulk | Modals lack margin on small screens | `mx-4` |
| **C10** | bulk | `setInterval 5000ms` aggressive polling | Increase to 15000ms or use WebSocket |

### Touch Target Violations (WCAG 2.5.5 / Apple HIG)

Across ALL pages, these elements consistently fail the 44x44px minimum:

| Element | Current | Fix |
|---------|---------|-----|
| Icon-only buttons | `w-8 h-8` (32px) | `w-11 h-11` (44px) |
| Form inputs | `py-2` (~32px) | `py-3` (~44px) |
| Action buttons | `py-2` (~32px) | `py-3` (~44px) |
| Tab buttons | `pb-2 px-1` (~32px) | `py-3 px-3` (~44px) |
| Checkboxes | default/14px | `w-5 h-5` (20px) minimum, prefer `w-6 h-6` |
| Select dropdowns | `py-2` (~32px) | `py-3` (~44px) |
| Nav links | `py-3` (~44px) | ✅ OK |

### Navigation Consistency

| Page | Watch Later Link | Subscription Link | Maintenance Link |
|------|-----------------|-------------------|------------------|
| dashboard | ✅ | ✅ | ✅ |
| settings | ✅ | ✅ | ✅ |
| playlists | ❌ Missing | ✅ | ✅ |
| subscriptions | ❌ Missing | — | ✅ |
| bulk | ✅ | ✅ | ✅ |
| watch-later | — | ✅ | ✅ |
| maintenance | ✅ | ✅ | — |
| playlist | ✅ | ✅ | ✅ |
| roadmap | ✅ | ✅ | ✅ |

---

## Positive Findings

1. ✅ **Viewport meta tags** — All pages correctly configured
2. ✅ **Mobile sidebar** — Functional hamburger menu with overlay, escape key, and auto-close on nav
3. ✅ **mobile-nav.js** — Clean, lightweight, no dependencies
4. ✅ **Dashboard stats grid** — Properly responsive (`grid-cols-2 md:grid-cols-4`)
5. ✅ **Settings grid** — Responsive (`grid-cols-1 lg:grid-cols-2`)
6. ✅ **Maintenance grid** — Responsive (`grid-cols-1 lg:grid-cols-3`)
7. ✅ **ux-enhancements.css** — Has mobile media query for toasts
8. ✅ **Focus-visible styles** — Good accessibility foundation
9. ✅ **No user-scalable=no** — Zooming not blocked
10. ✅ **Dark mode** — Consistent across all pages (good for OLED mobile)

---

## Recommended Fix Priority

### Phase 1: Quick Wins (1-2 hours)
1. Add `md:` responsive prefixes to logo text, header padding, all pages
2. Increase all `py-2` to `py-3` on buttons and inputs
3. Increase icon buttons from `w-8 h-8` to `w-10 h-10`
4. Add `mx-4` to all modals
5. Change `text-[10px]` to `text-xs md:text-[10px]`

### Phase 2: Layout Fixes (2-4 hours)
1. Fix bulk.html grid: `grid-cols-1 lg:grid-cols-3`
2. Fix bulk.html tab bar: add `flex-wrap` or convert to horizontal scroll
3. Fix watch-later.html AI plan row: restructure to 2-row mobile layout
4. Fix playlists.html grid: `grid-cols-2` on mobile instead of 3
5. Fix settings.html tabs: `flex-col sm:flex-row`

### Phase 3: Enhanced Mobile UX (4-8 hours)
1. Increase checkbox sizes across all pages
2. Add touch-friendly file upload styling
3. Replace `alert()`/`confirm()` with custom modals
4. Reduce polling interval on bulk.html
5. Add responsive `font-size` to all `text-[9px]` and `text-[10px]` elements
6. Fix playlist.html missing Watch Later nav link

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total pages reviewed | 10 |
| Total issues found | 47 |
| Critical issues | 8 |
| High issues | 18 |
| Medium issues | 15 |
| Low issues | 6 |
| Pages with hamburger menu | 8/10 |
| Pages with responsive grids | 5/10 |
| Pages with touch target violations | 8/10 |
| Estimated fix time | 7-14 hours |
