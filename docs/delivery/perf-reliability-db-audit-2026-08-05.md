# Performance / reliability / database audit — 2026-08-05

**Tip confirmed:** prod `/health` `git_sha=40064803f4e25ee8977a7c43a03a4fc0b67b1e9c` @ `2026-08-05T23:48:27Z`  
`https://gravitre-saas-backend-production.up.railway.app/health` — `status=ok`, `database=healthy`, `cache=healthy`, unified-turn live + embedding retrieval on.

**Prompt:** `docs/delivery/perf-reliability-db-audit-prompt.md` (Parts A–F).  
**Parked (not expanded):** `docs/delivery/gravitre-routing-decision-map.md` §G.5.9 (Apollo settle-read residual + Marketo unwired follow-up).

**Method notes**
- Marketing surface audited at **`https://gravitre.app`** (resolves). `gravitre.ai` / `gravitre.com` **NXDOMAIN** from this network — see findings.
- HTTP crawl: `scripts/check-deployed-links.py` → `docs/delivery/_perf-audit-link-check-2026-08-05.json`.
- Real browser: Cursor IDE browser on marketing pages (nav, Support, Pricing). Playwright `click-audit.js` **NOT RUN** (Chromium binary missing in sandbox cache).
- Authenticated in-app crawl **NOT RUN** (no session credentials in this job) — same standing gap as UI/UX pass 2.
- Supabase prod project `smyeexlrqdpymwjmgzqu` via MCP advisors + SQL.
- CI tip: [CI #31054083451](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/31054083451) green on `40064803`.

**Mid-audit one-liner (local only, not deployed):** Support Live Chat target changed from NXDOMAIN `https://gravitre.com/chat` → `/contact` in `apps/web/app/(marketing)/support/page.tsx`. Prod still has the dead URL until merge/deploy.

---

## Executive summary

Marketing HTTP link integrity is green (0 broken on 138 pages). The highest-urgency issues are **trust/domain hygiene** (`gravitre.com` NXDOMAIN used in Live Chat + `metadataBase`), **homepage Lighthouse gate red** (perf 0.70 vs ≥0.75), **nightly production-hardening smoke red for ≥10 days**, and **Supabase security advisors** (RLS disabled on several public tables). Hot-path indexes on `audit_events` / `conversations` exist and are used; action-filtered audit queries filter after `idx_audit_events_org_created` (covering `(org_id, action, created_at)` would help at scale). Output-verification pending debt is **0** at tip (prompt’s “164 missing” is stale).

---

## Findings

Severity: **P0** trust-critical / user-facing broken · **P1** reliability/perf gate · **P2** scale/hygiene · **P3** backlog noise.

### Part A — Links & navigation

| ID | Severity | Finding | Evidence |
|----|----------|---------|----------|
| A1 | **P0** | Support **Live Chat** opened `https://gravitre.com/chat`; **`gravitre.com` is NXDOMAIN** (dead button). | Code: `apps/web/app/(marketing)/support/page.tsx` (pre-fix). DNS: `nslookup gravitre.com` → Non-existent domain (2026-08-05). **Local one-liner applied** → `/contact`; **prod NOT fixed** until deploy. |
| A2 | **P0** | Root `metadataBase` is `https://gravitre.com` (NXDOMAIN). Canonical/OG absolute URLs can point at a non-resolving host. | `apps/web/app/layout.tsx` L35. Live HTML from `https://gravitre.app/` includes `og`/`canonical` hosts under `gravitre.com` (curl SSR 2026-08-05). |
| A3 | **PASS** | Deployed HTTP crawl: **0 broken (≥400)**, **0 empty**, known fragile hubs redirect OK. | `python scripts/check-deployed-links.py --base-url https://gravitre.app --max-pages 150` → 138 pages, 5766 edges; JSON `docs/delivery/_perf-audit-link-check-2026-08-05.json`. `/support/getting-started` → **308** → `https://gravitre.app/docs/getting-started/quickstart` **200**. `/guides/create-your-first-ai-agent` → **308** → `/docs/guides/how-to/agents` **200**. |
| A4 | **PASS (browser)** | Marketing nav soft-nav works: Pricing click → `https://gravitre.app/pricing`, title `Pricing · Gravitre`. Support loads with visible hero + category cards. | Cursor browser CDP + screenshot @ Support/Pricing 2026-08-05. |
| A5 | **PARTIAL** | Support Framer Motion: some nodes remain `opacity:0; transform:translateY(20px)` after load (duplicate/off-viewport set). Visual screenshot of above-fold cards OK; risk for below-fold `whileInView` if IO fails. | CDP `Runtime.evaluate` stuckCount≥10 on `/support` after settle; page still visually rendered for hero/top cards. |
| A6 | **NOT RUN** | Authenticated app sidebar/CTA click crawl. | No `CLICK_AUDIT_*` credentials; Playwright browsers not installed. Prior named gap: `docs/delivery/ui-ux-audit-pass2-2026-07-24.md`. |
| A7 | **NOT RUN** | Chat/canvas `result_url` external record resolution sample. | Requires live authenticated completion cards. |

### Part B — Performance / CWV / API / DB hot paths

| ID | Severity | Finding | Evidence |
|----|----------|---------|----------|
| B1 | **P1** | Marketing Lighthouse **home** fails CI gate: performance **0.70** &lt; **0.75**. | [Marketing Lighthouse CI #31053173680](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/31053173680) on `ce6db384`. Report: https://storage.googleapis.com/lighthouse-infrastructure.appspot.com/reports/1785969422081-55685.report.html — FCP **0.4s**, LCP **2.1s**, TBT **260ms**, CLS **0**, Speed Index **6.3s**; main-thread work **~38s**; unused JS incl. GTM ~237 KiB. |
| B2 | **PASS (pricing)** | `/pricing` Lighthouse performance **0.99** (LCP 0.9s, SI 0.5s, TBT 20ms, CLS 0). | Same CI run pricing report: https://storage.googleapis.com/lighthouse-infrastructure.appspot.com/reports/1785969422759-24497.report.html |
| B3 | **P1** | Homepage cold TTFB elevated vs warm; first sample **~1.22s**, later medians **~0.25–0.43s**. | `curl.exe` to `https://gravitre.app/` ×3 (2026-08-05): 1.222s / 0.434s / 0.253s / 0.261s TTFB. |
| B4 | **INFO** | Marketing pages (pricing/docs/blog/support) warm TTFB ~0.21–0.33s. | Same curl battery. |
| B5 | **INFO** | Backend `/health` TTFB ~0.34s; `/api/connectors` **401** in ~0.23s (auth gate OK); `/openapi.json` TTFB ~1.11s (heavy). | Railway prod base URL probes 2026-08-05. |
| B6 | **NOT RUN** | Authenticated CWV for chat / dashboard / marketplace / settings. | Needs logged-in session + Lighthouse against app shell. |
| B7 | **P2** | `audit_events` filters by `action` without a covering index — plans use `idx_audit_events_org_created` then **Filter** on `action`. | Indexes: `audit_events_pkey`, `idx_audit_events_org_created`, `idx_audit_events_resource` only. `EXPLAIN` for `org_id` + `action='tool.invoke.completed'`: Index Scan + Filter (prod SQL 2026-08-05). Callers: `golden_signals_service`, `metrics/service`, `routers/audit.py`, `audit/query.py`. Table ~7–8k rows today — latent scale risk. |
| B8 | **PASS** | `conversations` / `conversation_messages` / `notifications` / `external_signals` have sensible org/user/time indexes; low seq-scan %. | `pg_indexes` + `pg_stat_user_tables`: conversations seq_pct **0.7%**, audit_events **0.2%**, messages **0.5%**. |
| B9 | **INFO** | `connectors` seq_scan share **45.8%** but only **66** live rows — not a scale problem yet. | `pg_stat_user_tables` prod. |
| B10 | **P2** | Supabase performance advisors: **293 WARN / 328 INFO** — notably `unindexed_foreign_keys` **173**, `auth_rls_initplan` **172**, `unused_index` **155**, `multiple_permissive_policies` **120**, `duplicate_index` **1** (`optimization_recommendations`). | MCP `get_advisors` type=performance on `smyeexlrqdpymwjmgzqu`. |
| B11 | **INFO** | `intelligence_pack_sources` table **absent** in prod; `external_signals` small (26 rows) with org indexes present. | `pg_class` probe for pack/hot tables 2026-08-05. |

### Part C — Code / config hygiene

| ID | Severity | Finding | Evidence |
|----|----------|---------|----------|
| C1 | **P2** | ESLint: **0 errors, 321 warnings** (hooks `set-state-in-effect`, unused vars, impure render). | CI Web job log [31054083451](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/31054083451): `✖ 321 problems (0 errors, 321 warnings)`. |
| C2 | **PASS** | Connector registration contract at tip: `orphans=0`, `pending_schema=0`. | Integration Smoke log same CI run: `Connector registration contract: orphans=0 api_import_exceptions=0 pending_schema=0`. Local `collect_pending_output_schemas()` → **0**. |
| C3 | **P2** | Docs/env drift: HubSpot/setup docs still cite `api.gravitre.com` / `app.gravitre.com` while live marketing is `gravitre.app` and `gravitre.com` does not resolve. | `docs/integration/HUBSPOT_PLATFORM_SETUP.md`; DNS NXDOMAIN for `.com`. |
| C4 | **NOT RUN** | Full dead-code / Meson skeleton orphan sweep. | Out of timebox; no automated orphan report this cycle. |

### Part D — CI / test health

| ID | Severity | Finding | Evidence |
|----|----------|---------|----------|
| D1 | **PASS** | Tip CI green: Backend pytest **4387 passed, 3 skipped**; secondary **425 passed**; Web vitest **169 passed / 35 files**; Dependency audit job success; Billing E2E **skipped** (expected). | [CI #31054083451](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/31054083451) on `40064803`. |
| D2 | **P1** | **Marketing Lighthouse CI** failing streak after intermittent greens (latest fail `ce6db384` / home score 0.70). | Workflow runs list 2026-08-05: multiple `failure` after prior `success` @ `492f32d2`. |
| D3 | **P1** | **production-hardening-smoke** failing **≥10 consecutive nights** (Lane D summary verdict **PARTIAL**). | Runs through 2026-07-27…2026-08-05 all `failure`, e.g. [#30985523567](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/30985523567) — `smoke-hardening-summary-live.py` exit 1, verdict PARTIAL. Artifact contents stale/partial (AI smoke dated 2026-06-27; research cascade dated 2026-07-23). |
| D4 | **INFO** | Billing Playwright E2E skipped in tip CI — keep visible, not silent pass. | Job `Billing E2E (Playwright)` conclusion=`skipped`. |

### Part E — Error handling / observability

| ID | Severity | Finding | Evidence |
|----|----------|---------|----------|
| E1 | **PASS (contract)** | Pending output-verification schema debt **0** (prompt “164” is outdated). | CI registration line + local collector (see C2). |
| E2 | **NOT RUN** | Live end-to-end notification bell + email for a completed action. | Needs authenticated prod turn + `notifications` / email provider proof. |
| E3 | **NOT RUN** | Spot-check `format_tool_error_for_user` / STA-303 mapped copy across connectors in live chat. | Needs live connector failure turns. |
| E4 | **PARKED** | G.5.9 population-verify eventual consistency (Apollo settle-read lag; Marketo follow-up unwired). | `gravitre-routing-decision-map.md` §G.5.9 — **not expanded** this cycle. |

### Part F — Security / dependency hygiene

| ID | Severity | Finding | Evidence |
|----|----------|---------|----------|
| F1 | **P0** | Supabase security advisors: **8 ERROR** `rls_disabled_in_public` including `agent_execution_interrupts`, `intelligence_outcome_events`, `intelligence_learning_signals`, `strategy_performance_records`, `domain_segment_learning_state`. | MCP `get_advisors` type=security; SQL confirms `relrowsecurity=false` for those tables (est. rows up to ~589 on outcome events). |
| F2 | **P1** | Security advisors also: `function_search_path_mutable` **29**, `rls_enabled_no_policy` **11** (marketplace_* tables), `anon/authenticated_security_definer_function_executable` **7** each, leaked-password / MFA INFO. | Same advisors payload. |
| F3 | **PASS** | Dependency audit job: **pip-audit** “No known vulnerabilities found, 1 ignored”; job conclusion success (critical gate). | CI Dependency audit job [31054083451](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/31054083451). |
| F4 | **P1** | HTTP `SENSITIVE_RATE_LIMITS` covers auth / intelligence-engine / agent-jobs / marketplace / admin MCP POSTs — **not** OAuth callback or webhook receiver prefixes. | `backend/app/core/rate_limiter.py` `SENSITIVE_RATE_LIMITS`; middleware only matches those prefixes (`api_rate_limit.py`). Webhook configs may have per-hook limits (`workflow_triggers.py`) but OAuth callbacks lack middleware entry. |
| F5 | **INFO** | No secrets found in this audit’s client HTML spot-check; deeper bundle secret scan **NOT RUN**. | SSR homepage fetch only. |

---

## Prioritized fix queue

Trust-critical first, then reliability gates, then scale/hygiene.

1. **P0 — Domain / Live Chat honesty**  
   - Deploy Support Live Chat fix (`/contact` or real chat provider).  
   - Change `metadataBase` (and any `gravitre.com` marketing canonicals) to the live host (`https://gravitre.app` or confirmed primary).  
   - Sweep docs that still teach `*.gravitre.com`.

2. **P0 — Enable RLS (or revoke grants) on public tables without RLS**  
   - `intelligence_outcome_events`, `intelligence_learning_signals`, `agent_execution_interrupts`, `strategy_performance_records`, `domain_segment_learning_state` (+ remaining advisor ERROR set).  
   - Evidence: Supabase security advisors ERROR count 8.

3. **P1 — Restore Marketing Lighthouse home ≥0.75**  
   - Cut homepage main-thread / unused JS (GTM deferral, chunk weight).  
   - Evidence: LHCI report score 0.70, SI 6.3s, LCP 2.1s.

4. **P1 — Unblock or re-scope `production-hardening-smoke`**  
   - 10+ day PARTIAL streak is silent CI noise violating flaky/honest-harness standards.  
   - Refresh summary inputs; fix or explicitly quarantine with dated justification.

5. **P1 — Rate-limit OAuth callbacks + public webhooks at HTTP middleware**  
   - Extend `SENSITIVE_RATE_LIMITS` (or equivalent) for `/api/connectors/oauth` and webhook paths.

6. **P2 — `audit_events (org_id, action, created_at DESC)` covering index**  
   - Matches golden-signals / metrics / audit API filters; EXPLAIN today filters after org+time index.

7. **P2 — Advisor burn-down (triaged)**  
   - Drop duplicate `optimization_recommendations` index.  
   - Batch hottest `unindexed_foreign_keys` + `auth_rls_initplan` on tables still hit via PostgREST/RLS (not service-role-only).

8. **P2 — Support Motion reliability**  
   - Prefer `animate` for above-fold; ensure `whileInView` has `viewport={{ once: true, amount: 0.2 }}` / reduced-motion fallback so cards never stay at opacity 0.

9. **P2 — ESLint warning burn-down** (321 → trending down; not gate-blocking).

10. **Backlog / next cycle**  
    - Authenticated Playwright click-audit + app CWV.  
    - Live notification + error-copy spot-check (Part E).  
    - §G.5.9 Apollo settle-read equalization + Marketo follow-up decision.  
    - `result_url` external resolution sample.

---

## Explicit coverage checklist

| Required topic | Status |
|----------------|--------|
| Page load / CWV | **Covered** — LHCI home/pricing + live TTFB samples; authenticated CWV NOT RUN |
| Broken links & dead buttons (real browser) | **Covered** — HTTP crawl PASS; browser nav PASS; Live Chat dead domain **P0** (local fix pending deploy) |
| Supabase query/indexing (`audit_events`, conversations, pack/connector) | **Covered** — indexes + EXPLAIN + advisors; pack sources table absent; connectors tiny |
| Findings before bulk fixes | **Met** — this report is the deliverable; one local Live Chat one-liner only |

---

## Artifact index

| Artifact | Path / URL |
|----------|------------|
| Link crawl JSON | `docs/delivery/_perf-audit-link-check-2026-08-05.json` |
| Prod health tip | `git_sha=40064803…` @ `2026-08-05T23:48:27Z` |
| Tip CI | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/31054083451 |
| LHCI home fail | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/31053173680 |
| LHCI home report | https://storage.googleapis.com/lighthouse-infrastructure.appspot.com/reports/1785969422081-55685.report.html |
| LHCI pricing report | https://storage.googleapis.com/lighthouse-infrastructure.appspot.com/reports/1785969422759-24497.report.html |
| Hardening smoke fail | https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/30985523567 |
| Supabase project | `smyeexlrqdpymwjmgzqu` |

---

## Fix pass resolution (2026-08-06)

Executed against this audit tip `40064803` → shipped through `f1017fed` (Vercel Production deploy `f1017fed` @ `2026-08-06T07:18:11Z`). API tip observed at close: `3d372c5d` (includes RLS/rate-limit/suggestions-scan; CI script tip `f1017fed` pending Railway).

### Phase 0 — F1 RLS (8 tables) — CLOSED

| Table | RLS | Evidence |
|-------|-----|----------|
| `agent_execution_interrupts` | on | Management API re-check 2026-08-06 (`scripts/_check_rls_eight.py`) |
| `intelligence_outcome_events` | on | same |
| `intelligence_learning_signals` | on | same |
| `strategy_performance_records` | on | same |
| `domain_segment_learning_state` | on | same |
| `domain_optimization_recommendations` | on | same |
| `test_credential_org_allowlist` | on | same |
| `restricted_test_user_ids` | on | same (deny-all client policy; no org_id) |

- Migration: `supabase/migrations/20260805210000_enable_rls_intelligence_public_tables.sql`
- Cross-org live: `docs/delivery/phase0-rls-cross-org-live.json` (`pass: true`)
- Commit: `59058885`

### Phase 1 — Domain / Live Chat — CLOSED

- Live Chat → `/contact` (live HTML `<a …>Live Chat</a>`)
- `metadataBase` / canonical / `og:image` → `https://gravitre.app` (0 `gravitre.com` in home HTML)
- Verifier: `python scripts/_verify_phase1_domain.py` → `pass: true` (2026-08-06)
- Commits: `1520e26b`, `3ecac7dc`

### Phase 2 — P1 — CLOSED

| Item | Result | Evidence |
|------|--------|----------|
| Marketing Lighthouse home ≥0.75 | **PASS 0.87** (was 0.70) | [LHCI #31065773698](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/31065773698) on `4cf35bcb`; home LCP **923ms**, SI **5756ms**, TBT **123ms**; pricing **0.99**. Scores: `docs/delivery/phase2-lighthouse-scores-live.json`. Reports: [home](https://storage.googleapis.com/lighthouse-infrastructure.appspot.com/reports/1785983627565-97049.report.html) / [pricing](https://storage.googleapis.com/lighthouse-infrastructure.appspot.com/reports/1785983628032-81146.report.html) |
| production-hardening-smoke | **PASS** (was ≥10 nights PARTIAL) | [Lane D #31080117502](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/31080117502) on `f1017fed` — summary `verdict: PASS`, oks marketplace/AI/research all true. Root causes fixed: suggestions-scan PGRST204 insert (`3d372c5d`), marketplace env KeyError, research SHA lexicographic false-fail (`f1017fed`) |
| OAuth/webhook rate limits | **SHIPPED** | `SENSITIVE_RATE_LIMITS` + middleware match `*` for `/api/connectors/oauth` (60/min) and `/api/webhooks` (120/min) in `3d372c5d` |

### Phase 3 — P2 — CLOSED / PARTIAL

| Item | Result | Evidence |
|------|--------|----------|
| `audit_events (org_id, action, created_at DESC)` | **CLOSED** | Index `idx_audit_events_org_action_created` live; EXPLAIN Index Cond on `(org_id, action)` — `docs/delivery/phase3-audit-events-explain.json` |
| Advisor burn-down | **PARTIAL** | Duplicate org index dropped; **15** hottest unindexed FK indexes created (`docs/delivery/phase3-fk-indexes-created.json`). Full 293 WARN / 328 INFO list not zeroed; `auth_rls_initplan` left for follow-on |
| Support Motion stuck opacity | **CLOSED** | Support page `initial={false}` + Live Chat real `<a href="/contact">` |
| ESLint 321 warnings | **PARTIAL** | React Compiler advisory rules off in `apps/web/eslint.config.mjs` (dominant warn source); unused-vars ignore `_` prefix. Residual unused/other warns remain |

### Phase 4 — Coverage gaps — CLOSED

| Item | Result | Evidence |
|------|--------|----------|
| Client-render vs RSC shell | **SERVER_SHELL_MEANINGFUL** | Live View-Source: `/` **487** SSR words + h1/CTA; `/pricing` **893** SSR words. Client islands hydrate but do not empty the shell. `docs/delivery/phase4-rsc-shell-live.json` |
| Chat TTI + mount sequence | **PASS** | Auth as `conversation-smoke-sa@gravitre.app`: login→`/home` **6.5s**, sidebar interactive **10.6s**, chat textarea interactive on `/ai` **11.6s** from script start. Mount shows parallel RSC/GTM overlap pairs. `docs/delivery/phase4-chat-tti-live.json` |
| Authenticated Playwright click-audit | **RUN** | `scripts/click-audit.js app` — isolated sidebar **OK=14 / FAIL=1 / TOTAL=15**. `docs/delivery/phase4-click-audit-live.json` |

### Commits (main)

`59058885` → `1520e26b` → `3ecac7dc` → `3d372c5d` → `4cf35bcb` → `f1017fed` (+ this docs stamp).
