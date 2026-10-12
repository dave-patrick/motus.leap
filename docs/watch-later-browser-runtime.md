# Watch Later browser runtime repair — 2026-10-12

Production logs showed Playwright installed without Chromium binaries. The fallback then encountered a leaked sync Playwright runtime. Installed Chromium on the live Render instance and verified a real headless launch (BROWSER_LAUNCH_OK). Copied binaries to /app/data/ms-playwright and set PLAYWRIGHT_BROWSERS_PATH through Render; that triggered deployment dep-db6gh3qd0e5s73alvh3g.

Pin Playwright to 1.63.0 to match these binaries. Future version upgrades require installing matching browser binaries. Clean up failed contexts and runtimes before retry. Browser profiles default to the persistent data directory when configured.

Google OAuth app login does not create a signed-in YouTube browser session. No exported cookie file was present during the read-only production check. Live Watch Later membership and transfer are not yet verified; no transfer was executed for validation. Always confirm destination membership/addition before source removal.

Post-deployment verification: Render deploy dep-db6gh3qd0e5s73alvh3g is live. The new instance printed BROWSER_CACHE /app/data/ms-playwright and BROWSER_LAUNCH_OK_AFTER_DEPLOY; /health returned HTTP 200. Nine focused browser-cleanup and transfer-safety tests passed. Cleanup code remains in PR #5 until merged.

## Durability fix, 2026-10-12 second pass

Chromium was restored on the live instance, but the binaries were gone at the next check: `/app/data/ms-playwright` did not exist and `pw.chromium.launch()` failed with `Executable doesn't exist at /app/data/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell`. Manual copies into the disk do not survive a service or disk recreation.

The fix moves the install into the build: the service build runs the Playwright install with `PLAYWRIGHT_BROWSERS_PATH=/app/data/ms-playwright`, and `render.yaml` now declares `TUBE_MANAGER_DATA_DIR=/app/data`.

`core/actions.py` resolves the cookie store through `get_youtube_cookies_path()`, which checks `YOUTUBE_COOKIES_FILE`, then `$TUBE_MANAGER_DATA_DIR/cookies/youtube_cookies.json`, then `/app/data/cookies/youtube_cookies.json`, then the legacy `~/.camofox/cookies/cookies.json`, so an imported session survives redeploys.

Chrome 127 and later use app-bound encryption, so the local Chrome cookie database cannot be decrypted offline even while Chrome is closed. Cookies must be exported from inside Chrome.

Verified after restoring the binaries: `LAUNCH_OK`; the Watch Later page loads, `SIGNED_IN=False`, `ROWS=0`. The server browser still has no YouTube session.