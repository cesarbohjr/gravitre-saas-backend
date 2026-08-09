# Master Project — Knowledge Packages + Intelligence Packs + Connector Categories

**Status:** Phase 1 **DONE**. Phase 1.5 **DONE**. Phase 3 **DONE**. Pack track Executive→MSP→Sales **DONE** (Phase 4 PARTIAL). Phase 5 ML v1 **shipped**. **12-pack vision Phase 0 audited** (2026-07-14) — extend program, do not replace.  
**Date:** 2026-07-14  
**Pipeline canon (all sources):**  

`source → connector → normalization/cache → Business Knowledge Graph → Signal Engine → Organizational Memory → department agent → workflow + outcome tracking`

Every category (customer-owned / Gravitre-managed / BYO) enters at **source** and differs only in **source ownership** and **auth_mode**. No shortcuts past KG, Memory opt-in, or write approval gates.

---

## Precondition (tip-fresh) — PASS

Re-smoked on prod tip `716e9f44` @ 2026-07-13T04:15Z — overall **PASS**.

| Gate | Result | Artifact |
|------|--------|----------|
| Apollo omit-name | PASS | `docs/delivery/reaudit-item6-omit-name-live.json` |
| Trace D escalation | PASS | `docs/delivery/routing-trace-d-force.json` |
| Chips + assumption_notes | PASS | `docs/delivery/reaudit-item8-chips-live.json` |
| integration-suggestions apply | PASS (STA-317 both-gate) | `docs/delivery/sta317-apply-confirm-live.json` |
| actor_id on invoke | PASS | `docs/delivery/audit-actor-id-oauth-invoke-verify.json` |

Rollup: `docs/delivery/foundation-five-gates-tip-resmoke.json`

---

## Product decisions (locked / open)

| Decision | Status |
|----------|--------|
| Monetization | **LOCKED (b)** — standalone pack subscriptions |
| Licensing / data-governance owner | **LOCKED — Cesar Bohorquez Jr.** (sole owner, same as STA-312). Covers PII-embedding **and** Crunchbase / PDL / OpenCorporates-commercial / CIS Controls **and** Finance banking/QB/Xero/NetSuite, HR HRIS/ATS/Payroll, Compliance PHI-vs-guidance scope **and** GSC raw search-query → Memory/KG (Marketing stop-line). |
| Phase 5 ML | **UNHELD** — v1 shipped (CRM outcomes + ranked heuristics). **Churn tip PASS**; **CF soft-rank tip PASS**; **CF matrix factorization tip PASS** 2026-07-19 — `phase0-cf-churn-ml.md` |
| 12-pack vision | **Phase 0 DONE** — `docs/delivery/phase0-twelve-pack-marketplace-vision.md`. Build order below. |

---

## Phase 1 commitments (2026-07-13)

- **`needs_connection` stubs are in Phase 1** — not deferred. Template install must show staged connectors before OAuth/API-key; Phase 1 is not Done without this.
- **OpenCorporates:** build shared `gravitre_managed` client + catalog plumbing; **activation blocked** until Cesar confirms commercial license (`OPENCORPORATES_LICENSE_CONFIRMED` / equivalent). Same pattern as Crunchbase stop-line: code may exist, **live tenant enablement may not**.
- **Contact-level stop-line:** Crunchbase stays behind governance/activation gates. **PDL (2026-07-15 Cesar clear):** BYO tenant API key allowed on Sales/Prospecting/Marketing packs (`auth_mode=byo_required`); **no** contact-level Memory/KG writes without a separate clear.
- **GSC query stop-line (Marketing #6):** raw Search Console query strings (`searchAnalytics.query` row-level query text) must **not** be written to Organizational Memory / Knowledge Graph without Cesar governance sign-off (STA-312 pattern, applied preemptively). Aggregate/rollup metrics (clicks, impressions, position by URL) are **not** gated and may flow through the pack signal pipeline. See `docs/delivery/marketing-phase0-gsc-oauth.md`.
- **Scope this pass:** public gravitre sources (FRED, SEC, World Bank, OECD) + `auth_mode` + BYO fail-closed tests + stub template install + gated OC/NVD/CISA scaffolding.

### PDL BYO packaging (2026-07-15)

Cesar authorized People Data Labs as **BYO** on Sales, Prospecting, and Marketing intelligence packs (dashboard.peopledatalabs.com). Live `pdl.person.enrich` / `pdl.company.enrich` use the org API key only. Memory/KG contact persistence remains gated.

### Phase 1 closure evidence (DONE)

| Layer | Result | Artifact |
|-------|--------|----------|
| Code + unit | 15 PASS | `backend/tests/intelligence_packs/` |
| Prod migration Option A | Applied (pipedrive retained) | `docs/delivery/phase1-migration-preflight.md` |
| DB-side stub staging | PASS (7 needs_connection, 0 live) | `docs/delivery/phase1-needs-connection-stub-live.json` |
| **HTTP API stub staging** | **PASS** on tip `8df5f07e` — GET templates 200; POST executive + BYO install 200; 7 stubs `needs_connection`; 0 live; cleaned up | `docs/delivery/phase1-needs-connection-stub-http-live.json` |
| Deploy | Railway prod `git_sha=8df5f07e783d6c84181e7dd27fc581ce9bda7b7e` | `/health` |

**Phase 1 = DONE** only with both DB and HTTP rows above. One layer alone was PARTIAL (per FAST-mode lesson).

### Phase 1.5 — Shared ingestion plumbing (DONE)

**Full scope:** `docs/delivery/phase1.5-shared-ingestion-plumbing.md`  
**Migration preflight:** `docs/delivery/phase1.5-migration-preflight.md` — applied on prod.
**Live evidence:**
- Service: `docs/delivery/phase1.5-shared-plumbing-live.json` (PASS @ 2026-07-13T07:52:55Z)
- HTTP: `docs/delivery/phase1.5-shared-plumbing-http-live.json` (PASS @ 2026-07-13T08:31:23Z on tip `8cb6c39e`, http_status 200)
**Ownership boundaries (at Phase 1.5 close):** agent/tool/router was deferred to Phase 3; CRM emit was a Phase 5 precondition gap. **Superseded:** Phase 3 DONE + HubSpot CRM emit wired (see below).

**Diagnosis:** Pack/install/`auth_mode` is global; Phase 1.5 closed the shared cache→normalize→KG→signal path. Phase 3 wires that path into `invoke_tool` for FRED/NVD.

| Gate | Bar |
|------|-----|
| A — Same shared functions | ONE `cache_get`/`cache_set`, ONE `normalize_source_result` dispatcher (mappers plugged in), ONE `write_external_entity_with_provenance`, ONE PackSignalDefinition registration path — FRED+NVD as registrations, not copies |
| B — Third-source proof | World Bank = mapper + PackSignalDefinition only; **zero** changes to shared cache/KG-write/registry internals — else not DONE |
| C — Live prod | Cache row + KG/provenance write + signal registration for **FRED, NVD, and World Bank** on Railway tip (not local-only) |
| D — Ownership fields in artifact | Historical: deferred_to_phase_3 / flagged_phase_5_precondition_gap |

**Phase ownership (updated 2026-07-13):**

| Concern | Owns | Status |
|---------|------|--------|
| Shared cache / normalize / KG write / PackSignalDefinition | **Phase 1.5** | DONE |
| Agent / tool / router so chat can call FRED/NVD live | **Phase 3** | **DONE** — `fred.series.get` / `nvd.cve.get` via `invoke_tool` |
| CRM outcome emit production callers | **Phase 5 precondition** | **Wired** (HubSpot first caller); Phase 5 ML still HELD |

### Phase 3 — FRED/NVD invoke_tool (DONE)

**Evidence:** `docs/delivery/phase3-fred-nvd-invoke-live.json` — PASS on tip `52205362` via `POST /api/intelligence-packs/tools/invoke-smoke`.

| Action | cache | entity | signal |
|--------|-------|--------|--------|
| `fred.series.get` | `67b1129a-…` | `1e80b973-…` | `016360df-…` |
| `nvd.cve.get` | `1fe8c30b-…` | `a58a867d-…` | `d2a2837c-…` |

Tools registered in `_TOOL_REGISTRY` + ToolRegistry curated specs (`fred_get_series`, `nvd_get_cve`). Executors call Phase 1.5 `run_shared_ingestion` only. Gravitre activate: `POST /api/connectors/{id}/activate-gravitre`.

### Phase 5 — UNHELD (v1 scope filed 2026-07-14)

Cesar lifted the hold. Full CF/collaborative-filtering recommender remains deferred (`ml-stack-phase0-findings.json`: heuristic first).

| Slice | Scope | Status |
|-------|--------|--------|
| **5.0 Volume** | Real HubSpot closed won/lost → `crm_recommendation_outcomes` (webhook + optional backfill) | In progress |
| **5.1 Learning bridge** | On CRM ingest, mirror `crm_won`/`crm_lost` → `intelligence_outcome_events` | Shipped (code) |
| **5.2 Outcome-ranked heuristics** | `GET /recommendations/heuristics` soft-ranks via `recommendation_quality_engine` (advisory-only; never drops cards) | Shipped (code) |

**Non-goals for v1:** collaborative filtering, auto-execute from cards, GNN/forecasting, `deal_loss_scorer` until ≥25 labeled deals.

**CRM outcome emit (precondition):** HubSpot webhook path calls `ingest_crm_recommendation_outcome` for explicit `dealstage` → `closedwon`/`closedlost` only. Soft-dedupe on (org, connector, external_id, outcome_type).

**Apollo:** BYO tenant keys — platform smoke does not wait on Apollo plan upgrade (`docs/delivery/apollo-plan-upgrade-human.md`).

**Evidence:** `docs/delivery/crm-outcome-emit-live.json`; backfill `docs/delivery/phase5-hubspot-crm-outcomes-backfill-live.json` (when run).

---

## What this master project includes

### A. Connector categories (framework)
Three modes as **one** `auth_mode` enum on catalog metadata — not three codebases:

| `auth_mode` | Meaning | Examples |
|-------------|---------|----------|
| `customer_owned` | Tenant credentials only | HubSpot, Apollo (default) |
| `gravitre_managed` | Platform keys; tenant never sees secret | FRED, SEC, World Bank, OECD, NVD, CISA KEV, OpenCorporates (if commercial) |
| `byo_required` | Customer must bring their own subscription; **fail closed**; **never** substitute Gravitre key | ZoomInfo, LinkedIn Sales Navigator |

**Hard rule (test-enforced):** BYO connectors have no shared-key path.

### B. Intelligence packs (build order — original scope)
1. **Executive** first (public/aggregate)  
2. **MSP** second (NVD/CISA + curated docs; CIS deferred)  
3. **Sales** third (Crunchbase/hiring; Memory/KG gated)

Packs are **marketplace-installable demos**: agents + workflows + connectors + knowledge wiring + bounded agent context allowlists — production-ready customer demos, not vapor UI.

### C. Pipeline (same funnel for all)
See stage reality table below. **Phase 1.5** generalizes the shared cache → normalize → KG → PackSignalDefinition path (FRED + NVD + World Bank proof). Later pack work uses that path; it must not invent parallel plumbing.

### D. Explicitly out of this pass
- Stripe subscription charge wiring (usage logging only until SKUs)  
- Full autonomous learning / Phase 5 ML  
- CIS Controls ingest, licensed benchmarks, hiring Phase 2 provider  
- LinkedIn scrape under any framing  

---

## Phase 0 findings — Connector categories + pipeline

### 1. Marketplace “category template” install
**Gap.** Install is **per asset**. Department packs **block** until required connectors are already `active` — they do **not** pre-stage “needs connection” stubs.  
`marketplace_pack_items` = browse metadata only; no cascade connector create.  
**Build needed:** template Install → N connector rows in `needs_connection` (or equivalent) without auto-auth.

Evidence: `backend/app/marketplace/service.py` `validate_connectors_for_asset`, `connectors/repository.py` `create_connector` (always `active`).

### 2. OAuth vs API-key UI
**Mostly reusable.** Connect wizard already branches `oauth` / `apiKey` / `webhook` (`apps/web/app/connectors/page.tsx`, `apps/web/lib/connectors.ts`).  
**Gaps:** detail page is API-key-centric; no catalog `auth_mode` field yet (only `authType` / `credentialModel`).

### 3. Knowledge-base wiring after connect
**Mostly new for end-to-end.**  
Exists: intelligence pack → `agent_knowledge_assignments`; department pack → `rag_sources` pending_upload; manual Sync Knowledge for some vendors.  
Missing: post-OAuth/API-key step that auto-binds connector → RAG/assignment scope for pack install. Several intelligence pack `source_type` values mismatch `KNOWLEDGE_SOURCE_TYPES`.

### 4. Pipeline stage reality

| Stage | Verdict | Notes |
|-------|---------|-------|
| Source | PARTIAL | SEC/Wikipedia/PubMed partial; FRED/WB/OECD/OC/NVD/CISA missing |
| Connector | REAL | OAuth + API key + invoke_tool + write gates |
| Normalization + cache | PARTIAL | Per-vendor `NormalizedResult`; in-process dedup only — need durable TTL cache + provenance |
| Business Knowledge Graph | PARTIAL→LIVE | `org_entity_relationships` + builder/query live; GNN aspirational |
| Signal Engine | PARTIAL | `BusinessSignalsEngine` / event intelligence — no unified `external_signals` pack engine |
| Organizational Memory | PARTIAL | STA-316 Option B + opt-in default off — **reuse this path only** for pack data |
| Department agent | REAL | Pack install creates agents; tool permissions exist — extend to pack-source allowlists |
| Workflow + outcomes | PARTIAL | Approval gate REAL; `crm_recommendation_outcomes` schema live, emit path not wired |

ML stack Phase 0 (`docs/delivery/ml-stack-phase0-findings.json`): Recommendation ML not built; Memory Option B authorized; GNN OOS.

---

## Sequenced delivery plan

### Phase 1 — Catalog `auth_mode` + BYO fail-closed + gravitre sources (public first) — DONE
Order: FRED/SEC/WB/OECD → OpenCorporates/NVD/CISA → confirm Apollo `customer_owned` → ZoomInfo/LI Sales Nav **tests first** → PDL/Crunchbase last (stop at cache until governance owner clears).  
Marketplace category template: Install pre-stages connectors as needs-connection; **no** auto-auth.  
Evidence: DB + HTTP stub artifacts above.

### Phase 1.5 — Shared ingestion plumbing — DONE
Durable cache + one normalize dispatcher + one provenance KG write + one PackSignalDefinition path. Proven with FRED + NVD + World Bank (service + HTTP).  
Spec: `docs/delivery/phase1.5-shared-ingestion-plumbing.md`.  
Artifacts: `docs/delivery/phase1.5-shared-plumbing-live.json`, `docs/delivery/phase1.5-shared-plumbing-http-live.json`.  
Ownership: agent/tool/router = Phase 3; CRM outcomes = Phase 5 precondition gap.

### Phase 2 — Pack-facing use of shared path (after 1.5)
Memory **only** via existing opt-in gate; pack-specific signal *content* on top of PackSignalDefinition — **not** new per-source cache/KG plumbing.

### Phase 3 — Bounded agent training + tool/router wiring — DONE (FRED/NVD invoke)
`fred.series.get` / `nvd.cve.get` registered and live-proven via invoke_tool smoke. Curated chat tools `fred_get_series` / `nvd_get_cve`. Catalog allowlists via permitted_tools + scopes. World Bank chat wiring can follow same pattern later. No autonomous learning.

### Phase 4 — Workflow nodes + live E2E — PARTIAL (**accepted 2026-07-13**)
Spine: `hubspot.lists.create` registered + vendor-cataloged; live smoke created list_id `9` with `result_url`.  
Apollo discover on smoke org is **plan-limited** (`apollo.people.search` 403 free plan) — accepted as PARTIAL; upgrade/master API key required for full chain.  
Artifacts: `docs/delivery/phase4-sales-workflow-e2e-live.json`, `docs/delivery/phase4-executive-pack-live.json`.

### Pack track — Executive DONE; MSP DONE; Sales DONE
**Executive** — **DONE** (`phase4-executive-pack-live.json`).  
**MSP** — **DONE** (`phase4-msp-pack-live.json`). CIS deferred; **CISA invoke follow-on:** `cisa_kev.feed.get`.  
**Sales** — **DONE** (`phase4-sales-pack-live.json`): Pipeline Analyst, HubSpot/Apollo stubs, `hubspot.pipelines.list` read-only. Crunchbase/PDL/KG/Memory gated; BYO ZoomInfo/LI fail-closed; no OpenCorporates enable.  
**SEC EDGAR research** — `sec_edgar.filings.search` (platform `SEC_USER_AGENT`).  
OpenCorporates stays activation-gated. Phase 5 ML **UNHELD** (v1: volume + bridge + ranked heuristics).

### Phase 5 — UNHELD (see filed v1 table under Product decisions / Phase 5 section)

CRM outcome **emit path wired** (HubSpot); backfill + learning bridge + outcome-ranked heuristics are the v1 path. CF/ML deferred until usage data at scale.

---

## Production-demo definition of done (customer-facing)

1. Prebuilt agents (scoped)  
2. Prebuilt workflows (gated writes)  
3. Connectors in correct `auth_mode` (connect step works; BYO fails closed)  
4. Knowledge wiring (assignments + RAG where applicable)  
5. Live governed write proof (approval → invoke → result_url)  
6. Usage logging suitable for standalone subscription metering later  

---

## Human-only (not agent)

API accounts/keys for FRED, SEC_USER_AGENT, OpenCorporates commercial token, NVD, Crunchbase, BYO customer keys, OAuth apps — humans add to Railway. Set `OPENCORPORATES_LICENSE_CONFIRMED=true` only after Cesar signs commercial terms.

---

## Immediate asks

~~Licensing owner~~ — **locked to Cesar** (STA-312 scope extended).  
~~Go Phase 1~~ — **DONE** (DB + HTTP stub evidence).  
~~Scope Phase 1.5~~ — **DONE** (`docs/delivery/phase1.5-shared-ingestion-plumbing.md`).  
~~Phase 3 FRED/NVD invoke~~ — **DONE** (`docs/delivery/phase3-fred-nvd-invoke-live.json`).  
~~CRM outcome first caller~~ — **wired** (`docs/delivery/crm-outcome-emit-live.json`; Phase 5 volume via webhook + backfill).  
~~Executive Intelligence Pack~~ — **DONE** (`docs/delivery/phase4-executive-pack-live.json`).  
~~Phase 4 full E2E~~ — **PARTIAL accepted** (Apollo free-plan blocker; HubSpot list create live).  
~~MSP Intelligence Pack~~ — **DONE** (`docs/delivery/phase4-msp-pack-live.json`).  
~~Sales Intelligence Pack~~ — **DONE** (`docs/delivery/phase4-sales-pack-live.json`).  
**Pack track complete (Executive → MSP → Sales).** Phase 5 ML **UNHELD** — v1 volume/bridge/ranked heuristics.

**Follow-ons:**
- **CISA invoke** — `cisa_kev.feed.get` (+ Phase 1.5 mapper/signal) — DONE
- **SEC EDGAR research** — `sec_edgar.filings.search` (requires `SEC_USER_AGENT`) — DONE
- **Apollo plan upgrade** — **BYPASSED** (tenant BYO keys; `docs/delivery/apollo-plan-upgrade-human.md`)
- **NVD API key** — activated + Railway/local; MSP re-smoke PASS
- **Phase 5 v1** — HubSpot outcome volume + learning bridge + ranked heuristics — DONE (PR #118)
- **12-pack vision Phase 0** — `docs/delivery/phase0-twelve-pack-marketplace-vision.md` — DONE (no build yet)

---

## 12-pack Marketplace vision (absorbed 2026-07-14)

**Not a second program.** Same pipeline, auth_mode, Phase 1.5 shared ingestion, approval gate, notifications. Full Phase 0 tables: `docs/delivery/phase0-twelve-pack-marketplace-vision.md`.

### Locked pack order (after Executive → MSP → Sales)

| # | Pack | Status / gate |
|---|------|----------------|
| 1–3 | Executive, MSP, Sales | **DONE** |
| **3.5** | Shared Pack KPI + notify/result_url cohesion smoke on Executive | **DONE** — `docs/delivery/phase35-executive-cohesion-live.json` |
| 4 | Customer Success | **DONE** — `docs/delivery/phase4-customer-success-pack-live.json` (internal HubSpot; Zendesk staged) |
| 5 | Prospecting & Lead Scouting | **DONE** — `docs/delivery/phase4-prospecting-pack-live.json` (Apollo/HubSpot lists; search plan-limited) |
| 6 | Marketing | **DONE** — GSC OAuth PASS; SEMrush/Ahrefs BYO v1–v3 write executors + schemas; PackSignal + PackKpiPanel; install tip `docs/delivery/phase4-marketing-pack-live.json` (tip `0db6ddf0`); raw-query Memory/KG stop-line held |
| 7 | RevOps | **DONE** — catalog + install (`revops-intelligence-pack`); HubSpot pipelines/deals tip; Salesforce stub; Finance pack F3 unlocked separately; PackKpiPanel Reports tab; tip `docs/delivery/phase4-revops-pack-live.json` |
| 8 | AI Search | **DONE (UI-only)** — Cesar skip API (2026-07-18). Tip `phase4-ai-search-pack-live.json` (C+S2; UI scrape live OK @ 2026-07-17). Dual-BYO Ahrefs/Finseo API invoke **NOT RUN** (optional follow-on if keys provided) |
| 9 | Finance | **PARTIAL** — F3 unlock + scaffold; tip now asserts **4× staged stubs** (`stubCoverage`). `live_invoke_ok: false` — live Plaid/QB/Xero/NS **HOLD**. Evidence `docs/delivery/phase4-finance-pack-live.json` |
| 10 | HR & Talent | **PARTIAL** — H3 unlock + scaffold; tip asserts **4× staged stubs**. `live_invoke_ok: false` — live Workday/BambooHR/Greenhouse/Gusto **HOLD**. Evidence `docs/delivery/phase4-hr-talent-pack-live.json` |
| 11 | Compliance | **DONE (guidance only)** — `docs/delivery/phase0-compliance-intelligence-pack.md` + tip `phase4-compliance-pack-guidance.json`. PHI → **STOP**; no catalog/install/connectors this pass |
| 12 | Business Operating System | **DONE (rollup only)** — `docs/delivery/phase0-business-os-intelligence-pack.md` + `phase4-business-os-pack-rollup.json`. No new connectors; live UI rollup = Reports `PackKpiPanel` tabs |

### Cross-cutting UX (every pack from #4 onward)

1. One shared Pack KPI pattern (build once in 3.5) — `PackKpiPanel` + `GET /api/intelligence-packs/{id}/kpis`  
2. Signals/workflows → existing `emit_notification()` taxonomy  
3. External records → existing verified-output / `result_url`  
4. Prove on Executive first, then template CS  

**Manual agent pick (not pack-ordered):** [STA-321](https://linear.app/staqbot/issue/STA-321) — Assignments / Workflow builder / Swarm.

**Finance/HR connectors:** Cesar locked **F3** + **H3** (2026-07-15) for **unlock/scaffold**. Tip re-ran on health tip `cd056edf` — both **PARTIAL** (`live_invoke_ok: false`, `any_active_connector: false`).

### Live-activation HOLD (recorded 2026-07-16 — STA-312 pattern)

**Decision:** Hold. Do **not** authorize live Plaid Link / Gusto OAuth / QuickBooks (or other F3/H3) connection testing against the smoke org — even sandboxed test accounts, even read-only — until Cesar gives an **explicit separate** sign-off naming those live tests. Sandbox does not auto-clear governance for financial-account / employee PII-comp scopes.

F3/H3 remain: scaffolded, correctly gated, not live-tested, **PARTIAL**.

**2026-07-16 Cesar confirmation:** Live-activation left open / not approved inline. Explicit call required before anything moves on F3/H3 connects. Greenhouse CHECK-constraint fix is schema plumbing only — does **not** authorize live HR API connects.

**Greenhouse stub (2026-07-16):** FIXED — additive migration applied; smoke-org row `47ed6670-…` staged as `needs_connection` (HR template status; Zendesk uses `pending_auth` label). See `docs/delivery/phase4-hr-talent-pack-live.json` `greenhouse_stub`.

**Sales + Prospecting:** Both ship; Prospecting reuses Apollo/PDL/Crunchbase/BYO wiring — no duplicate clients.  

### Out of scope this pass

Compliance PHI live sources remain **STOP**. Finance/HR live OAuth remain **HOLD**. Business OS catalog install / Daily Briefing workflow optional follow-on (rollup closed 2026-07-18).

### Pack #8 closure (2026-07-18)

Cesar chose **skip API** — Pack #8 closed on UI tip evidence only. Dual-BYO live invoke remains optional: set `AHREFS_API_KEY` / `FINSEO_API_KEY` then `scripts/upsert-smoke-ai-search-byo-connectors.py`.

### Pack #9 / #10 scaffold hardening (2026-07-18)

No live OAuth. Install bundles return `stubCoverage` + stub IDs; tip smokes require 4× staged connectors (`needs_connection` / `pending_auth` class). Unit tests: `test_finance_pack.py`, `test_hr_talent_pack.py`, F3/H3 template cases in `test_auth_mode_and_stubs.py`. Live-activation HOLD unchanged.

**Tip re-smoke (2026-07-18):** Finance + HR both `pass: true`, `stub_coverage_ok: true`, `live_invoke_ok: false` against prod tip `9d1ae051…` — evidence in `phase4-finance-pack-live.json` / `phase4-hr-talent-pack-live.json`.

### Pack #11 Compliance guidance (2026-07-18)

Guidance + PHI stop-line locked in `docs/delivery/phase0-compliance-intelligence-pack.md`. Artifact `docs/delivery/phase4-compliance-pack-guidance.json` (`DONE_GUIDANCE_ONLY`). No `compliance-intelligence-pack` catalog/install. Build requires Cesar named clear; EHR/PHI sources stay **STOP**.

### Pack #12 Business OS rollup (2026-07-18)

Locked sequence **closed**. Spec `docs/delivery/phase0-business-os-intelligence-pack.md`; artifact `docs/delivery/phase4-business-os-pack-rollup.json` (`DONE_ROLLUP_ONLY`). No new connectors / no catalog install. Live rollup UX = Intelligence Reports multi-pack `PackKpiPanel`. Open holds (Finance/HR live, Compliance PHI, AI Search dual-BYO API) unchanged — not cleared by #12.

### CF / Churn ML start (2026-07-18)

**Both sequenced — churn first.** Spec `docs/delivery/phase0-cf-churn-ml.md`; artifact `docs/delivery/phase5-cf-churn-ml-start.json` (`CF_TIP_PASS`).

- Churn: labeled `churn_customer_signal` via `confidence_note` + `metric_value_after`. **PASS** — advisory HTTP 200 `trained:true` @ `2026-07-19T02:53:31Z` tip sha `77529f7f…` (`phase5-churn-ml-live.json`).
- CF v1: item-affinity soft-rank after heuristics / before dismiss; ≥50 interactions/30d gate. **PASS** — heuristics HTTP 200 `cfRanked:true` gate ready @ tip sha `9d5451a5…` (`phase5-cf-soft-rank-live.json`).
- CF MF: TruncatedSVD user×item (`cf_matrix_factorizer`). **PASS** — heuristics HTTP 200 `cfMethod=matrix_factorization` @ tip sha `c36f92d3…`; model `a194a993…` v1 deployed (`phase5-cf-matrix-factorization-live.json`).
