# Site performance, accessibility, UX and functionality audit

Scope: current FastAPI application, shared web shell, dashboard, playlists,
subscriptions, maintenance, AI Hub, Settings, bulk operations, cache and scan
services, and the existing test suite. Work builds on stabilization commit
`67052db`. Changes remain on `codex/stabilize-cleanup`; they are not deployed.

## Implemented fixes

| Area | Defect and correction |
| --- | --- |
| Full scans | Removed silent 150/200-playlist and 10,000/12,000-video cutoffs. Fetch concurrency remains bounded at 1–5 and invalid concurrency settings fall back to 3. Added a 201-playlist regression. Empty playlist results now replace stale disk content. |
| Cache correctness | Disk-read memory keys include the storage directory, eliminating cross-directory contamination. Playlist invalidation clears direct memory entries and disk-read cache entries. Memory cache is bounded to 128 entries. Retention checks also apply to memory hits. |
| Authentication | Cookie-only sessions no longer redirect solely because localStorage has no token. Logout calls the revocation endpoint before clearing client state, surfaces failure, and clears library caches. WebSocket accepts the server cookie and validates supplied origins. |
| Deploy freshness | Static assets revalidate with ETags instead of being pinned indefinitely by unchanged URLs. Service worker uses network-first static caching, ignores private/API/cross-origin requests, and deletes only its own older caches. Registration is currently under `/static/`; whole-site offline navigation is not enabled. |
| Dashboard | Polling avoids hidden tabs and overlapping scan-status requests. Console output is bounded to 500 lines. Failed maintenance reads no longer produce a false “Clean” state. OAuth messages require the same origin. Read retries return the final response and mutations are not automatically retried. |
| Accessibility | Added names to 42 form controls, navigation labels, current-page state, skip link, notification announcements, and global reduced-motion behavior. Mobile navigation now retains the real overlay, supports Escape, traps focus while open, restores focus, and makes its closed mobile sidebar inert. |
| Feedback | Partial bulk moves report the actual success count and retain unconfirmed items. Subscription refresh no longer displays success after failure. Browser storage quota errors no longer prevent fresh playlist/subscription data from rendering. “Cancel” that only hid progress now says “Hide progress.” |
| Logging | Fixed shared-stream heartbeat replies and tab-return reconnects; suppressed duplicate dashboard connections. Routed 36 worker log broadcasts through persistent logging, preserved error severity, buffered early console messages, and added recent-log history. Rotates 5 MiB files with three backups and reads a bounded tail. |
| AI and backend | Repaired async test mocks at the actual transport boundary. Provider discovery stops retrying permanent HTTP errors. Added shutdown of classifier connections and scheduler. Restored the scan-cache method’s documented return value. Added origin checks to four mutation endpoints. |
| Verification | Added Python security/cache regressions and dependency-free JavaScript behavior tests, wired into CI. Existing playlist-protection rules are preserved; the old mapping test now explicitly exercises a staging playlist. |

## Highest-value next improvements

These are recommendations, not claims that the features have been implemented.

| Priority | Improvement | Benefit and acceptance criteria |
| --- | --- | --- |
| 1 | Compile and self-host CSS; fingerprint static assets | Pages currently load Tailwind's runtime CDN script and external font/icon resources. Build a CSS artifact covering dynamic classes, then use content-hashed URLs with long cache lifetimes. Verify all screens and dark/mobile states visually before replacing the runtime. Measure cold/warm page loads on a midrange phone. |
| 1 | Durable scan jobs with progress and coverage | Show playlists completed/total, videos examined, elapsed time, partial failures, last successful refresh, and resume/retry controls. A job must not be labelled complete when any playlist failed. Persist checkpoints and cancellation state across restarts. |
| 1 | Complete bulk-operation results | Return successful and failed item IDs with reasons; preserve failed selections and offer “Retry failed.” Use idempotency keys so a network retry cannot duplicate a mutation. Preview moves before applying them. Only offer undo where a reliable compensating action exists. |
| 1 | Paginated, searchable library API | Large pages still download and hold full collections. Add server pagination, stable sorting and search; render only visible rows. Test at 25,000+ videos and ensure selections persist across pages. |
| 2 | Use the larger quota for deliberate freshness | Keep lightweight incremental sync, add an explicit full reconciliation that does not infer unchanged contents solely from equal video counts, and show data age. Display estimated local usage separately from authoritative Google usage. The ledger currently tracks mutations and resets on UTC, so it is not a complete Google quota meter. |
| 2 | Explain classification and protect user intent | Show the rule/channel match that proposed each move, confidence, source/target and protection reason. Allow pinning a video to its current playlist and resolving conflicting rules in a review queue. |
| 2 | Consolidate navigation and action feedback | Use the shared shell and common accessible dialog, toast and error components everywhere. Separate Hide, Stop, Retry and Undo; remove duplicate action entry points and developer-only controls from everyday views. |
| 2 | Performance measurements and deployment gates | Establish mobile and desktop baselines for LCP, INP, CLS, API latency, request count, JS/CSS transfer and scan memory. Require CI before deployment and protect main after write access is restored. Do not claim production speedups from unit-test duration. |

## Verification and limits

- Python regression suite: **335 passed** on Python 3.12. Production undefined-name gate and compilation passed.
- JavaScript: **6 behavioral regressions passed**; **21 source/inline-script blocks** passed syntax checks.
- Source inspection covers page form labels; it does not establish WCAG conformance.
- The cloud browser refused the local preview URL (`ERR_BLOCKED_BY_CLIENT`). No
  screenshots, Lighthouse scores, mobile touch verification, contrast measurements,
  or authenticated production end-to-end results are claimed.
- YouTube, OAuth and AI-provider behavior is mocked in tests. Live credentials,
  account permissions, provider outages, quota enforcement and Render runtime
  health need staging/production verification.
- Existing style lint debt remains. CI's production F821 gate is not a full
  style/type-clean bill of health.
- GitHub previously rejected branch creation with “Resource not accessible by
  integration.” No alternate write route is attempted. Publishing requires the
  connector's repository-write permission to be corrected.
