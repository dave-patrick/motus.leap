# Neo — Delegation Log (motus.leap)

George (the butler agent) delegates **ALL** coding to the subagent **Neo** (skill `neo-coding-agent`). This ledger records every task sent and what Neo returned, for Dave's oversight.

**Rules:**
- Each entry = **Dispatch** (brief sent to Neo) + **Outcome** (Neo's report).
- Nothing is committed or pushed without Dave's explicit approval.
- Neo has `web_search`; for UI/UX tasks he is also briefed with the `ui-design` skill.

---

## [SETUP] 2026-07-09 — Neo established
- Created skill `neo-coding-agent` (expert-coder standing orders; web_search enabled; TDD/verify-before-done; never commit/push/deploy).
- `ui-design` skill already governs Neo's visual work (Dave's locked-in dark bento system).
- Created this ledger.
- Verified bug register (all findings confirmed by George against source): 5 Critical, 7 High, 8 Medium, 4 Low, 4 UI/UX.

---

## [NEO-001] 2026-07-09 — Fix sync failure: `stats` NameError (C3) + single-subscription (C4)
- **Bugs:** C3 `services/youtube_service.py:820-821` undefined `stats` → `NameError` during `sync_playlists`; C4 `subscriptions.append` + enrichment sit outside the per-subscription loop → only 1 subscription ever cached, stale `cid`.
- **Brief sent to Neo:** repo path + venv; exact lines; required fix (use `channel_stats.get(cid, {})`; move append/enrichment inside `for sub in all_subs:`; add/adjust pytest proving multiple subs returned; run `python -m pytest tests/unit/ -q` from repo root; NO commit/push; return structured summary).
- **Status:** ✅ COMPLETE (verified by George).
- **Neo's report:**
  - *Files changed:* `services/youtube_service.py` (lines ~810-837), `tests/unit/test_youtube_service.py` (+`test_fetch_all_data_multiple_subscriptions`).
  - *Root cause confirmed:* C3 undefined `stats` → NameError swallowed → "Failed to fetch subscriptions"; C4 `append` ran once outside loop → ≤1 sub.
  - *Fix:* wrapped enrichment + `append` in `for sub in all_subs:`; `stats = channel_stats.get(cid, {})`. Mirrored in-repo `list_subscriptions` pattern.
  - *Tests:* 36 passed (35 existing + 1 new). **George re-ran & confirmed green.**
  - *Caveats:* none. No commit/push (per standing orders).
- **George's independent verify:** viewed fixed block (812-837) — correct loop, no stray `stats.` ref; `grep` confirms only `channel_stats.get(cid, {})` usage; 36 tests pass.
- **Committed & DEPLOYED:** commit `0e35a02`, pushed to main → Render deploy. Logged in `updates/commits/` + `updates/deployments/`.

---

## [NEO-002] 2026-07-09 — Fix unauthenticated bulk router (C1)
- **Bug:** `api/bulk_operations.py:24` router has no `Depends(get_current_user)`; `app.py:251` includes it bare → `/api/bulk/*` move/delete/tag/import + op-history unauthenticated (CRITICAL security hole).
- **Brief sent to Neo:** secure router with same auth dependency as rest of app; import `get_current_user` from its source module (avoid circular import); add pytest asserting 401 without token / 200 with; run `python -m pytest tests/unit/ -q` + new security test; NO commit/push.
- **Status:** ✅ COMPLETE (verified by George).
- **Neo's report:** Added `from api.auth import get_current_user, verify_origin`; set `dependencies=[Depends(get_current_user), Depends(verify_origin)]` on the `APIRouter(...)`. New `tests/security/test_bulk_auth.py` (8 tests). Root cause confirmed by reading `api/bulk_operations.py:24` + `app.py:251`.
- **George's independent verify:** grep confirms import + deps applied; **47 tests passed** (36 unit + 8 security) at first run; **78 passed** in combined run with C2. No circular import (auth helpers live in `api/auth.py`, imports only core.limiter/fastapi/passlib).
- **Caveat:** working tree also had NEO-003's half-done C2 edits at the same time — distinct files, no conflict. Will commit C1 + C2 together on Dave's approval.
- **Not yet committed.**

## [NEO-003] 2026-07-09 — Fix scan infinite-loop (C2)
- **Bug:** `background_worker.py` `full_cluster_scan` outer playlist-pagination loop and inner per-playlist video loop share `page_token` var → page 1 re-fetched forever for >50 playlists (Dave has 61). Corrupts counts.
- **Brief sent to Neo:** rename to `playlist_page_token` (outer) / `video_page_token` (inner); pure variable fix, no restructure; add pytest with 2-page mock + `asyncio.wait_for(timeout=10)` to fail fast on regression; run `python -m pytest tests/unit/ -q`; NO commit/push.
- **Status:** ✅ COMPLETE (verified by George).
- **Neo's report:** Renamed `page_token`→`playlist_page_token` (outer) / `video_page_token` (inner). New `tests/unit/test_background_worker_scan.py` (3 tests: advances past page 1 / single page / inner loop doesn't clobber outer token). Reported 39 passed.
- **George's independent verify:** grep confirms `playlist_page_token` (lines 273,287) + `video_page_token` (314,329) present, no shared `page_token`. **78 tests pass** combined. Test patches `app.youtube_service` (test-only; documented by Neo).
- **Committed & DEPLOYED:** commit `87b0e20`, pushed to main → Render deploy. Logged in `updates/commits/` + `updates/deployments/`.

---

## [NEO-005] 2026-07-09 — Backend non-AI batch (H1,L1,L2,M3,H2,H6,H7,M1,M2,M4,M5,M6)
- **Bugs:** H1 export 500; L1 cache KeyError; L2 export leaks oauth; M3 GET mutates config; H2 config save can't clear; H6 unsubscribe 404; H7 stale client after reset; M1 open self-registration; M2 *.onrender.com CSRF; M4 lock bypass; M5 misplaced field mismatch; M6 LRU evict bug.
- **Brief sent to Neo:** read-before-change; surgical fix each; add pytest per bug; run `python -m pytest tests/unit/ -q`; backend only (H6 may touch subscriptions.js minimally); do NOT touch AI or frontend; NO commit/push.
- **Status:** ✅ COMPLETE (George finished the final-5 directly — Neo's re-dispatch did NOT report back / was not running; see below).
- **George's direct completion (2026-07-10, deleg context lost):** Neo's re-dispatch (deleg_142575be) never returned and no process was alive (verified by process-list + file mtimes). George applied the remaining items himself:
  - **M4** ✅ `services/youtube_service.py`: replaced `asyncio.Lock()` `_data_lock` with a new `_ReentrantAsyncLock` (defined in-file). Plain asyncio.Lock would DEADLOCK because `get_basic_stats()` holds `_data_lock` while calling `list_subscriptions()`/`list_playlists()` (confirmed by reading call graph: get_basic_stats line 276→292; get_videos line 994→list_playlists). Reentrant lock gives single-flight without self-deadlock.
  - **M6** ✅ `core/lru_cache.py`: `set()` now assigns `access_count=1` and evicts with `exclude=<just-set key>`; `_maybe_evict` takes `exclude`. New entry no longer evicted immediately at capacity.
  - **M5** ⚠️ INVESTIGATED — NOT a bug (like U1). Wrote tests proving `scan_misplaced` flags a video owned by a non-mapped channel and ignores correctly-placed ones; both PASS with NO code change. Scan uses `videoOwnerChannelId` (bw:363); `scan_misplaced` reads `channel_id` from `get_videos`, which derives `channel_id` from `videoOwnerChannelId` (ys:264) — consistent. No edit made.
  - **Tests** ✅ created `tests/unit/test_backend_fixes_batch.py` (6 tests: M4 reentrant+single-flight, M5 misplaced flag/ignore, M6 eviction order x2). 
  - **George's independent verify:** `python -m pytest tests/unit/ -q` → **45 passed** (was 39; +6, nothing broken). M4/M6 verified in tree; M5 verified-consistent by test.
- **CORRECTION (verified 2026-07-10, Sheldon review + direct diff read):** M1 + M2 WERE delivered in-tree by Neo's earlier batch (api/auth.py + models/config.py), NOT open as George's interim note stated. Verified by `git diff api/auth.py`: (M1) `/register` now raises 403 unless `config.allow_self_registration` is true (default false); (M2) `verify_origin` no longer blanket-allows `*.onrender.com` — only declared `ALLOWED_ORIGINS` + `config.allowed_origins` + `FRONTEND_URL` trusted, referer host-matched. George's earlier "OPEN" note was stale (predated reading api/auth.py). Corrected.
- **M4 rationale note:** Sheldon flagged the stated deadlock premise is technically inaccurate (list_* do not acquire _data_lock in current call graph, so the OLD asyncio.Lock would not have self-deadlocked). The reentrant lock is SAFE and correct (true single-flight across distinct tasks); George will soften the code comment to "defensive reentrancy guarantee" to avoid a fictional justification.
- **Test file:** `tests/unit/test_backend_fixes_batch.py` (committed in batch).

## [POST-DEPLOY] 2026-07-10 — sync_playlists returned 0 playlists (INVESTIGATED, NOT a code regression)
- **Symptom:** after deploy, dashboard "Scan" showed 479 duplicates (STALE cached per-playlist data from a much earlier successful run), but the "sync_playlists" agent command returned "API returned 0 playlists / 0 subscriptions" with NO 403/exception.
- **Diagnosis (verified by reading code, NOT by guessing):** `sync_playlists` → `fetch_all_data(force_refresh=True)` bypasses ALL caches (background_worker.py:542; youtube_service.py:774 `if not force_refresh`), so the 0 result was a LIVE 200-with-empty-`items` from `playlists?mine=true`. My M4/M6 batch did NOT change `fetch_all_data` logic (git diff vs 87b0e20 proved equivalence). `_oauth_request` calls `raise_for_status()` + JSON-parse (youtube_client.py:269-271), so a 200-empty is a truthful API response, not a parse bug. **Conclusion: OAuth token/account state, not application code.**
- **Fix applied (code, palliative):** commit `95d241f` — `background_worker.py` now shows a clear re-auth hint when `mine` returns 0 with no error (previously only 403 triggered guidance).
- **Root cause + resolution:** user RE-AUTHORIZED YouTube in Settings. Code resets cached client on re-auth (`api/auth.py:1132 app_youtube_service._client = None`), so new token took effect. Re-run sync → **"Successfully synchronized 61 playlists, 9287 videos, 465 subscriptions."** ✅ RESOLVED.
- **Lesson (honesty):** a 200-with-0-`mine` result after deploy is almost always a stale/invalid OAuth token, NOT a regression. The scan's "479 forever" was misleading cached data — never trust a cached count as proof the live API works.

## [INVESTIGATION] 2026-07-10 — why the card said "479" but live scan said "24 duplicates / 10 groups"
- **Surface:** after re-auth, `scan_duplicates` (agent command) reported 24 extra copies / 10 groups; the Scan Details card (pre-fix) showed 479 from stale maintenance.json. Fixed card-staleness in `8597fb1` (persist live scan → maintenance.json, MERGE not clobber, full-scan only).
- **Deeper cause found (REAL BUG, distinct from staleness):** `fetch_all_data` TRUNCATES the synced video set — youtube_service.py:944-945 `max_playlists = 50 if force_refresh else 10`, `max_total_videos = 2000 if force_refresh else 500`; and youtube_service.py:980 `playlists[:max_playlists]` + :991 `if len(videos) >= max_total_videos: break`.
  - Library = **61 playlists, 9,287 videos**. A sync fetches only the first 10 (or 50) playlists and stops at 500 (or 2000) videos. `get_videos(playlist_id=None)` → `fetch_all_data()` therefore returns a PARTIAL library; the live `scan_duplicates` fingerprint-matches only that partial set → undercounts (24 vs the cluster scan's 479 on the FULL library).
  - The background **cluster scan** (`full_cluster_scan`, background_worker.py:316-329) paginates EVERY playlist fully with NO cap → it sees all 9,287 videos → 479 duplicates is the CORRECT count; 24 was an undercount caused by the sync cap.
- **Consequence:** the dashboard duplicate scan (and anything reading the synced "all_data" video cache) only examines a fraction of the library. Masked earlier by the token outage; now exposed.
- **Fix not yet applied (needs user sign-off):** raise/remove the caps to cover the full library SAFELY — keep the existing Semaphore(1) sequential fetch (heap-safe on Render), set e.g. `max_playlists = 200` and `max_total_videos = 12000`. Do NOT silently remove quota guards. This changes sync runtime/quota, so George will get explicit approval before shipping (candidate for MoA break-glass if it regresses on Render).

## [JNU-001] 2026-07-09 — First archival audit (Duty 1)
- **Brief sent to Jnu:** inventory tree; backfill missing commit/deploy records (esp. predates-ledger commits like `4c6fb0d`); refresh memory mirror; check ledger completeness; scan sessions for gold.
- **Status:** ✅ COMPLETE (verified by George).
- **Jnu's findings:** all expected tree nodes exist; **18 commit records backfilled** (git had 20 SHAs, only 87b0e20+0e35a02 were logged) → all 20 now reconcile; memory mirror refreshed; delegation ledger complete; no session gold missed.
- **George's independent verify:** `ls commits/*.md` = 20; diff against `git log -20` = no missing; memory mirror file present + current.
- **Caveat (Jnu):** git author = "Dave Patrick"; logged faithfully, attribution nuance flagged (our convention credits code to Neo/George — noted, not rewritten).
- **Schedule:** nightly audit set via cron `0 8 * * *` UTC = 1am Arizona/MST (job 739cf6f03f33).
- **Bugs/items:** H3 settings targetSelect undefined; H4 dashboard loadDashboardStats undefined; H5 agent-drawer WS no token; M7/U3 broken thumbnails; L3 DOMPurify gap; L4 dead CSRF header; U2 "479 issues" banner; U1 timezone (INVESTIGATE — George suspected false alarm).
- **Brief sent to Arwin:** follow `ui-design` skill; HTML/CSS/JS only, no backend .py; verify U1 before "fixing"; CSP+DOMPurify discipline; run pytest green; NO commit/push.
- **Status:** ✅ COMPLETE (verified by George).
- **Arwin's deliverables:** `web/settings.html` (H3 `targetSelect` declared line 394; L4 dead X-CSRF header removed); `web/static/dashboard.js` (H4 `loadDashboardStats()` defined line 74; U2 banner → "N duplicates · M misplaced"); `web/static/ux-enhancements.js` (H5 WS now sends `?token=` line 1043); `web/static/playlist.js` (M7/U3 misplaced thumb from `v.video_id` ytimg line 346); `web/static/subscriptions.js` (L3 `c.title` sanitized line 45).
- **U1 finding (Arwin, confirmed by George):** NOT a bug — backend stores UTC ISO with `+00:00` offset, so `new Date().toLocaleTimeString()` localizes correctly. No change made. Good that we didn't ship a needless fix.
- **George's independent verify:** grep confirms each fix; **39 tests pass** (suite green, front-end changes didn't break backend tests).
- **Caveats:** Arwin notes M7 relies on `v.video_id` being present in misplaced payload (it is). Pure front-end; no backend touched.
- **Not yet committed.**

## Remaining after these batches
- C5 (AI classifier) — DEFERRED per Dave.
- U1 outcome pending Arwin's investigation (may be a non-bug).
- All other non-AI items should be resolved by NEO-005 + ARWIN-001.


## Next non-AI batch (Dave-approved direction: fix the other things)
Remaining open: H1–H7 (High), M1–M8 (Medium), L1–L4 (Low), U1–U4 (UI/UX → Arwin).
Candidates to queue next (Neo, non-AI):
- H1 `/api/storage/export` 500
- H3/H4 UI JS errors (H4 → Arwin? H3 is settings.html dead dropdown, UI; could be Arwin)
- H6 unsubscribe 404, H7 stale client, H2 config save bug
- M1/M2 auth gaps, M3 GET-mutates-config, M5 misplaced mismatch, M7 broken thumbs (UI → Arwin)
- UI/UX (Arwin): U1 timezone, U2 "479 issues" banner, U3/U4 thumbnails + dead dropdown

---

## [AUDIT-2026-07-13-AI] 2026-07-13 — Full AI-Subsystem Audit (COMPLETE, AWAITING DEPLOY)

- Scope: AI subsystem (services/ai_classifier.py, app.py /api/ai/*, web/settings.html) across
  functionality/performance/efficiency/security/completeness.
- Roster (all ran): Neo (C5+injection+allow-list+retry), Gwen (research brief), Arwin (XSS audit + wire UI),
  Sheldon (review gate x2), MoA review preset (second tier), Jnu (archive).
- Pipeline: Wave1 done -> Sheldon W2 APPROVE-WITH-NOTES -> MoA AMEND->CONDITIONAL (3 gates) ->
  Neo+Arwin closed gates (W4) -> Sheldon W5 APPROVE (all 3 gates YES, 0 blockers).
- C5 root cause (George, pre-dispatch): classify_video unpacked _classify_sync's return as dict but
  it returns a tuple -> TypeError on every call. CONFIRMED fixed by Neo; 22 AI tests, suite 92 green.
- Deliverables: ai_classification_research.md (Gwen), ai_ux_audit.md (Arwin),
  updates/audits/2026-07-13_ai_audit.md (Jnu), this ledger.
- Status: SHIP-READY. Awaiting Dave's commit word -> Render deploy.
- **Scope:** Full audit of the AI subsystem — `services/ai_classifier.py`, `app.py` `/api/ai/*`, and `web/settings.html` AI UX — across five lenses: functionality, performance, efficiency, security, completeness.
- **Roster fanned out (parallel):**
  - **Neo** — code track: fix C5 (`ai_classifier.py` classify tuple/dict bug) + injection hardening + performance.
  - **Gwen** — research track; deliverable → `project_information/architecture/ai_classification_research.md`.
  - **Arwin** — UX audit of AI surface; deliverable → `project_information/design_guidelines/ai_ux_audit.md`.
  - **Sheldon** — review gate (1st-tier verification of Neo's fix + others).
  - **MoA review preset** — 2nd-tier (Mixture-of-Agents) review preset.
  - **Jnu** — archival: this entry + master index at `updates/audits/2026-07-13_ai_audit.md`.
- **Status table:**

  | Agent | Role | Status |
  |-------|------|--------|
  | Neo | C5 fix + injection + perf | 🟡 DISPATCHED (in progress) |
  | Gwen | research | 🟡 DISPATCHED (in progress) |
  | Arwin | UX audit | 🟡 DISPATCHED (in progress) |
  | Sheldon | review gate | ⬜ PENDING |
  | MoA preset | 2nd-tier review | ⬜ PENDING |
  | Jnu | archive | ✅ DISPATCHED (scaffold done) |

- **Confirmed root cause (pre-dispatch, by George):** **C5** — `classify_video` in `ai_classifier.py` unpacks `_classify_sync`'s return **as a dict but it returns a tuple** → `TypeError` on every classify call. AI classification 100% broken. Bug register status: ⬜ open; **being fixed by Neo** (status NOT yet flipped — George verifies fix first, per standing rule).
- **Expected deliverables / landing zones (all PENDING until produced):**
  - Gwen research → `project_information/architecture/ai_classification_research.md`
  - Arwin UX audit → `project_information/design_guidelines/ai_ux_audit.md`
  - Neo fix diff → source (`services/ai_classifier.py` + `app.py`) + commit record under `updates/commits/` on Dave's approval
  - Sheldon verdict → review-gate note (here / ledger)
  - MoA verdict → 2nd-tier review note (here / ledger)
- **Master audit index:** `updates/audits/2026-07-13_ai_audit.md`
- **Rules honored:** no source/config/bug_register edits by Jnu; no commit/push/deploy.


