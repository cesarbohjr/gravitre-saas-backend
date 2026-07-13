# Master Project — Knowledge Packages + Intelligence Packs + Connector Categories

**Status:** Phase 1 **DONE** (2026-07-13) — DB + HTTP evidence linked below.  
**Date:** 2026-07-13  
**Pipeline canon (all sources):**  

`source → connector → normalization/cache → Business Knowledge Graph → Signal Engine → Organizational Memory → department agent → workflow + outcome tracking`

Every category (customer-owned / Gravitree-managed / BYO) enters at **source** and differs only in **source ownership** and **auth_mode**. No shortcuts past KG, Memory opt-in, or write approval gates.

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
| Licensing / data-governance owner | **LOCKED — Cesar Bohorquez Jr.** (sole owner, same as STA-312). Covers PII-embedding **and** Crunchbase / PDL / OpenCorporates-commercial / CIS Controls licensing sign-off. |
| Phase 5 ML | **HELD** — see placeholder below (full prompt not written to docs/delivery) |

---

## Phase 1 commitments (2026-07-13)

- **`needs_connection` stubs are in Phase 1** — not deferred. Template install must show staged connectors before OAuth/API-key; Phase 1 is not Done without this.
- **OpenCorporates:** build shared `gravitree_managed` client + catalog plumbing; **activation blocked** until Cesar confirms commercial license (`OPENCORPORATES_LICENSE_CONFIRMED` / equivalent). Same pattern as Crunchbase/PDL stop-line: code may exist, **live tenant enablement may not**.
- **Contact-level stop-line:** Crunchbase + PDL stay behind governance/activation gates; no KG/Memory writes.
- **Scope this pass:** public gravitree sources (FRED, SEC, World Bank, OECD) + `auth_mode` + BYO fail-closed tests + stub template install + gated OC/NVD/CISA scaffolding.

### Phase 1 closure evidence (DONE)

| Layer | Result | Artifact |
|-------|--------|----------|
| Code + unit | 15 PASS | `backend/tests/intelligence_packs/` |
| Prod migration Option A | Applied (pipedrive retained) | `docs/delivery/phase1-migration-preflight.md` |
| DB-side stub staging | PASS (7 needs_connection, 0 live) | `docs/delivery/phase1-needs-connection-stub-live.json` |
| **HTTP API stub staging** | **PASS** on tip `8df5f07e` — GET templates 200; POST executive + BYO install 200; 7 stubs `needs_connection`; 0 live; cleaned up | `docs/delivery/phase1-needs-connection-stub-http-live.json` |
| Deploy | Railway prod `git_sha=8df5f07e783d6c84181e7dd27fc581ce9bda7b7e` | `/health` |

**Phase 1 = DONE** only with both DB and HTTP rows above. One layer alone was PARTIAL (per FAST-mode lesson).

### Phase 5 placeholder

Phase 5 (ML/predictive layer) — scoped and reviewed in conversation, **held** pending outcome-data volume and governance re-review; revive from chat when Phase 0–4 are live-verified — do not execute a stale docs prompt.

---

## What this master project includes

### A. Connector categories (framework)
Three modes as **one** `auth_mode` enum on catalog metadata — not three codebases:

| `auth_mode` | Meaning | Examples |
|-------------|---------|----------|
| `customer_owned` | Tenant credentials only | HubSpot, Apollo (default) |
| `gravitree_managed` | Platform keys; tenant never sees secret | FRED, SEC, World Bank, OECD, NVD, CISA KEV, OpenCorporates (if commercial) |
| `byo_required` | Customer must bring their own subscription; **fail closed**; **never** substitute Gravitree key | ZoomInfo, LinkedIn Sales Navigator |

**Hard rule (test-enforced):** BYO connectors have no shared-key path.

### B. Intelligence packs (build order — original scope)
1. **Executive** first (public/aggregate)  
2. **MSP** second (NVD/CISA + curated docs; CIS deferred)  
3. **Sales** third (Crunchbase/hiring; Memory/KG gated)

Packs are **marketplace-installable demos**: agents + workflows + connectors + knowledge wiring + bounded agent context allowlists — production-ready customer demos, not vapor UI.

### C. Pipeline (same funnel for all)
See stage reality table below. Phase 2 builds **minimum real** KG/signal wiring for cleared sources only — not the full aspirational engine.

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

### Phase 1 — Catalog `auth_mode` + BYO fail-closed + gravitree sources (public first)
Order: FRED/SEC/WB/OECD → OpenCorporates/NVD/CISA → confirm Apollo `customer_owned` → ZoomInfo/LI Sales Nav **tests first** → PDL/Crunchbase last (stop at cache until governance owner clears).  
Marketplace category template: Install pre-stages connectors as needs-connection; **no** auto-auth.

### Phase 2 — Pipeline wiring (cleared sources only)
Durable cache + provenance → KG (where allowed) → minimal signal detection → Memory **only** via existing opt-in gate.

### Phase 3 — Bounded agent training
Catalog allowlists of packs/sources per agent; server-side deny cross-pack retrieval. No autonomous learning.

### Phase 4 — Workflow nodes + live E2E
ICP/enrich/signal lookup nodes (read) + any HubSpot/Apollo write still through approval gate.  
Acceptance: ICP → enrich → Apollo discover → HubSpot list create → live `tool.invoke.completed` + `result_url`.

### Pack track (parallel after Phase 1 skeleton)
Executive → MSP → Sales per original build order; OpenCorporates client = shared module as previously designed.

### Phase 5 — HELD (do not start; full prompt not filed)

See **Phase 5 placeholder** under Product decisions. Do not expand into a standalone delivery prompt until preconditions are met.

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
~~Go Phase 1~~ — **in progress** (stubs + auth_mode + public sources + BYO tests).
