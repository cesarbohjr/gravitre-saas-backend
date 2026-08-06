# Gravitre performance & reliability audit

**Status:** Diagnosis only (no inline fixes)  
**Tip at audit:** prod `40064803` (`api.gravitre.app/health`) · `origin/main` matched  
**Date:** 2026-08-06  
**Discipline:** Every claim is **CONFIRMED** (measurement / code / query) or **UNKNOWN** (not measured). No “probably fine.”

Artifacts produced this pass:

| Artifact | Purpose |
| -- | -- |
| `docs/delivery/_perf-audit-link-check-2026-08-06.json` | Unauthenticated link crawl |
| `docs/delivery/_perf-audit-api-mount-2026-08-06.json` | JWT-timed chat-mount APIs |
| `docs/delivery/_perf-audit-ia-redirects-2026-08-06.json` | IA consolidation redirects |
| Prior: `docs/delivery/unified-turn-task-ttft-live.json` (2026-08-05) | Streaming TTFT |

---

## Executive summary

The app “feels slow” is **not** primarily explained by marketing TTFB or broken links. The strongest evidence points to:

1. **Chat workspace mount APIs** that take **4.5–6.0s** (`business-signals`, `advisor-brief`) on every `/ai` load.  
2. **Task-turn streaming TTFT** still far above the program’s ~200ms / social ~500–750ms baselines (`wall_ttft_p50_ms=3568`, max `20904`).  
3. **No frontend error reporting** (Sentry absent) — failures can stay console-only.  
4. Marketing Lighthouse CI is **failing on main**, but exact LCP/INP numbers were **not recoverable** from CI artifacts this pass (local Chrome missing).

Standing TTFB finding for `/` + `/pricing` page-level `"use client"`: **RESOLVED** (server page shells + client islands).

---

## Part A — Page load / Core Web Vitals

### A1. Lighthouse coverage (current wiring)

| Item | Evidence | Status |
| -- | -- | -- |
| CI Lighthouse URLs | `apps/web/lighthouserc.json` → only `http://127.0.0.1:3000/` and `/pricing` | **CONFIRMED** |
| App routes in LHCI (`/ai`, `/activity`, `/agents`, `/settings`, `/connectors`) | Not in `lighthouserc.json` | **CONFIRMED gap** |
| Latest Marketing Lighthouse CI on main | Run `31053173680` (2026-08-05) → **failure** (`categories.performance` minScore 0.75) | **CONFIRMED** |
| Numeric LCP / INP / CLS from that run | No downloadable artifacts; log lacks per-metric values | **UNKNOWN** (CI failed; metrics not retained) |
| Local Lighthouse vs prod | No Chrome/Edge binary on audit machine | **UNKNOWN this pass** |

### A2. Standing finding: `/` and `/pricing` client-rendered?

| Route | Page file | `"use client"` at page? | HTML / timing |
| -- | -- | -- | -- |
| `/` | `apps/web/app/(marketing)/page.tsx` | **No** — default server component | RSC flight HTML present; title in first HTML; browser nav TTFB **23ms**, DCL **322ms**, `loadEvent` **6159ms** |
| `/pricing` | `apps/web/app/(marketing)/pricing/page.tsx` | **No** — default server component | Browser nav TTFB **17ms**, DCL **1408ms**, `loadEvent` **1614ms** |

**Verdict: RESOLVED.** The earlier “fully client-rendered page” finding does **not** hold on tip `40064803`. Client islands remain (e.g. `components/marketing/home/*` marked `"use client"`), but the page shell is server-rendered.

Cold HTTP HEAD averages (3 samples, PowerShell `Invoke-WebRequest`):

| Route | Avg TTFB (ms) | Status |
| -- | -- | -- |
| `/` | 235 | 200 |
| `/pricing` | 212 | 200 |
| `/login` | 176 | 200 |
| `/ai` | 226 | 307 → login (unauth) |
| `/activity` | 225 | 307 → login |
| `/agents` | 223 | 307 → login |
| `/settings` | 225 | 307 → login |
| `/connectors` | 270 | 307 → login |

### A3. Poor-route causes / bundle analyzer

| Item | Status |
| -- | -- |
| `@next/bundle-analyzer` wired (`ANALYZE=true` in `next.config.mjs`) | **CONFIRMED** |
| Fresh analyzer report on tip | **UNKNOWN** — not run this pass (build+ANALYZE not executed) |
| Homepage long `loadEvent` (6159ms) despite fast TTFB | **CONFIRMED** browser Navigation Timing — likely deferred media/fonts/JS after DCL; exact resource attribution **UNKNOWN** without Lighthouse waterfall |

### A4. Chat theme / background cost

| Item | Status |
| -- | -- |
| Live themes | **CONFIRMED** 5 department tiles in `lib/chat-background-themes.ts` (not 8 washes). Legacy 8-theme module orphaned. |
| PNG sizes | **CONFIRMED** ~51–68 KB each (`gw-*-{light,dark}.png`) |
| Measurable CLS/LCP delta with theme on vs plain | **UNKNOWN** — no A/B Lighthouse this pass |
| Prior risk note | Bake-alpha + `background-attachment: local` exist as code mitigations — **CONFIRMED** comments; benefit **UNKNOWN** numerically |

---

## Part B — Chat window load & streaming

### B1 / B2. Mount APIs and TTI

Product chat is **`/ai`** (`AiWorkspace`). `/chat` is Universal Search.

**CONFIRMED mount fan-out (code):** parallel SWR for `auth/me`, billing, onboarding, conversations list, preferences, business-signals, advisor-brief, metrics, approvals, notifications (15s poll); message load gated on `orgReady`. Duplicate `auth/me` keys across shell + workspace.

**CONFIRMED live API timings** (JWT operator org, tip `40064803`, sequential probe — wall times):

| Endpoint | ms | Status |
| -- | -- | -- |
| `/api/assistant/advisor-brief` | **6008** | 200 |
| `/api/assistant/business-signals` | **4576** | 200 |
| `/api/connectors` | 1204 | 200 |
| `/api/auth/me` | 970 | 200 |
| `/api/metrics/overview` | 739 | 200 |
| `/api/billing/status` | 601 | 200 |
| `/api/conversations?limit=100&include_archived=true` | 451 | 200 |
| `/api/agents` | 447 | 200 |
| `/api/notifications?limit=50` | 378 | 200 |
| `/api/approvals` | 359 | 200 |
| `/api/onboarding` | 310 | 200 |
| `/api/assistant/preferences` | 299 | 200 |
| `/api/organizations` | 181 | 200 |

**Chat TTI (type + send):** **UNKNOWN** as a single browser stopwatch this pass (no authenticated browser session). **Lower bound CONFIRMED:** if UI waits on advisor-brief/business-signals before declaring ready, mount cost alone is **≥6s** on the critical parallel path (slowest of the parallel set). If input is enabled before those complete, perceived TTI can be lower — wiring of “disabled until…” **UNKNOWN** without authenticated instrumentation.

### B3. Side panel threshold

| Item | Status |
| -- | -- |
| `SIDE_PANEL_STEP_THRESHOLD = 3` | **CONFIRMED** `apps/web/lib/task-side-panel-threshold.ts` |
| Wired in `ai-workspace` | **CONFIRMED** |
| Live under-threshold rate on tip | **UNKNOWN** (no new prod sample; prior v2 live PASS recorded 2026-08-04) |

### B4. Streaming TTFT vs baselines

From `docs/delivery/unified-turn-task-ttft-live.json` (2026-08-05, tip era `63d95eec…` / reverify):

| Metric | Value | Status |
| -- | -- | -- |
| `wall_ttft_p50_ms` | **3568** | **CONFIRMED** |
| `wall_ttft_min_ms` | 1344 | **CONFIRMED** |
| `wall_ttft_max_ms` | **20904** | **CONFIRMED** |
| `model_ttft_p50_ms` | 2859 | **CONFIRMED** |
| Gate / `ok` | **false** (misses 200ms program gate) | **CONFIRMED** |
| Social baseline ~500–750ms | Documented in `unified-turn-ttft-investigation.md` | **CONFIRMED** historical |
| Fresh TTFT on tip `40064803` | Not re-probed this pass | **UNKNOWN** vs 2026-08-05 artifact |

---

## Part C — Links, buttons, empty states

### C1. Unauthenticated link checker

`python scripts/check-deployed-links.py --base-url https://gravitre.app`:

| Metric | Value | Status |
| -- | -- | -- |
| Pages fetched | 138 | **CONFIRMED** |
| Broken (≥400) | **0** | **CONFIRMED** |
| Empty HTML | **0** | **CONFIRMED** |
| Assertion / metadata failures | **0** | **CONFIRMED** |
| App shells (`/marketplace`, `/connectors`, `/ai/help/control`, …) | HTTP 200 with `text_len≈804` (login/shell without auth content) | **CONFIRMED** — not counted broken |

### C2. Authenticated in-app crawl (standing gap)

| Item | Status |
| -- | -- |
| Named gap in `ui-ux-audit-pass2-2026-07-24.md` | **CONFIRMED** still accurate |
| `navigation-e2e.yml` | **CONFIRMED** `workflow_dispatch` only |
| `check-deployed-links.py` auth mode | **CONFIRMED** none |
| This pass | IA redirects + unauth crawl + code empty-state review + API timings | **PARTIAL close** — not a full Playwright authenticated click crawl |

**IA redirects (CONFIRMED live):**

| From | To | HTTP |
| -- | -- | -- |
| `/outcomes` | `/activity` | 308 |
| `/runs` | `/activity` | 307 |
| `/tasks` | `/activity` | 308 |
| `/intelligence/agents` | `/agents` | 308 |
| `/agents/swarm` | `/multi-agent-run` | 308 |
| `/workflows/failure-predictions` | `/activity?tab=failures` | 307 |
| `/ai`, `/activity`, `/agents`, `/settings`, `/connectors`, `/marketplace` (unauth) | `/login` | 307 |

### C3 / C4. Buttons & empty states (code + unauth)

| Surface | Empty state | Dead buttons |
| -- | -- | -- |
| Activity | Helpful + CTAs (`activity/page.tsx`) | No `href="#"` / empty handlers found |
| Agents | “No agents yet” + New Agent | None found |
| Connectors | Helpful + Add connector; “Coming soon” → toast (intentional gate) | Not dead — gated |
| Outcomes page | Redirect stub only | N/A |

**Authenticated live click of every control:** **UNKNOWN** this pass.

---

## Part D — Silent / processing errors

| Finding | Status |
| -- | -- |
| `apiFetch` default timeout **60s** (`apps/web/lib/fetcher.ts`) | **CONFIRMED** |
| Most client API via `fetcher` / `*Api` | **CONFIRMED** |
| Raw `fetch` bypasses (login me, signup analytics, oauth callback, marketing cards, …) | **CONFIRMED** small set (~6–7 client sites) |
| Frontend Sentry / `@sentry/*` | **CONFIRMED absent** |
| Route `error.tsx` → `route-error` + `console.error` only | **CONFIRMED** |
| Module D voice on backend tool errors | **CONFIRMED** adapters exist |
| Every FE async path shows Module D copy | **UNKNOWN** (needs live failure samples) |
| Rate-limit UX for 429 via `apiFetch` | **CONFIRMED** `RateLimitError` path exists; end-to-end UX **UNKNOWN** |

---

## Part E — Supabase organization & query performance

Project: `smyeexlrqdpymwjmgzqu` (`SUPABASE_URL`).

### E1. Slow-query log / `pg_stat_statements`

| Item | Status |
| -- | -- |
| `pg_stat_statements` enabled | **UNKNOWN** — extension probe did not return a usable row set in this MCP session |
| Top production queries by time | **UNKNOWN** — cannot claim without statements / dashboard export |

**Proxy evidence (API wall times above):** advisor-brief / business-signals dominate chat-path latency even if SQL itself is not proven as the bottleneck.

### E2. Indexing (high-traffic tables)

**CONFIRMED present (examples):**

- `conversations`: org/user/updated, active partial, GIN `task_state`, title FTS  
- `conversation_messages`: `(conversation_id, created_at)`  
- `audit_events`: `(org_id, created_at DESC)`, resource index  
- `workflow_runs`: org/created, org/env/created, active unique  
- `connectors`: org/type/status/env + soft-delete partial  
- `notifications`: org/user/created + unread partial  
- `agent_jobs`: org/created, status/created  

**CONFIRMED unused indexes (`idx_scan=0`):**

- `idx_conversations_title_search`  
- `idx_conversations_org_user_pinned_updated`  

**CONFIRMED advisor volume (project-wide performance lints):** 621 total — **173** `unindexed_foreign_keys`, **172** `auth_rls_initplan`, **155** `unused_index` (Supabase `get_advisors` performance).

### E3. RLS policy performance

**CONFIRMED** policy shapes from `pg_policies`:

- `conversations_*`: `user_id = auth.uid()` AND `org_id IN (SELECT … organization_members WHERE user_id = auth.uid())`  
- `conversation_messages_*`: `EXISTS (conversations …)` + membership subquery  
- `connectors_org_scope`: membership subquery (duplicate of `connectors_org` using `auth_org_accessible`)  
- `workflow_runs_org`: `org_id = (SELECT … LIMIT 1)`  

These match the classic **auth RLS initplan** anti-pattern (`auth.uid()` re-evaluated per row) called out by Supabase advisors. Quantitative cost at current scale (**~2.4k conversations, ~8k audit_events**) is **UNKNOWN** without EXPLAIN ANALYZE under JWT role.

### E4. N+1 in list endpoints

| Endpoint | Assessment |
| -- | -- |
| Connectors list | Primary list is bulk select; some detail/simulation paths issue follow-up selects — **PARTIAL CONFIRMED** from `connectors.py` patterns; full N+1 proof **UNKNOWN** without tracing |
| Agents / Activity list | Not fully traced this pass | **UNKNOWN** |

### E5. Connection pooling

| Item | Status |
| -- | -- |
| Pooler mode / size vs traffic | **UNKNOWN** — not readable from app config; `pg_settings` via MCP returned sizes only |
| Table sizes | audit_events **7.0 MB**, conversations **6.9 MB**, messages **0.6 MB**, workflow_runs **0.7 MB** — **CONFIRMED** (small; pooler unlikely the primary pain today) |

### E6. Bloat / maintenance

| Table | n_live_tup | n_dead_tup | Status |
| -- | -- | -- | -- |
| audit_events | 8065 | 174 | **CONFIRMED** |
| conversations | 2390 | 504 | **CONFIRMED** (~21% dead — elevated) |
| conversation_messages | 1028 | 0 | **CONFIRMED** |
| workflow_runs | 413 | 122 | **CONFIRMED** |
| agent_jobs | 109 | 66 | **CONFIRMED** |
| `last_analyze` | null on sampled tables | **CONFIRMED** — analyze lag |

---

## Part F — Prioritized findings & sequenced closure plan

Severity × breadth × fix complexity. Diagnosis only.

| Rank | ID | Finding | Sev | Breadth | Complexity | Evidence |
| -- | -- | -- | -- | -- | -- | -- |
| 1 | PERF-CHAT-MOUNT | `/ai` mount calls `advisor-brief` (6008ms) + `business-signals` (4576ms) | Critical | Every chat open | Medium (defer/lazy/cache) | API timings tip `40064803` |
| 2 | PERF-TTFT | Task wall TTFT p50 **3568ms** (max 20.9s); gate fail | Critical | Every task turn | Hard (model/prompt/tools) | `unified-turn-task-ttft-live.json` |
| 3 | REL-SENTRY-FE | No frontend Sentry; route errors → console only | High | All web surfaces | Narrow | Code search |
| 4 | PERF-LHCI-FAIL | Marketing Lighthouse CI failing; app routes not gated | High | Marketing + unknown app | Medium | GH run `31053173680`; `lighthouserc.json` |
| 5 | QA-AUTH-CRAWL | Authenticated in-app crawl still not CI-automated | High | All authenticated IA | Medium | `navigation-e2e.yml` + pass2 audit |
| 6 | PERF-DUP-ME | Duplicate `/api/auth/me` SWR keys on `/ai` | Medium | Chat shell | Narrow | Code |
| 7 | DB-RLS-INITPLAN | RLS uses per-row `auth.uid()` subqueries; 172 advisor WARN | Medium | Org-scoped tables | Medium | `pg_policies` + advisors |
| 8 | DB-UNUSED-IDX / FK | 155 unused indexes + 173 unindexed FKs (project-wide) | Medium | Write/join paths | Narrow–medium | Advisors + `idx_scan=0` |
| 9 | PERF-HOME-LOAD | `/` `loadEvent` 6159ms after 23ms TTFB | Medium | Marketing home | Medium | Browser Navigation Timing |
| 10 | DB-ANALYZE | Hot tables `last_analyze` null; conversations dead tuples elevated | Low–Med | Query planner | Narrow | `pg_stat_user_tables` |
| 11 | THEME-COST | Theme PNGs modest; render delta unmeasured | Low | Chat users with theme | Narrow | Asset sizes; A/B **UNKNOWN** |
| — | TTFB-SSR | `/`+`/pricing` page-level client render | — | — | — | **CLOSED / RESOLVED** |

### Recommended closure sequence (for follow-up execution prompt)

1. **Defer or lazy-load** `advisor-brief` + `business-signals` off the critical `/ai` path; keep chat input interactive without waiting on them. Re-measure mount wall.  
2. **Re-run TTFT battery** on tip `40064803`; treat streaming p50 as a separate workstream from mount.  
3. **Wire Sentry (or equivalent) on FE** + verify error boundaries report stack + org/route context.  
4. **Expand Lighthouse CI** to authenticated or at least public shells for `/login` + key marketing; capture numeric LCP/INP/CLS artifacts; install Chrome in local audit env or use LHCI temporary storage downloads.  
5. **Enable scheduled authenticated Playwright crawl** (`navigation-e2e` / `click-audit.js`) with smoke credentials — close the pass2 gap for real.  
6. **RLS initplan fix** (`(select auth.uid())` pattern) on conversations/messages/connectors; drop or justify unused indexes; add missing FK indexes on hottest FKs only.  
7. **ANALYZE** hot tables; watch conversations dead-tuple ratio.  
8. Theme A/B Lighthouse only if chat CLS complaints remain after #1–2.

---

## Explicit UNKNOWN backlog (do not invent)

- Numeric LCP / INP / CLS per route from Lighthouse  
- Authenticated chat TTI stopwatch (navigation → input enabled)  
- Bundle analyzer top chunks on tip  
- Theme on vs plain CWV delta  
- `pg_stat_statements` top queries  
- Pooler configuration vs concurrent connections  
- Full authenticated dead-button click matrix  
- Fresh TTFT on tip `40064803` after 2026-08-05 artifact  

---

## Update discipline

Same as the routing decision map: append dated sections when re-measured; never upgrade UNKNOWN → CONFIRMED without a new artifact pointer (CI URL, JSON path, or audit_events / query result).
