# motus.leap — Shared Shell + Defect Remediation Plan

## Chosen approach
**JS-injected shared shell**, not Jinja/base.html routing.

Rationale:
- Current serving path serves static HTML through `app.py:no_cache_file_response(...)` and there is no template_folder/jinja wiring today.
- Introducing Flask `render_template` for all 9 pages would broaden scope into backend routes; JS injection still gives ONE source of truth with less risk.
- SPA `navigateSPA` replaces body content; mount points + injected shell keep the shell intact across full-page swaps and SPA navigation.

Files:
- `web/static/shared-shell.js` — single-source shell injector.
- `web/templates/base.html` — human-readable canonical shell markup (template literal source for maintainers; not served by Flask).
- 9 page HTML files — add mount point divs and load `shared-shell.js`.
- `web/static/ux-enhancements.js` — remove agent-status pill and any AI Chat Console auto-render.
- `web/ai-hub.html` — remove AI Chat Console panel and info banner.
- `web/maintenance.html` — add `/bulk` CTA.
- `web/settings.html` — add `/roadmap` link, restructure Advanced/Diagnostics into one box, standalone Sign Out, add Storage & Data section.

## Preserved SPA invariant
`web/static/ux-enhancements.js` around `navigateSPA` must keep this exact sequence intact:

```text
scriptsToRun.push(s); s.remove(); document.body.appendChild(child)
```

Current lines kept: `ux-enhancements.js:861-864`.

## Change map

### 1. Shared shell source + injector
- Add `web/templates/base.html` with canonical header/sidebar/footer markup only.
- Add `web/static/shared-shell.js`:
  - injects header into `#shell-header`, sidebar into `#shell-nav`, footer into `#shell-footer`
  - uses `textContent`/`DOMPurify.sanitize` where dynamic values are inserted
  - updates active nav class from `location.pathname`
  - idempotent init + re-init hook after SPA swaps

### 2. Convert pages to shell mount points
For each page file, replace the duplicated local header/sidebar/footer with:
```html
<div id="shell-header"></div>
<div id="mobile-overlay" ...></div>
<button id="sidebar-toggle" ...></button>
<div id="shell-nav"></div>
<div class="flex flex-1 ...">
  <main> ... page content unchanged ... </main>
</div>
<div id="shell-footer"></div>
<script src="/static/shared-shell.js?v=<deploy_tag>"></script>
```
Pages:
- `web/dashboard.html`
- `web/bulk.html`
- `web/ai-hub.html`
- `web/playlist.html`
- `web/playlists.html`
- `web/subscriptions.html`
- `web/maintenance.html`
- `web/roadmap.html`
- `web/settings.html`

### 3. Remove agent-status pill entirely
- `web/static/ux-enhancements.js:967-993` — remove `initGlobalAgentDrawer()` function body or replace with no-op so pill creation/anchor logic is gone.
- `web/static/ux-enhancements.js:1319` — remove `DOMContentLoaded` listener for `initGlobalAgentDrawer`.

### 4. Remove AI Chat Console floating panel on AI pages
- `web/ai-hub.html` — remove the entire pinned console block starting at `<div class="h-[20vh] ...">` around line 199 through line 213.
- Keep the robot-button chat drawer logic untouched; only delete the auto-rendered floating panel.

### 5. Remove AI Hub info banner
- `web/ai-hub.html:89-95` — delete the info banner block containing `Global classification prompt & auto-apply are managed in Settings → AI Integration` and `Go to Settings →`.

### 6. Header font/alignment fixes embedded in shared shell
- Shared header includes `justify-between`.
- `.site-title { font-family: 'Deltha', serif; }` remains in shared CSS.
- Per spec: `u` stays cyan via shared markup.

### 7. Bulk link
- `web/maintenance.html` — add `<a href="/bulk" class="...">Bulk Operations</a>` CTA inside the main content area, near the page title.

### 8. Roadmap link in Settings
- `web/settings.html` — add an in-page link to `/roadmap` inside content, near General box or as a settings nav card.

### 9. Settings restructure
- `web/settings.html`:
  - Remove **Clear Thumbnail Cache** button from Advanced (`settings.html:217`).
  - Merge Diagnostics box and Advanced box into one card, preserving:
    - View System Logs
    - Debug/reset actions from Advanced (minus cleared-thumbnail)
    - Keep red `Reset All Settings`
  - Move **Sign Out** outside the combined box as standalone button.
  - Add **Storage & Data** section with `Clear All Data` action.
  - Keep existing Storage box content and diagnostics.

### 10. Footer
- Shared footer becomes single pinned minimal footer in shell.
- Remove per-page footer markup from converted pages.

## Deliverables checklist
- Branch `feature/shared-shell`, local commits only.
- `PLAN.md` with file:line references.
- `grep "agent-status-pill" web/ == 0`
- `grep "AI Chat Console" web/ == 0`
- `grep "Global classification prompt" web/ == 0`
- `navigateSPA` still contains `scriptsToRun.push(s); document.body.appendChild(child)`
- `node --check` on every edited JS file.
- `git log origin/main..HEAD` empty.
