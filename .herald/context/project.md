# motus.leap: project context

## Overview
Software project in motus.leap. See existing project documentation for its purpose.

## Existing guidance
- Read `AGENTS.md` for existing project guidance; follow directory-specific instructions where present.
- Read `CLAUDE.md` for existing project guidance; follow directory-specific instructions where present.
- Read `README.md` for existing project guidance; follow directory-specific instructions where present.

## Stack evidence
- `package.json` is present; use it to confirm dependencies and supported commands.
- `pyproject.toml` is present; use it to confirm dependencies and supported commands.
- `requirements.txt` is present; use it to confirm dependencies and supported commands.

## Conventions
- Both CSP modes allow framing only by the arnés Control Center origins (local port 9130, GB5 Tailscale HTTPS, and the private hosted Hub). CSP frame-ancestors replaces X-Frame-Options so nested cross-origin framing works.
- Embedded Google login opens a popup. The callback dashboard sends its token only to the motus.leap opener origin; the frame checks sender identity and validates the token before saving it in its own storage, supporting partitioned browser storage.
- Shared mobile shell rules live in `web/static/shared-shell.js`: compact branding, document scrolling, stacked responsive toolbars and in-flow footer. Queue-specific rules remain scoped to maintenance.
- `web/static/ui-polish.js` supplies dialog focus/Escape behavior and library/schedule controls while preserving original form values and action safeguards. Programmatic ID/cron assignments must dispatch change/input events to keep displayed and submitted values synchronized.
- Android branding uses the existing transparent symbol and Deltha lettering; preserve both and the official Google sign-in artwork.
- Watch Later to 1~Sort is an explicit confirmed background operation. Browser creation, live collection and removal stay on one worker thread; source removal follows confirmed target membership/addition, never precedes it. No shared snapshot is used for selecting source videos.
- Preserve existing project instructions, configuration, credentials, and application data.
- Use Graft for code context when available, following the global and project Graft guidance.
- Keep this context accurate as project architecture and conventions are established.
- Herald compiler output replaces vendor files. Preserve and merge existing guidance before compiling.

- Android 0.5.0 starts at Dashboard (stats, activity, quota, scan actions). The user-supplied unframed artwork is android/app/src/main/res/drawable-nodpi/brand_symbol.png.
- Render browser repair: Playwright 1.63.0 is pinned to installed Chromium binaries. PLAYWRIGHT_BROWSERS_PATH=/app/data/ms-playwright persists them; failed startup closes context and stops Playwright before fallback. Watch Later still requires an authenticated browser profile, separate from app OAuth.


- Public landing/help source is site/; GitHub Pages publishes it independently of app hosting. See documentation/PUBLISHING.md. Preserve app branding, screenshots and existing build/device limitations.
