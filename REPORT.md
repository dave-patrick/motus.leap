# Code Scan Report for motus.leap (tube-manager)

## Security Vulnerabilities

1. **Potential XSS via innerHTML**
   - Files: `dashboard.html`, `playlists.html`, `playlist.html`
   - User-controlled data (playlist titles, video titles, channel names) is inserted into the DOM via `innerHTML` or template literals without sanitization in several places.
   - Mitigation: Use `textContent` where possible, or sanitize with DOMPurify (already imported) before setting `innerHTML`.

2. **Token Storage Vulnerabilities**
   - Auth tokens are stored in `localStorage` and a non-HttpOnly cookie (` SameSite=Lax` but accessible via JavaScript).
   - If an XSS attack occurs, tokens can be stolen.
   - Mitigation: Consider using HttpOnly, Secure cookies for tokens and avoid storing tokens in localStorage.

3. **Missing CSRF Protection**
   - State-changing endpoints (e.g., `/api/action`, bulk operations) rely solely on Bearer token in `Authorization` header (from localStorage). While this mitigates CSRF if the token is not automatically sent by the browser, the application also uses cookies for authentication (see cookie set on login). If both are used, CSRF protection is needed.
   - Mitigation: Implement double-submit cookie or require a custom header (e.g., `X-CSRF-Token`) for mutating endpoints.

4. **Unrestricted File Upload**
   - Settings page allows uploading YouTube cookies JSON file; no validation of file type beyond extension `.json` and no size limit.
   - Mitigation: Validate file size, content structure, and sanitize filename.

5. **Information Exposure in Error Messages**
   - Some API endpoints may return internal error details (e.g., stack traces) to the client, potentially leaking sensitive information.
   - Mitigation: Ensure error responses are generic in production; log details server-side.

6. **Insecure Direct Object References (IDOR)**
   - Bulk operation endpoints accept `playlist_id` and `video_id` parameters without verifying ownership against the authenticated user.
   - Mitigation: Add authorization checks ensuring the user owns the resource.

## Performance Bottlenecks

1. **Excessive Polling**
   - Dashboard polls `/api/stats` every 30 seconds via `setInterval`.
   - Each playlist page also polls for stats and activity.
   - Mitigation: Use WebSocket for real-time updates or increase interval; consider conditional polling only when user is active.

2. **Redundant API Calls**
   - After each action (e.g., rescan, move), the app reloads entire playlists or videos list, causing duplicate requests.
   - Mitigation: Update UI optimistically and only fetch changed data; use caching strategies.

3. **Inefficient YouTube Data Fetching**
   - Subscription and playlist fetching is done page-by-page sequentially; each page requires a separate HTTP request.
   - Mitigation: Use `maxResults=50` (already) but consider parallelizing page requests or using batch endpoints if available.

4. **Client-Side Duplicate Detection O(n)**
   - Actually O(n) with hashmap, acceptable. However, for large playlists (>10k videos) it may cause UI freeze.
   - Mitigation: Offload heavy computations to Web Workers.

5. **Lack of Video Data Caching**
   - Video metadata (title, thumbnail, duration) is fetched per playlist view and not cached beyond the session.
   - Mitigation: Cache video data in IndexedDB or localStorage with TTL.

6. **Multiple WebSocket Connections**
   - Each page opens a WebSocket to `/ws/terminal`; duplicates can accumulate.
   - Mitigation: Reuse a single connection or close when not needed.

## UX Elements Review

1. **Header Status Indicators**
   - The header includes a hidden `#app-status` paragraph that shows `🟢 READY` or `🟡 RUNNING`. The user prefers minimal headers with only brand title/icon.
   - The status is also duplicated in the system activity box.
   - Recommendation: Remove header status per user preference; keep activity box if needed.

2. **Unused / Dead UI**
   - The scan detail panel (`#scan-detail-panel`) is present but may be rarely used; the toggle function exists but no obvious trigger.
   - The "Additional Module Placeholder" bento card is empty.
   - Recommendation: Remove or collapse unused UI to reduce clutter.

3. **Modal Overlays**
   - Multiple modals (login, settings, playlist manage) are created via JavaScript and appended to body; ensure they trap focus and are accessible (aria-modal).
   - No visible focus trap implementation.

4. **Toast Notification Duplication**
   - Toast function is copy-pasted across HTML files; leads to code bloat.
   - Recommendation: Centralize toast logic in a shared JavaScript module (`ux-enhancements.js`).

5. **Animation Overhead**
   - CSS animations (ambient-glow, gradient-shift) run continuously and may cause GPU load on low-end devices.
   - Provide option to disable animations or reduce motion.

6. **Accessibility**
   - Buttons relying solely on icons lack accessible labels (e.g., the eye toggle for secrets has `title` but no aria-label).
   - Ensure all interactive elements have discernible names.

7. **Responsive Design**
   - The layout uses fixed `min-w-[1200px]` containers; may cause horizontal scroll on narrow screens.
   - Consider fluid layouts or breakpoints.

## Recommendations Summary

- **Security**: Sanitize innerHTML, improve token storage, add CSRF checks, validate uploads, enforce authorization.
- **Performance**: Reduce polling, deduplicate API calls, cache video data, consider Web Workers for heavy JS.
- **UX**: Remove unused UI per user preference, centralize shared code, improve accessibility, respect reduced motion, make layout responsive.
