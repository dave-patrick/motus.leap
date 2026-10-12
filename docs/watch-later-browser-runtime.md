# Watch Later browser runtime repair — 2026-10-12

Production logs showed Playwright installed without Chromium binaries. The fallback then encountered a leaked sync Playwright runtime. Installed Chromium on the live Render instance and verified a real headless launch (BROWSER_LAUNCH_OK). Copied binaries to /app/data/ms-playwright and set PLAYWRIGHT_BROWSERS_PATH through Render; that triggered deployment dep-db6gh3qd0e5s73alvh3g.

Pin Playwright to 1.63.0 to match these binaries. Future version upgrades require installing matching browser binaries. Clean up failed contexts and runtimes before retry. Browser profiles default to the persistent data directory when configured.

Google OAuth app login does not create a signed-in YouTube browser session. No exported cookie file was present during the read-only production check. Live Watch Later membership and transfer are not yet verified; no transfer was executed for validation. Always confirm destination membership/addition before source removal.

Post-deployment verification: Render deploy dep-db6gh3qd0e5s73alvh3g is live. The new instance printed BROWSER_CACHE /app/data/ms-playwright and BROWSER_LAUNCH_OK_AFTER_DEPLOY; /health returned HTTP 200. Nine focused browser-cleanup and transfer-safety tests passed. Cleanup code remains in PR #5 until merged.

