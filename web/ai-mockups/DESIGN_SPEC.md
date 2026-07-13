# motus.leap — AI Management UX/UI Design Spec

**Phase:** 1 (research + UX/UI design only). No backend code.
**Author:** ARWIN (UX/UI specialist) · **Date:** 2026-07-13
**Status:** FINALIZED design — reconciled contract + Dave's 4 product decisions baked in. Awaiting Sheldon (reviewer) + MoA review. Mockups under `web/ai-mockups/` are throwaway scratch (Tailwind CDN + FA + inline `<style>`), NOT production.

---

## 0. Dave's 4 Product Decisions (baked into this spec)

| # | Decision | How it is encoded |
|---|----------|-------------------|
| 1 | **AI Landing Page = YES** — build an AI Hub at `/ai` | New `index.html` mockup (light overview: provider health, rule count, recent jobs, quick links + Settings pointer card). §1 + new §1.x. |
| 2 | **Rule→Playlist uniqueness = NO duplicates** — at most ONE rule per `target_playlist` | `POST /api/ai/rules` returns **409** on duplicate `target_playlist`; UI shows conflict error ("'Aviation' already has a rule — edit or delete it first"). §3 Flow B + §7 rules contract. |
| 3 | **Global classification prompt stays in Settings** | Existing AI Integration tab keeps global prompt + auto-apply. AI Hub shows a pointer card to Settings. Noted in §1 IA + §1.x. |
| 4 | **Provider fallback = YES** | If active/default provider errors mid-chat, auto-fall back to next enabled active provider; reply surfaces `model_used`. UI shows "answered by `<model>`". §3 Flow C + §7 chat contract. |

> **Contract reconciliation (Gwen ↔ UI):** Gwen's brief (ai_enhancement_research_2026-07-13.md) used `POST .../discover` + `POST .../select`. The UI is the consumer and already standardized on **`GET /api/ai/providers/{id}/models`** (discover) and **`PUT /api/ai/providers/{id}/models`** (select). **We keep the UI verbs.** Gwen's `discover` ⇒ `GET .../models`; Gwen's `select` ⇒ `PUT .../models`. The §7 table is now the single source of truth; Gwen's §F.3 inventory is folded in below.

---

## 1. Information Architecture

### Decision: NEW top-level "AI" sidebar nav item → AI Hub

**Recommendation:** Add a dedicated top-level sidebar item **AI Management** (icon: `fa-comments`/`fa-robot`) that opens an **AI Hub** with a secondary (inner) sub-nav:

> **Providers · Models · Rules · AI Chat · Scheduled Jobs**

**Justification (vs. expanding Settings):**
1. **Scope explosion.** The current "AI Integration" tab in `settings.html` already packs provider select, custom endpoint, API key, classification mode, prompt, training memory, suggestions, and a test-classify box into one scroll. Dave's 6 goals (connect → load models → select → describe rules → chat-manage → schedule) need their own screens. Burying them deeper in Settings hides the feature and repeats the "not intuitive" failure.
2. **Mental model.** Providers/Models are *infrastructure*; Rules/Chat/Jobs are *operations*. Settings is for global knobs, not a management console. A first-class AI area signals it's a primary capability, not a hidden toggle.
3. **Navigation parity.** Every other primary surface (Dashboard, Playlists, Subscriptions, Maintenance, Settings) is a top-level item. AI now earns the same.
4. **Migration path.** In Phase 2, the existing Settings "AI Integration" tab is reduced to a **pointer card** ("Manage AI →") + the global classification prompt/auto-apply toggle (kept in Settings because they're global settings). Nothing is lost.

### AI Hub structure
- **AI Hub landing** (`/ai`): light overview — provider health, rule count, recent scheduled jobs, quick links, **plus a pointer card to Settings** for the global classification prompt & auto-apply (Decision 3). Built as `index.html` mockup. Full spec in §1.x.
- **Providers** (`/ai/providers`): connect / disconnect / list.
- **Models** (`/ai/models`): per-provider model multi-select + default model.
- **Rules** (`/ai/rules`): role cards, enable/disable, edit (form or chat).
- **AI Chat** (`/ai/chat`): conversational management + confirm/destructive flow.
- **Scheduled Jobs** (`/ai/jobs`): upcoming jobs list + create (NL or cron).
- **Settings → AI Integration tab (unchanged):** keeps the **global classification prompt** and **auto-apply** toggle (Decision 3). Not an AI-Hub screen; AI Hub links to it.

### Sidebar markup pattern (locked)
All five sub-items live under a grouped `<div class="mt-2 pt-2 border-t border-[#2a2f3a]">` block, each an `<a class="ai-sub ...">` with active state `bg-[#2a2f3a] text-white border-l-2 border-[#2f8fc9]`. Mobile uses the existing `#sidebar-toggle` / `#mobile-overlay` / `closeMobileSidebar()` off-canvas pattern — no new mobile code needed. **An `AI Hub` (`/ai`) item is the first (active-by-default) sub-item** above Providers.

---

## 1.x AI Hub Landing (`/ai`)

**Purpose (Decision 1):** a single light overview screen so Dave sees system state at a glance without diving into sub-screens, and a clear pointer to where the global prompt lives (Decision 3). Mockup: `web/ai-mockups/index.html`.

**Layout (bento, dark tokens, responsive — single column <768px, 2–4 col strips ≥768px):**
1. **Header** — "AI Hub" + "Open AI Chat" accent button (→ `/ai/chat`).
2. **Settings pointer card (Decision 3)** — tinted accent border, icon + copy: *"Global classification prompt & auto-apply — managed in Settings → AI Integration."* + "Go to Settings →" button (`/settings`). This makes explicit that the prompt is NOT on the AI Hub.
3. **Stat strip (4 bento cards):** Providers (connected count + status), Active models (count + "across N providers"), Rules (count + active/off split), Scheduled jobs (count + next-run).
4. **Provider health** — one card per connected provider: icon + name (sanitized) + base URL (mono, sanitized) + status pill (`#16a34a` Connected) + "X of Y active" sub-line. Empty state: "No providers connected — add one →".
5. **Recent scheduled jobs** — up to 4 job rows: icon + name (sanitized) + cron (mono, sanitized) + "next <time>". Empty state card. "View all →" (`/ai/jobs`).
6. **Quick links** — 4 bento tiles: Connect a provider, Select models, New rule, Ask the AI. Plus a small DOMPurify + fallback note line (reinforces Decisions 4 & security).

**Data sources (mocked in mockup → real endpoints in §7):** `GET /api/ai/providers` (health, model counts), `GET /api/ai/rules` (rule count + active split), `GET /api/ai/jobs` (recent + next run). No writes on this page.

**Constraints honored:** DOMPurify on every provider/job-derived string; `auth-check.js` loaded first; no API keys rendered.

---

## 2. Components (shared, in Dave's locked tokens)

All use `.bento-card` (`bg #1a1d24`, `1px #2a2f3a`, `radius 12px`, subtle shadow). Inputs: `bg #20242c`, `border #2a2f3a`, `min-h-[44px]` (touch target), `text-xs`. Accent buttons `bg #2f8fc9 hover #2a7db8`. Status pills: success `#16a34a`, error `#dc2626`, warning `#ca8a04`, info `#2f8fc9` (all with `/15` bg + `/30` border tints). Toasts mirror `settings.html` (top-right, icon + `DOMPurify.sanitize` message).

| Component | Used in | Notes |
|---|---|---|
| Provider card | Providers, Models | icon + name + base URL (mono) + status pill + Manage/Disconnect |
| Add Provider modal (2-step) | Providers | Step 1: Name/Type/Base/Key → "Connect" → Step 2: model checklist → Save. Stepper dots at top |
| Model group | Models | per-provider collapsible list, checkbox + `Set default`/`DEFAULT` badge |
| Rule card | Rules | icon + name + role desc + target playlist chip + model chip + enable toggle + Edit/Delete |
| New/Edit Rule modal | Rules | name, target playlist, role description (mono), model, enabled |
| Chat window | Chat | AI/user bubbles, action-preview card (destructive = red confirm), suggested chips, input |
| Job card | Jobs | icon + name + cron (mono) + next-run + Run now/Delete |
| Create Job form | Jobs | NL input + "Parse with AI" → cron + task textarea + Create |

---

## 3. Interaction Flows

### Flow A — Connect → Load Models → Select
1. **Providers** → `Add Provider` (or dashed "add" card).
2. Modal **Step 1**: enter Name, pick Type (OpenAI/Anthropic/Groq/Google or Custom), for Custom enter Base URL, enter API Key.
3. Click **Connect** → `POST /api/ai/providers` → `GET /api/ai/providers/{id}/models` returns discovered model list.
4. Modal **Step 2**: render checklist of discovered models (pre-selected sensible defaults). User toggles. Sets nothing destructive.
5. Click **Save Selection** → `PUT /api/ai/providers/{id}/models` (active set). Toast success. Card appears in grid.
6. **Disconnect** (destructive) → `confirm()` → `DELETE /api/ai/providers/{id}`. Rules using its models are disabled (server responsibility; UI shows toast).

### Flow B — Create / Edit Rule via Chat

> **UNIQUENESS CONSTRAINT (Decision 2):** At most **ONE** rule per `target_playlist`. The server enforces this; the UI surfaces the conflict.

1. **Rules** → `Edit via AI Chat` (or chip "Add a rule").
2. Chat opens; user types e.g. *"Add a rule: all synthwave music → Synthwave playlist"*.
3. AI parses → **preview card** (read-only) showing rule name / target / description.
4. If AI needs disambiguation (unknown playlist), it asks — no destructive action.
5. User confirms → `POST /api/ai/rules` (chat-created) or `PATCH /api/ai/rules/{id}`. New card appears in **Rules**.
   - *Alternative path:* Rules → `New Rule` modal (manual). Same endpoint.
   - **Duplicate `target_playlist` (409):** if `POST /api/ai/rules` returns **409 Conflict** (the playlist already has a rule), the UI renders a red error card: *"'<playlist>' already has a rule — edit or delete it first."* The user is offered quick links to that rule's Edit / Delete. The form is NOT cleared (so they can change the target). No rule is created. This applies to **both** the manual modal and the chat path (chat surfaces the same 409 message as an AI error bubble).
   - Mockup state: `rules.html` shows a `data-conflict` error card on duplicate save (see §8 note).
6. Enabling/disabling a rule (toggle) → `PATCH` — **no confirm** (non-destructive, reversible).

### Flow C — Management Chat → Confirm Destructive Action

> **PROVIDER FALLBACK (Decision 4):** If the active/default provider errors mid-chat (5xx / timeout / auth at request time), the server auto-falls back to the **next enabled + active** provider and answers from there. The chat response carries `model_used` so the UI can show **"answered by `<model>`"** (e.g. "answered by llama-3.3-70b-versatile (fallback from Groq)"). If all enabled providers fail, the UI shows a single error ("All AI providers unavailable — check connections in Settings.").

1. User: *"Scan my 1sort playlist for duplicates and remove any duplicates."*
2. AI runs a **read-only scan** automatically (no confirm needed for reads).
3. AI returns a **preview card** listing exact items it will change + a red **"Destructive action — confirmation required"** banner.
4. Buttons: **Confirm & Remove** (`POST /api/ai/actions/{id}/execute`) / **Cancel** (AI leaves library unchanged).
5. On confirm, server executes; AI posts result ("Removed 3 duplicates, 211 remaining") and a small footer line: **"answered by `<model_used>`"** (sanitized, `DOMPurify`). If the answer came via fallback, append "(fallback)".
> **Rule of thumb:** Read-only scans auto-run. Anything that **removes / moves / renames / deletes** shows a preview and waits for explicit Confirm.
> Mockup state: `chat.html` shows an "answered by <model>" footer under each AI reply after send (see §8 note).

### Flow D — Schedule Job
1. **Jobs** → `New Job` (scrolls to form) OR a chat chip "Schedule a job".
2. User types NL ("Every day at 3am, scan 1sort for duplicates") → `Parse with AI` → fills **cron** (`0 3 * * *`) + **task** prompt.
   - *Or* user enters cron directly + task.
3. `Create Job` → `POST /api/ai/jobs` (stores cron + task + enabled).
4. Card appears; "Next run" computed server-side. `Run now` → `POST /api/ai/jobs/{id}/run` (treated like Flow C if the task is destructive — preview + confirm).
5. Delete job → `confirm()` → `DELETE /api/ai/jobs/{id}`.

---

## 4. Component States (every list/async surface)

| State | Pattern |
|---|---|
| **Empty** | Centered icon + muted copy ("No models loaded…", "No scheduled jobs yet…"). Use `#jobs-empty` / `#empty-state` pattern. |
| **Loading** | Spinner `fa-spin` inside the trigger ("Connecting…", "Loading…") or skeleton rows. `fa-spinner fa-spin text-[#2f8fc9]`. |
| **Error** | Red `#dc2626` text/border card + retry. Mirror `settings.html` `resultEl` error styling. Never interpolate raw error without `DOMPurify.sanitize`. |
| **Success** | Green `#16a34a` pill/toast ("Connected", "Rule saved"). |
| **Disabled** | `opacity-75` card, gray toggle, "disabled" label. |

---

## 5. Design Tokens (locked — do NOT introduce new colors)

```
--bg-main:#121419  --bg-deep:#0f1115  --bg-card:#1a1d24  --bg-input:#20242c  --border:#2a2f3a
--accent:#2f8fc9   --accent-hover:#2a7db8
--text:#e5e5e5      --muted-300/400/500:#cbd5e1/#9ca3af/#6b7280 (gray-300/400/500)
--success:#16a34a   --error:#dc2626     --warning:#ca8a04    --info:#2f8fc9
Fonts: Inter (UI), JetBrains Mono (mono/numbers), Deltha (wordmark /static/Deltha.otf only)
Radii: card 12px. Touch targets ≥40px (use min-h-[44px]).
```

---

## 6. Security Notes (NON-NEGOTIABLE)

1. **CSP enforced → NO inline `<script>` and NO inline event handlers (`onclick=`) in production.** Mockups use inline handlers only because they are throwaway review artifacts. Production JS **must** live in `/static/*.js` (e.g. `ai-providers.js`, `ai-chat.js`) and bind via `addEventListener`, exactly like the existing `mobile-nav.js`.
2. **DOMPurify on EVERY AI/YouTube-derived string.** The current `settings.html` already sanitizes `channel_title`/`playlist_name` in the AI suggestions block (lines ~711-712) — **good** — but the diagnostic log lines (1271, 1301) concatenate server `l` strings into `innerHTML` **unsanitized** (latent XSS). The new AI UI must sanitize:
   - all model names (provider-derived),
   - all rule names/descriptions/playlist names,
   - all chat messages and action-preview text,
   - all job names/cron/task,
   - all error/status strings from the API.
   Pattern (from `settings.html`): `el.innerHTML = '...' + DOMPurify.sanitize(value, {USE_PROFILES:{html:true}}) + '...';`
3. **auth-check gate preserved.** Every AI page loads `/static/auth-check.js` first (redirects to `/auth` if no token). Keep it as the first `<script>` after DOMPurify.
4. **Confirm destructive actions** client-side (`confirm()` for disconnect/delete; custom preview card for chat-driven remove/move). Server must ALSO re-validate — UI confirm is UX, not security.
5. **API key handling:** never render the key back (use `•••••••• — previously saved` placeholder pattern from `settings.html`). Send over HTTPS only; mask in inputs (`type=password`).

---

## 7. Backend Contract Needs (FLAG FOR NEO — backend code is out of scope here)

> **Single source of truth.** This table supersedes Gwen's §F.3 inventory in `ai_enhancement_research_2026-07-13.md`. Where Gwen wrote `POST .../discover` we use **`GET /api/ai/providers/{id}/models`**; where she wrote `POST .../select` we use **`PUT /api/ai/providers/{id}/models`**. Phase tags: `existing` (today), `P1/P2/P3` (Gwen's phasing). All request/response bodies that include provider/AI-derived strings must be treated as untrusted and sanitized client-side (§6).

| Method | Endpoint | Purpose | Phase | Request | Response |
|---|---|---|---|---|---|
| GET | `/api/ai/providers` | List connections (keys redacted) | P1 | — | `[{id,name,type,base_url,status,active_model_count,discovered_model_count,enabled}]` |
| POST | `/api/ai/providers` | Connect new | P1 | `{name,type,base_url?,api_key}` | `{id, status}` |
| GET | `/api/ai/providers/{id}/models` | **Discover** models (Gwen's `discover`) | P1 | — | `{models:[{id,name,owned_by?}]}` |
| PUT | `/api/ai/providers/{id}/models` | **Select** active + default (Gwen's `select`) | P1 | `{active:[model_id], default:model_id}` | `{ok:true}` |
| DELETE | `/api/ai/providers/{id}` | Disconnect | P1 | — | `{ok:true}` |
| GET | `/api/ai/models` | All active models (grouped) | P1 | — | `{providers:[{name,models:[{id,name,active,default}]}]}` |
| GET | `/api/ai/rules` | List rules | P2 | — | `[{id,name,description,playlist_id,playlist_name,model,enabled,matched_count}]` |
| POST | `/api/ai/rules` | Create (chat or form) | P2 | `{name,description,playlist_id,model,enabled}` | `{id}` — **409** if `playlist_id` already has a rule (Decision 2) |
| PATCH | `/api/ai/rules/{id}` | Edit/enable | P2 | partial | `{ok:true}` |
| DELETE | `/api/ai/rules/{id}` | Delete | P2 | — | `{ok:true}` |
| POST | `/api/ai/chat` | Send message | P2 | `{messages:[...]}` | `{reply, model_used, actions?:[{id,type,preview,items[]}], fallback?:bool}` |
| POST | `/api/ai/actions/{id}/execute` | Confirm destructive | P2 | `{confirmed:true}` | `{result}` |
| GET | `/api/ai/jobs` | List scheduled jobs | P3 | — | `[{id,name,cron,next_run,task,enabled,last_run,last_status}]` |
| POST | `/api/ai/jobs` | Create | P3 | `{name,cron,task,enabled}` | `{id}` |
| POST | `/api/ai/jobs/parse` | NL → cron+task | P3 | `{text}` | `{cron,task}` |
| POST | `/api/ai/jobs/{id}/run` | Run now | P3 | — | `{job_run_id}` (destructive → preview+confirm flow) |
| PATCH | `/api/ai/jobs/{id}` | Enable/pause | P3 | `{enabled}` | `{ok:true}` |
| DELETE | `/api/ai/jobs/{id}` | Delete | P3 | — | `{ok:true}` |
| POST | `/api/ai/classify` | classify video (existing, now uses active connection + rules) | existing | — | (unchanged shape) |
| POST | `/api/ai/record-move` | record training move (existing) | existing | — | (unchanged) |
| GET | `/api/ai/suggestions` | channel→playlist mapping suggestions (existing) | existing | — | (unchanged) |
| GET | `/api/ai/memory` | training memory (existing) | existing | — | (unchanged) |

### Key contract changes (this finalization)
- **`model_used` added to `POST /api/ai/chat` response (Decision 4).** UI shows "answered by `<model_used>`". `fallback:true` if the answer came from a backup provider; the UI appends "(fallback)".
- **`POST /api/ai/rules` → 409 on duplicate `target_playlist` (Decision 2).** Server must check `playlist_id` uniqueness before insert. Response body suggested: `{error:"playlist_has_rule", playlist_name, rule_id}`. UI renders the conflict card (§3 Flow B).
- **`GET /api/ai/providers/{id}/models`** = Gwen's `discover`; **`PUT /api/ai/providers/{id}/models`** = Gwen's `select`. No `POST .../discover` / `POST .../select` endpoints.
- `GET /api/ai/rules` now returns `playlist_name` alongside `playlist_id` so the UI can render the playlist chip without a second lookup.

**Notes for Neo:**
- `type` enum: `openai | anthropic | groq | google | custom`. For `custom`, `base_url` required.
- **Discovery per type (reconciled, 2026-07-13):** `openai`, `groq`, and `custom` are OpenAI-compatible → live `GET {base}/v1/models` probe. `anthropic` and `google` are NOT OpenAI-shape → probe skipped; `GET .../models` returns the curated catalog or `{manual_entry:true}`. (Gwen §A.2's old 3-value `openai-compatible` type is retired in favor of this 5-value enum; `groq` takes the probe path.)
- Chat `actions[]` drives the confirm/destructive UI (Flow C). Each action carries a typed `preview` so the UI can render the red confirmation card without trusting free-text.
- NL parse (`/api/ai/jobs/parse`) can reuse the same LLM that powers chat; returns structured `cron` (5-field) so the form stays validatable.
- **Fallback order (Decision 4):** server keeps an ordered list of `enabled` providers (per `ai_active_provider_id` first, then remaining `enabled` connections). On active-provider failure, try next; set `model_used` to the model that actually answered and `fallback:true`. If none succeed, return a single 503-style error the UI renders as "All AI providers unavailable — check connections in Settings."
- **Rule uniqueness (Decision 2):** enforce a uniqueness constraint on `playlist_id` (or `target_playlist`) in the `ai_rules` store; `POST` returns 409 on violation. PATCH that changes a rule's `playlist_id` to an occupied one should also 409.

### Agentic-layer & security contract (added 2026-07-13 — Sheldon + MoA review)

> **Auth baseline (all new mutating AI routes):** every new mutating route (`POST /api/ai/providers`, `PUT /api/ai/providers/{id}/models`, `DELETE /api/ai/providers/{id}`, `POST /api/ai/rules`, `PATCH /api/ai/rules/{id}`, `DELETE /api/ai/rules/{id}`, `POST /api/ai/chat`, `POST /api/ai/actions/{id}/execute`, `POST /api/ai/jobs`, `POST /api/ai/jobs/parse`, `POST /api/ai/jobs/{id}/run`, `PATCH /api/ai/jobs/{id}`, `DELETE /api/ai/jobs/{id}`) **MUST** carry `dependencies=[Depends(get_current_user), Depends(verify_origin)]`, matching the existing AI endpoints (`app.py` L2021+). `verify_origin` **MUST** reject requests with missing `Origin`/`Referer` for state-changing methods (harden the known CSRF weakness before chat/jobs ship). Note: `GET /api/ai/providers/{id}/models` (model discovery) is read-only and needs only the read-side auth.

**P1 — required BEFORE `/api/ai/chat` and `/api/ai/jobs` are built (ship-blockers):**
1. **Tool-result sanitization.** Every `tool_result` / retrieved string — including attacker-controlled video titles/descriptions from scan results — MUST pass through `_sanitize_field` + fenced-delimiter treatment before re-entering the model context. Mirrors `ai_classifier._build_prompt` (L318–341). No exceptions.
2. **Model-output validation layer.** Every tool call the model emits MUST be validated against (a) a static tool allowlist per context, (b) a JSON Schema with `additionalProperties:false`, (c) string-param sanitization via `_sanitize_field`, (d) a per-session invocation rate limit.
3. **`schedule_job` privilege gate.** `schedule_job` is PRIVILEGED / confirm-required. Auto-scheduling of destructive payloads (remove/move/delete) is FORBIDDEN without explicit user confirmation at creation. Scheduled destructive jobs execute without per-run confirm *by design* (informed-consent boundary) — so creation is the only confirm point.
4. **Scheduled-job reduced scope.** Scheduled jobs run in a reduced-privilege context: only non-destructive tools allowed unless explicitly elevated at creation (separate elevated confirmation).
5. **Secret redaction.** All AI-endpoint logs/debug MUST redact `*_API_KEY`, `*_TOKEN`, and OAuth credentials (replace with `[REDACTED]`). Provider keys are NEVER logged.
6. **`apply_rules` redefinition.** In the new `ai_rules` model, `apply_rules` is read-only at chat time (validate/activate rules) — it MUST NOT mutate `config`. Retire the legacy `config.rules` write path (background_worker legacy handler persists `payload["rules"]` — must be removed/redefined).

**P2 — before AI pages ship:**
7. **CSP tightening.** Move ALL AI JS to `/static/*.js` AND tighten `add_security_headers` CSP to drop `'unsafe-inline'` + remove `cdn.tailwindcss.com` (build Tailwind locally). The running middleware currently ships `'unsafe-inline'` — the spec posture must match reality (Finding #5).
8. **Discovery per-type.** (See enum note above.) For `anthropic`/`google`, `GET .../models` returns catalog or `{manual_entry:true}` — NOT a live probe.
9. **Type-enum unification.** 5-value enum adopted (above). `groq`/`custom` = probe path; `anthropic`/`google` skip probe. (Gwen §A.2 corrected to match.) *MoA escalated this to P1; it is functionally available at P1 (it lives in the `ProviderConnection` data model + §7 Notes) so P1 discovery is not blocked — restated here for visibility.*
10. **Chat rate limiting.** Per-session rate limit on `/api/ai/chat` aligned to the provider quota tier (guards the single-user YouTube+LLM quota — your recurring burn risk).

**P3 — completeness:**
11. **Pending-action contract.** `POST /api/ai/actions/{id}/execute` accepts ONLY `{confirmed:true}` + server-held payload; a client-supplied payload → 400. Pending action state is server-retained (Finding #9).
12. **Migration x-ref.** `ai_provider` → `ai_providers` back-compat (synthesize from scalars on `ConfigManager.load()`) is specified in Gwen §A.2; restated here — Neo MUST implement before P1 ships so existing configs don't break (Finding #10).
13. **Tool-schema hardening / cross-session isolation.** Tool schemas are static (never built from user content); tool-execution state is strictly session-scoped (no cross-session leakage).

---

## 8. Mockup Files (review artifacts — do NOT commit)

| File | Screen |
|---|---|
| `ai-mockups/index.html` | **AI Hub landing `/ai`** — provider health, rule/job counts, recent jobs, Settings pointer card (Decision 1) |
| `ai-mockups/providers.html` | Provider list + 2-step Add Provider modal (connect → load models) |
| `ai-mockups/models.html` | Per-provider model multi-select + default model |
| `ai-mockups/rules.html` | Rule cards + New/Edit modal + "Edit via AI Chat". *(409 conflict state + answered-by footer are SPECIFIED in §3 but not yet rendered in this mockup — mockup polish, non-blocking.)* |
| `ai-mockups/chat.html` | AI Chat with destructive-action preview/confirm flow + suggested chips. *(answered-by-<model> footer SPECIFIED in §3 Flow C, not yet rendered — mockup polish.)* |
| `ai-mockups/scheduled-jobs.html` | Job list + NL/cron create form |

Open in browser (George): `file:///home/opc/projects/motus.leap/web/ai-mockups/<file>.html`
Responsive: desktop sidebar visible ≥768px; <768px collapses to hamburger + off-canvas (existing `mobile-nav.js` pattern, replicated inline in mockups for standalone viewing).

---

## 9. Open Questions / Follow-ups (RESOLVED)
> The 4 product-decision questions from §0 are now **answered by Dave (2026-07-13)** and encoded throughout this spec. Struck below so they aren't re-litigated.

~~1. AI Hub landing page — DECIDED YES (Decision 1): build `/ai` overview (index.html).~~
~~2. Global classification prompt — DECIDED: stays in Settings, AI Hub links to it (Decision 3).~~
~~3. Rule → playlist uniqueness — DECIDED NO duplicates: one rule per `target_playlist`, 409 on conflict (Decision 2).~~
~~5. Multi-provider fallback — DECIDED YES: auto-fallback + `model_used` surfaced (Decision 4).~~

**Genuinely open (for Neo / later):**
4. **Job execution model** — runs in-process (APScheduler inside `background_worker`) or via a separate worker/cron daemon? Current recommendation: in-process `AsyncIOScheduler` (Gwen §E) — affects "Run now" latency + `next_run` display only.
6. **Rule precedence when two enabled rules would match the same video** — with one-rule-per-playlist (Decision 2) this is largely moot at the playlist level, but cross-playlist overlaps (a video matching rules for two different playlists) still need a defined precedence/tie-break. Server-side decision for Neo.
7. **Chat streaming** — spec assumes request/response `POST /api/ai/chat`. WebSocket streaming is a possible later enhancement (not in scope for P2).
