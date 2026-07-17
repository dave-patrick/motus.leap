# motus.leap — TODO

Source of truth for active work. Roadmap page (`web/roadmap.html`) should mirror this list.

## Now / In Progress
- CSP Phase 0: per-route strict-CSP opt-in, `/api/csp-report` endpoint, retire `fix_csp.py`/`fix_html_csp.py`, delete duplicate `<meta>` CSP tags.
- Resolve open High/Medium/Low backlog from `bug_register.md`: H1 export 500, H2 config save reset behavior, H6 unsubscribe 404, H7 stale client ref.
- Roadmap UX: make roadmap a reliable tracker linked from Settings.

## Next
- H2/M4/M5/M6 backend hardening: config save/merge semantics, single-flight/cache correctness.
- H3/H4/H5/H7 frontend auth/path fixes still open in code: verify deployed fixes remain stable through UI shell work.
- Low/CSP canaries: roadmap.html, dashboard.html, playlist.html, playlists.html inline handler removal + external JS/CSS conversion.

## Planned
- Remove Tailwind Play CDN; add static build step.
- Remove `unsafe-inline` globally after page-by-page externalization is complete.
- Advanced analytics + multi-user support.
