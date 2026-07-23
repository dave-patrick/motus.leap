# motus.leap — CSP Strictness Plan (Remove `unsafe-inline`)

## Ground truth (verified by Neo/Gwen/Sheldon from the live repo)
- CSP emitted by one global middleware `app.py:437-462` `add_security_headers`: `script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdnjs.cloudflare.com`; `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com`.
- Pages served as static files via `no_cache_file_response` (`app.py:268-294`), already does per-response string rewriting (deploy tag + `?v=` asset busting).
- ~81 inline handlers (`onclick/onload/onchange/onsubmit`) across 8 legacy pages: settings 27 (Sheldon: 23, grep 27 — both agree it's the largest), bulk 16, subscriptions 10, maintenance 9, playlist 6, playlists 6, dashboard 4, roadmap 3.
- 11 pages load `<script src="https://cdn.tailwindcss.com">` (Play CDN — runtime JIT, needs `unsafe-inline` + `unsafe-eval`).
- Duplicate `<meta http-equiv="Content-Security-Policy">` re-allows unsafe-inline in playlist.html:11, playlists.html:11, test.html:8 (test.html also has unsafe-eval).
- `ai-hub.html` is handler-clean (0 inline handlers) but NOT Tailwind-clean — it still loads the Play CDN. So it's a valid reference for the handler→addEventListener half, NOT for the Tailwind-removal half.
- No frontend/UI tests exist for legacy pages. Backend suite has 35 P2/P3 AI tests + pre-existing isolation debt in other modules.
- Root-level `fix_csp.py` / `fix_html_csp.py` may re-inject `<meta>` CSP — must be retired/reconciled.
- `settings.html` is shared by BOTH `/settings` and `/rules` routes.

## Recommended architecture (consensus of Neo + Gwen)
1. **Tailwind:** replace Play CDN with a precompiled `/static/tailwind.css` built by the **standalone Tailwind CLI** (no Node dependency — linux-arm64 binary). `content` globs must include `web/**/*.html` AND `web/static/**/*.js` (arbitrary-value classes live in JS template literals, e.g. `bg-[#2f8fc9]`). Swap `<script src="cdn.tailwindcss.com">` → `<link href="/static/tailwind.css?v=...">` on all 11 pages.
2. **FontAwesome + Google Fonts:** keep `<link>` tags as-is. They need `style-src … fonts.googleapis.com, cdnjs.cloudflare.com` and `font-src … fonts.gstatic.com, cdnjs.cloudflare.com` (already present). Webfont FA + Google Fonts CSS need NO unsafe-inline. **No work beyond not deleting the hosts.**
3. **JS externalization:** delete all ~81 inline handlers; bind via `addEventListener` from external `web/static/<page>.js`; use **event delegation** for `innerHTML`-injected rows (maintenance.html:211-216 maintMove/maintKeep/maintRemove, bulk.html op rows). Replace inline `this` → `e.currentTarget`. Remove `window.*` exposures (mobile-nav.js).
4. **Inline `<style>` blocks:** move each page's `<style>` into the compiled CSS (or a per-page `/static/*.css`) so `style-src` needs no `unsafe-inline`.
5. **Nonce:** Gwen's finding — nonce only covers `<script>`/`<style>` ELEMENTS, NOT inline event-handler ATTRIBUTES. Since we externalize all JS and remove all handlers, a nonce becomes unnecessary. Final CSP: `script-src 'self'` (only). Sheldon counters: build the per-request nonce + per-route CSP config + fallback flag FIRST anyway, because it's the safe rollback mechanism during the transition.
6. **Meta tags:** delete the `<meta http-equiv="Content-Security-Policy">` re-allowing unsafe-inline from playlist.html, playlists.html, test.html (test.html also drop unsafe-eval).

## Phased rollout (Neo's plan, Sheldon-ordered by blast radius)
- **Phase 0 — Foundation (no behavior change):** Build static Tailwind CSS; swap Play CDN → `<link>` on all 11 pages; delete duplicate `<meta>` CSP tags; land per-request nonce + per-route CSP config + `unsafe-inline` fallback flag (env/config.json); retire `fix_csp.py`/`fix_html_csp.py`; add targeted CSP probes (`test_csp_no_unsafe_inline`, `test_page_has_nonce`, `test_no_inline_handlers`, `test_no_inline_style`). Verify: header has no unsafe-inline, Tailwind now static, pages visually identical (screenshot diff).
- **Phase 1 — ai-hub baseline:** externalize ai-hub.html `<style>` (14-32) → `web/static/ai-hub.css`; confirm 0 handlers (already). Proves the pipeline on the safest page.
- **Phase 2 — Low-risk canaries:** roadmap (3), dashboard (4), playlist (6), playlists (6). Externalize → `<page>.js` + `<page>.css`.
- **Phase 3 — Medium:** subscriptions (10), maintenance (9 — dynamic rows via delegation).
- **Phase 4 — High blast radius:** bulk (16 — destructive move/delete/tag/export), settings (27 — shared by /settings + /rules, includes logout + API-key save).
- **Phase 5 — Global lockdown:** drop `unsafe-inline` from the API/JSON CSP variant; final sweep `grep -rn "onclick|<style>|unsafe-inline" web/**/*.html` → expect 0.

## Verification per phase
- Automated: targeted probes above (header no unsafe-inline, nonce present, 0 inline handlers, 0 inline `<style>`, external JS contains addEventListener for each former handler).
- Browser: `browser_navigate` each route → `browser_console` assert ZERO "Refused to execute/apply" errors; `browser_vision` screenshot to confirm styling; exercise one action per page (tab/modal/destructive button) to confirm addEventListener fires.
- Playwright smoke: assert every destructive button bound & fires (bulk delete/move, maintenance apply, logout).
- Rollback: each phase independently revertible; Phase 5 is the point of no return — keep last, behind Dave's explicit go.

## Risk gate (Sheldon): APPROVE-WITH-CONDITIONS
- **BLOCKER 1 (CRITICAL):** ~81 inline handlers will silently die if unsafe-inline removed before 100% conversion. Convert page-by-page WITH the flag still ON, flip per page only after browser verification.
- **BLOCKER 2 (CRITICAL):** No nonce/per-route CSP exists. Build it + fallback flag BEFORE touching any inline handler.
- **BLOCKER 3 (HIGH):** ai-hub.html is NOT a Tailwind-clean baseline — correct the plan's false claim; don't model static-build migration on it.
- **HIGH risk:** Tailwind static build must capture arbitrary-value classes in BOTH html and js globs; miss = silent styling break. Diff-render-screenshot each page before/after.
- **HIGH risk:** Zero frontend tests → silent conversion failure undetectable. Need manual browser checklist + Playwright smoke.
- **SCOPE:** Keep as its OWN workstream, separate from AI Hub. Document settings.html two-route coupling.

## MoA second-tier review (hermes chat -m review --provider moa) — VERDICT: APPROVE-WITH-CONDITIONS (UPGRADED from Sheldon)
Both reference models (openrouter:nvidia/nemotron-3-super-120b:free, naga:nemotron-3-ultra-550b:free) confirmed. Sheldon's gate wins the nonce tension: build per-route CSP + fallback flag FIRST (Gwen's "nonce unnecessary at end-state" is correct for the final state, but the rollback infra must gate P0).

**Amended blockers (B1–B3 stand) + NEW blockers added by MoA:**
- **B1 (CRITICAL, amended):** Handler removal requires DUAL-RUN verification — externalize JS + add listeners WHILE keeping inline handlers present; verify destructive actions fire via externalized path (inline still as backup); only remove inline after browser confirms. Prevents silent death.
- **B2 (CRITICAL, amended):** Build per-route CSP + `CSP_STRICT` env toggle (or per-route override) for instant rollback without code deploy. Also add a CSP **violation-reporting endpoint + logging** (report-only mode) so silent breaks surface in logs, not just console.
- **B3 (HIGH):** ai-hub.html is NOT Tailwind-clean — fix the plan's false claim; include Play CDN removal in the global swap.
- **B4 (NEW):** Tailwind build must live in the **Render/Docker build step, NOT committed to repo** (standalone CLI binary should not be a committed artifact). Content globs MUST cover `web/**/*.html` + `web/static/**/*.js` or arbitrary-value classes silently break.
- **B5 (NEW):** Add CI **content-glob coverage check** — fail the build if an arbitrary-value class used in JS isn't captured (automated guard against the silent-styling-break risk).
- **B6 (NEW):** **Screenshot-diff pipeline** (staging→prod visual parity) for ALL pages, since styling regressions are silent.
- **B7 (NEW):** **Settings.html dual-route verification matrix** — because it backs BOTH `/settings` and `/rules`, define a checklist proving neither route regresses before/after.
- **V (NEW):** Automated **destructive-action verification checklist** (bulk delete/move, maintenance apply, logout) prepared in P0 for use in P1+.

**P0 GO/NO-GO: GO WITH MANDATORY SCOPE ADDITIONS.** P0 must deliver (exit criteria): CSP middleware with per-route policy + `CSP_STRICT` toggle; violation-reporting endpoint + logging; Tailwind build in Render buildCommand (not repo); CI content-glob coverage check; screenshot-diff pipeline; Play CDN removed from ai-hub.html; duplicate `<meta>` CSP tags deleted; documented+tested rollback (toggle → purge Render cache); `fix_csp.py`/`fix_html_csp.py` retired. P0 EXPLICIT NON-GOALS: no onclick/onload removal, no inline `<style>` externalization (except trivial ai-hub), no nonce generation required. No P1+ may begin until P0 infra is deployed on staging and verified zero false-positives on a canary route.

## Execution log (slow, page-by-page)
- **Chunk 1 — Foundation (DONE, committed):** Added per-route strict-CSP opt-in (`X-CSP-Mode: strict` response header) gated behind `CSP_STRICT` env (default OFF) so no page changes until it opts in. Added `POST /api/csp-report` violation-reporting endpoint (logs, 204) + report-only header when strict. Deleted duplicate `<meta http-equiv=Content-Security-Policy>` re-allowing unsafe-inline/unsafe-eval from playlist.html, playlists.html, test.html. Verified: all 9 routes 200, default CSP header unchanged (still has unsafe-inline), strict gate holds even with CSP_STRICT=1 (no route opts in -> no change), 35/35 AI suite green. Zero behavior change.
- **Page 1 roadmap.html (NEXT):** externalize JS + `<style>`, addEventListener, keep inline as backup until browser-verified, flip only after Dave confirms.

## Open questions for Dave
- Approve the P0-only scope (infrastructure + Tailwind build + meta-tag cleanup, NO handler removal yet)?  [RESOLVED: doing it slow, page-by-page; Chunk 1 = infra + meta cleanup, no handler removal yet]
- `CSP_STRICT` env toggle default OFF until all phases verified — OK?  [RESOLVED: default OFF, opted-in per route]
- Tailwind build in Render `buildCommand` (not committed binary) — OK, or want it in-repo for offline builds?  [DEFERRED to its own chunk before any page needs strict styling]
- test.html (debug page) — clean in P0 or move outside strict route?  [RESOLVED: meta tag removed in Chunk 1; test.html inherits global header]
