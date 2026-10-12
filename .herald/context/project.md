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
- Shared mobile shell rules live in `web/static/shared-shell.js`: compact branding, document scrolling, stacked responsive toolbars and in-flow footer. Queue-specific rules remain scoped to maintenance.
- `web/static/ui-polish.js` supplies dialog focus/Escape behavior and library/schedule controls while preserving original form values and action safeguards. Programmatic ID/cron assignments must dispatch change/input events to keep displayed and submitted values synchronized.
- Android welcome uses a text wordmark and a centered, width-bounded column that adapts to the actual inset/window width. Keep Google sign-in artwork and browser OAuth behavior intact.
- Preserve existing project instructions, configuration, credentials, and application data.
- Use Graft for code context when available, following the global and project Graft guidance.
- Keep this context accurate as project architecture and conventions are established.
- Herald compiler output replaces vendor files. Preserve and merge existing guidance before compiling.
