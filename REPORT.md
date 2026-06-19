
# Comprehensive Scan Report: motus.leap

This report details the findings from a comprehensive scan of the `motus.leap` codebase, focusing on Performance, UX, and Security. It includes enhancements made during the current session and outlines further recommendations.

## I. Performance Enhancements

### Completed during this session:
*   **Watch Later Caching:** Implemented `_watch_later_cache_ttl` and `youtube_service.list_watch_later_items_cached` with a shorter TTL (15 minutes) for the Watch Later feature to reduce repeated API calls and improve responsiveness.
*   **Asynchronous File I/O:** Refactored `_load_users`, `_save_users` in `api/auth.py` and `ConfigManager` methods (`load`, `save`, `config` property) to use `asyncio.to_thread` with `aiofiles`, preventing blocking of the event loop and improving overall application responsiveness.
*   **HTTP Client Reuse:** Implemented a shared `httpx.AsyncClient` for YouTube API calls (`refresh_oauth_token`, `_oauth_request`) and ensured all calls are awaited, resolving `malloc(): unsorted double linked list corrupted` and `SSL: DECRYPTION_FAILED_OR_BAD_RECORD_MAC` errors by ensuring thread-safe asynchronous HTTP operations and efficient connection management.

### Further Recommendations:
*   **Generalized Caching Strategy:**
    *   **Finding:** While specific caching for Watch Later is implemented, a more generalized caching mechanism (e.g., `functools.lru_cache` or a custom decorator for API endpoints) could be beneficial across other `youtube_service` methods that fetch frequently accessed, less dynamic data (e.g., `list_playlists`, `list_subscriptions`).
    *   **Recommendation:** Implement a `@cached(ttl=...)` decorator for `YouTubeService` methods to centralize and control caching, reducing redundant API calls and improving response times for frequently requested data. This would be preferable to manual caching in each method.
*   **Database/File I/O Optimization (Review):**
    *   **Finding:** File I/O operations in `api/auth.py` and `ConfigManager` are now asynchronous.
    *   **Recommendation:** Review `services/ai_classifier.py` and any other modules that perform file I/O to ensure `asyncio.to_thread` or `aiofiles` is consistently used for non-blocking operations.
*   **Frontend Data Fetching Optimization:**
    *   **Finding:** The dashboard polls `loadDashboardStats` every 30 seconds. Individual playlist/video data fetching on `/playlists` and `/playlist/{id}` should be efficient.
    *   **Recommendation:** For the `/playlists` page, ensure the API endpoint (`/api/playlists` or `api_playlist_names`) is optimized to return only essential metadata for the grid view, avoiding fetching full video details until a specific playlist is selected.

## II. UX Enhancements

### Completed during this session:
*   **Playlist Grid Density:** Increased playlist grid column density on `web/playlists.html` to reduce tile size by 1/3, improving information density and user overview.
*   **Unified Scan Box:** Relocated the rescan button, added a unified scan box with filter controls, and replaced `scanForDuplicates()` with a `performFullScan()` function in `web/playlist.html`, streamlining playlist operations.
*   **Centralized Frontend Logout/Refresh:** Removed inline script for token refresh and logout logic from `dashboard.html`, moving it to external JavaScript files (`dashboard.js`, `global_scripts.js`, `auth-check.js`) for better maintainability and code organization. Updated logout button handler.
*   **Header Logout Button:** Standardized the logout button to call `logoutUser()` in `web/playlists.html` for consistency.

### Further Recommendations:
*   **Loading Indicators and Skeleton States:**
    *   **Finding:** The UI often displays "Loading..." or "No data yet." While functional, more visually appealing skeleton loaders or progress bars could enhance the perceived performance and user experience during data fetching.
    *   **Recommendation:** Implement skeleton loading states (e.g., gray shimmer placeholders) for grids and lists (playlists, videos) to provide immediate visual feedback while data is loading.
*   **Enhanced Error Handling and User Feedback (Frontend):**
    *   **Finding:** The `toast` function is used for success/error messages, but some error messages (`Failed to load playlists`, `API error`) are generic.
    *   **Recommendation:** Enhance error messages to be more specific and actionable for the user. For instance, if an API call fails due to network issues, suggest checking the internet connection. If due to authentication, prompt re-login.
*   **Comprehensive Empty States:**
    *   **Finding:** "No playlists found. Create one to get started." is a good empty state message. Ensure similar helpful messages exist for other empty data states (e.g., empty Watch Later, empty scan results).
    *   **Recommendation:** Review all pages for their empty states and ensure they provide clear instructions or suggestions to the user.
*   **Accessibility Audit:**
    *   **Finding:** The `Content-Security-Policy` is strict. Image `alt` attributes are generally present.
    *   **Recommendation:** Perform a light accessibility audit, focusing on keyboard navigation, screen reader compatibility, and sufficient color contrast, especially for interactive elements and text.
*   **Responsive Layout Review (`min-w` usage):**
    *   **Finding:** `min-w-[1200px]` is used in `dashboard.html` and `playlists.html`, which forces a minimum width and can lead to horizontal scrolling on smaller screens.
    *   **Recommendation:** Re-evaluate the use of `min-w` to allow for better responsiveness across various screen sizes. Consider using responsive grid classes (e.g., `grid-cols-1 md:grid-cols-2 lg:grid-cols-3`) with appropriate `max-w` containers instead.

## III. Security Enhancements

### Completed during this session:
*   **Enforce `TUBE_MANAGER_SECRET_KEY`:** Modified `api/auth.py` to remove fallback logic and raise a `RuntimeError` if `TUBE_MANAGER_SECRET_KEY` is not explicitly set as an environment variable, ensuring stable user sessions in production.
*   **Protect `/api/auth/security/status` Endpoint:** Restricted access to `/api/auth/security/status` to authenticated administrators only by adding `dependencies=[Depends(check_role([RoleEnum.ADMIN]))]`, preventing unauthorized exposure of security configuration.
*   **CSRF Protection for Sensitive Endpoints:** Implemented `Depends(verify_origin)` to all sensitive POST/PUT/DELETE API endpoints in `app.py` (e.g., `/api/mappings`, `/api/action/cancel`, `/api/youtube/disconnect`, `/api/ai/classify`, `/api/settings/reset`, `/api/cookies/save`, `/api/storage/clear-thumbnails`, `/api/webhook/test`) to mitigate Cross-Site Request Forgery attacks.
*   **Rate Limiting on Registration:** Applied `@limiter.limit("5/minute")` to the `/api/auth/register` endpoint in `api/auth.py` to prevent brute-force attacks and abuse.

### Further Recommendations:
*   **Environment Variable Best Practices (Review):**
    *   **Finding:** `TUBE_MANAGER_SECRET_KEY` is enforced.
    *   **Recommendation:** Add a `check_env_vars()` function in a central place (e.g., `core/config_manager.py` or app startup) to verify the presence of *all* critical environment variables (including YouTube API keys, OAuth client secrets) and provide clear error messages if they are missing. Ensure no sensitive values are ever hardcoded.
*   **Comprehensive Input Validation (Backend & Frontend):**
    *   **Finding:** Pydantic models provide good backend validation. `DOMPurify.sanitize` is used in `playlist.js`.
    *   **Recommendation:** Conduct a systematic review of all points where user-generated content is displayed on the frontend and ensure `DOMPurify.sanitize()` or equivalent is consistently applied. Also, consider stricter backend validation (e.g., using `Field(min_length=..., max_length=..., regex=...)` in Pydantic models) for string lengths and allowed characters for *all* user-input fields.
*   **Secure Logging Practices:**
    *   **Finding:** Logging for `_save_users` errors is present.
    *   **Recommendation:** Implement a logging filter or thoroughly review all `log.info`/`log.warning`/`log.error` calls to ensure that sensitive information (passwords, tokens, API keys, PII) is never inadvertently written to logs, especially in production environments.
*   **Dependency Vulnerability Scanning:**
    *   **Finding:** No explicit dependency vulnerability scanning is noted in the workflow.
    *   **Recommendation:** Integrate a dependency scanning tool (e.g., `pip-audit`, Snyk, Dependabot) into the CI/CD pipeline to automatically detect and alert on known vulnerabilities in third-party libraries.
*   **Authentication Token Management (Advanced):**
    *   **Finding:** Access tokens have a 7-day expiry. Refresh tokens are not explicitly used, relying on a refresh endpoint to issue new access tokens.
    *   **Recommendation:** Consider implementing a robust refresh token mechanism for longer-lived sessions, where refresh tokens are separate, long-lived, and stored securely (e.g., HTTP-only cookies), while access tokens remain short-lived. This improves security by limiting the exposure window of access tokens.

This concludes the comprehensive re-scan and recommendations.
