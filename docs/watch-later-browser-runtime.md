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
## Cookie import repair, 2026-10-12 third pass

The browser itself was already healthy after the durability fix: a live launch returned `BROWSER_OK=True`, loaded `https://www.youtube.com/playlist?list=WL` (939,174 bytes of HTML) and reported 7 cookies, but `SIGNED_IN` markers were absent and `/app/data/cookies/youtube_cookies.json` did not exist. The only remaining gap was the missing YouTube session.

Why the previous UI could not close that gap: the paste-cookies box and its `POST /api/import-yt-cookies` handler live in `server.py`, which nothing imports. The deployment runs `uvicorn app:app`, so the live service returned **404** for that route and the handler still targeted the retired Camofox service and the legacy `~/.camofox/cookies/cookies.json` store.

The fix:

- `app.py` now exposes `POST /api/import-yt-cookies` (guarded by `get_current_user` + `verify_origin`, like the other mutating routes). It parses the Netscape export, keeps YouTube/Google cookies, writes the Playwright JSON store, and mirrors a Netscape copy beside it. No Camofox dependency.
- `core/actions.get_youtube_cookies_write_path()` gives the import a deterministic target. `get_youtube_cookies_path()` returns the first store that *exists*, which would have let a stale legacy store capture the write; the write path never falls back.
- Settings → YouTube → **Browser Session (Watch Later)** gains a paste box and import button in `web/settings.html`, so a cookie export can be loaded without routing it through an assistant.

Verification: 375 tests pass, including `tests/unit/test_import_yt_cookies.py` (store written, Netscape mirror, no-Camofox success, empty and non-YouTube rejection) and three new `get_youtube_cookies_write_path()` cases.

Export cookies from a signed-in `youtube.com` tab ("Get cookies.txt LOCALLY", Netscape format) and paste them into that box. Imported cookies apply on the next browser launch.
## InnerTube rework, 2026-10-12 fourth pass

The cookie import closed the session gap, but reading and clearing Watch Later still launched headless Chromium. On a 512 MiB instance that browser is what got the run killed mid-transfer, and a browser adds nothing that the stored cookies cannot already do.

Watch Later now runs over InnerTube, the same private web API the YouTube site itself calls, using plain HTTP requests with the cookie store that already fed Playwright. Watch Later is not reachable through the public Data API, so this is the only browser-free path.

- `services/youtube_innertube.py` (new) is the whole implementation. It reads the cookie store through `core.actions.get_youtube_cookies_path()` (JSON store or Netscape export), signs requests with `SAPISIDHASH`, reads the list from browse id `VLWL` (`FEwatch_later` is rejected with 400), pages through continuations, and removes a video with `POST /youtubei/v1/browse/edit_playlist`. `remove_from_watch_later()` returns `True` only on `STATUS_SUCCEEDED`, so the confirmed-addition-before-removal rule still holds.
- `core/actions.list_videos_in_playlist()` and `remove_video_from_playlist()` try InnerTube first for a Watch Later reference. A signed-out session raises `WatchLaterSessionError` and is never retried in a browser, because that browser would be signed out in exactly the same way. Any other `InnerTubeError` falls back to the browser only when the caller supplied a `driver`; otherwise it re-raises.
- `services/watch_later_transfer.py`, `api/bulk_operations.py`, `services/watch_later_service.py`, and `app.py` no longer create or quit a browser for Watch Later. The `allow_browser` flag on `load_watch_later_videos()` keeps its name for API compatibility but no longer starts one.
- `web/maintenance.html` and `web/settings.html` no longer describe a server browser session; the copy now says the imported cookies drive signed-in Watch Later reads and clears.

Known limitations: Watch Later is served by a private API, so a YouTube change can break it; and `render.yaml` still installs Playwright Chromium at build time, which only matters for the explicitly-supplied-driver path and can be dropped later.

Verification: 20 new tests in `tests/unit/test_watch_later_innertube.py` (renderer and continuation parsing, non-video lockups skipped, the `SAPISIDHASH` signature, `STATUS_SUCCEEDED`-only confirmation, signed-out detection, and that Watch Later reads/removals start no browser), 397 tests total, all passing. Live production Watch Later membership and transfer are still not verified; the cookies installed in production are currently signed out.

## Pagination fix, 2026-10-12 fifth pass

PR #6 shipped the browser-free read, but production still returned only **100** of the **446** videos actually in Watch Later — a silent truncation that would have left 346 behind on a "move all".

Root cause: `_continuation_token()` looked only at `continuationItemRenderer.continuationEndpoint.continuationCommand.token`. YouTube now nests the token deeper, at `continuationItemRenderer.continuationEndpoint.commandExecutorCommand.commands[].continuationCommand.token`. The live read found `continuationCommand` once and no top-level `continuation` key, so the first page looked terminal and paging stopped after one page.

The pages also carry a second `continuationItemRenderer` — a "Reload for updates" popup driven by `playlistVotingRefreshPopupCommand` — which has no token. The fix walks each continuation renderer's subtree for the first real `continuationCommand.token`, which reads both the new nested shape and the older flat one while ignoring the popup.

Verification on the deployed instance: page 1 → 100, page 2 → 200, page 3 → 300, page 4 → 400, page 5 (+46) → 446, then no token, ending at the full **446**-video library. `_MAX_CONTINUATION_PAGES = 40` is ample for about five pages. The test helper in `tests/unit/test_watch_later_innertube.py` emitted the old flat shape, so the suite passed while production truncated; it now emits the nested `commandExecutorCommand.commands[]` shape, with a 446-video multi-page regression test, a popup-only-page stop test, and direct token-shape tests. 402 tests pass.

Watch Later currently uses the `playlistVideoListRenderer` / `continuationItemRenderer` family, but YouTube's newer lockup lists put the token at `continuationItemViewModel.continuationCommand.innertubeCommand.continuationCommand`, and the container's outer `continuationCommand` carries no token of its own — a live public playlist returns `continuationItemRenderer` zero times and finds nothing with a renderer-only lookup. So the token lookup now takes the first node that actually carries a token anywhere in the payload, preferring `CONTINUATION_REQUEST_TYPE_BROWSE`, which reads every container shape seen so far and still ignores the token-less popup renderer. 405 tests pass.

## Import-time session check, 2026-10-12 sixth pass

The "move Watch Later" ran, failed, and reported nothing useful: the last production
operation (`watch_later_*`) ended `status=failed`, `total_items=0` with "The stored
YouTube cookies are no longer signed in". Three attempts failed the same way before the
cause was obvious from the UI, and the failure only surfaced after the user had already
walked through the move.

Root cause: the imported export was **signed out**. A logged-out youtube.com page still
sets cookies, so the export looks like a plausible cookie file while carrying none of the
login cookies. A browser read of the same file agreed (`LOGGED_IN=false`), and so did
`yt-dlp`; the same export also failed from a residential IP, so this was never a
datacenter-IP block. The instance JSON was byte-identical to the local export, so the
import itself was faithful. The problem was upstream: the browser tab had no session.

`POST /api/import-yt-cookies` used to accept any YouTube/Google cookie file silently and
only reveal the dead session later, mid-move. It now reports the session at import time:

- `services/youtube_innertube.check_watch_later_session()` returns
  `{"signed_in": bool | None, "message": str}`. `False` means the cookies are definitely
  signed out, `True` that YouTube answered as the signed-in account, and `None` that the
  session could not be verified (a network or YouTube failure), which is neither. It
  never raises, so it can run inside the import without turning a completed write into an
  error, and it caps its own request timeout at 20s so the import stays responsive.
- `services.youtube_innertube.missing_login_cookies()` lists the login cookies a
  signed-in export always carries (`SID`, `HSID`, `SSID`, `APISID`, `SAPISID`,
  `__Secure-1PSID`, `__Secure-3PSID`, `LOGIN_INFO`). Their absence is proof the export
  came from a signed-out page, so it is reported **before** any request goes out: a
  signed-out export is caught offline.
- `app.py` still writes the cookies first (the user may be mid-flow), then annotates the
  response with `signed_in` and `warning` and folds the warning into `message`. The
  `success` / `count` / `path` contract is unchanged, so existing callers keep working.
- `static/app.js` and `web/settings.html` show a signed-out import as an amber warning
  instead of a green check, and keep the pasted text so the user can retry.

Verification: 413 tests pass (was 405). New tests cover the offline missing-cookie report
(proving no request goes out), a signed-in jar confirmed over a canned response, a
signed-out jar reported after a request, a network failure reported as `None`, and the
endpoint annotating a signed-in, a signed-out, and a partial export. Live production Watch
Later verification is still blocked on a genuinely signed-in export; the export on hand is
anonymous.
