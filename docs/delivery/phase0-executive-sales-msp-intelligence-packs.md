# Phase 0 — Executive / Sales / MSP Intelligence Packs

**Date:** 2026-07-13  
**Mode:** Investigation only (no pack code)  
**Precondition:** Five foundation gates re-smoked on tip `716e9f44` — overall **PASS** (`docs/delivery/foundation-five-gates-tip-resmoke.json`).

---

## Precondition evidence (tip-fresh)

| Gate | Result | Artifact |
|------|--------|----------|
| Item 6 Apollo omit-name | PASS — `inferred_fields: ["name"]`, `awaiting_confirm` | `reaudit-item6-omit-name-live.json` |
| Item 7 Trace D escalation | PASS — `write_tool_from_simple` audit `8f5895cf…` | `routing-trace-d-force.json` |
| Item 8 chips + assumption_notes | PASS | `reaudit-item8-chips-live.json` |
| STA-317 apply gate | PASS — apply → `awaiting_confirm`, confirm → `tool.invoke.*` | `sta317-apply-confirm-live.json` |
| actor_id on invoke | PASS — non-null UUID on requested/completed | `audit-actor-id-oauth-invoke-verify.json` |

Prod SHA: `716e9f4476dab25a4f12863f549929594c02ccaf`

---

## A. Marketplace Pack Framework reuse

**Finding:** A working `intelligence_pack` framework exists (catalog → seed → install → agent knowledge assignments). **Sales** and **MSP** catalog entries already exist as connector/BYO assignment templates — not Gravitre-managed API lookups. There is **no** Executive or Prospect intelligence pack asset.

**Evidence:**
- `backend/app/marketplace/intelligence_packs/catalog.py` — 4 specs including `sales-intelligence-pack`, `msp-intelligence-pack`
- `backend/app/marketplace/intelligence_packs/install.py`
- `backend/app/marketplace/seed_catalog.py` — `_intelligence_packs()`
- Live: `docs/delivery/part-d-p5-live-trace.json` (`support-intelligence-pack`)

**Reuse verdict:**
- **Yes** — register Executive (and evolve Sales/MSP) as `intelligence_pack` catalog assets for marketplace install/UI.
- **No** — FRED/SEC/World Bank/OECD/OpenCorporates/NVD/CISA shared lookup layer does **not** exist; needs new source modules, cache, usage logging, and credential consumption patterns.

---

## B. Plan-tier gating

**Finding:** Three layers today: (1) platform subscription via `entitlement_service`, (2) paid marketplace asset entitlements (Stripe one-time), (3) agent/workflow plan limits. Intelligence packs currently seed as **free** and skip agent/workflow plan-limit checks. Install is **per-agent** (`agentId`), not org-wide Gravitre-managed enable.

**Evidence:** `backend/app/billing/entitlement_service.py`, `backend/app/marketplace/entitlements.py`, `backend/app/marketplace/pack_pricing.py` (department packs only), `backend/app/marketplace/service.py`.

---

## C. GIE / shared intelligence reality-check

**Exists:** Company intelligence orchestrator, outcome learning, domain retrieval, `external_knowledge_service` (Wikipedia/PubMed/SEC with hardcoded User-Agent), in-process dedup cache, connector rate limits.

**Missing for this program:** Shared durable cache, per-request usage logs, source registry for pack APIs, clients for FRED / World Bank / OECD / OpenCorporates / NVD / CISA KEV.

**Evidence:** `backend/app/services/external_knowledge_service.py`, `company_intelligence_orchestrator.py`, `platform_intelligence_dedup.py`. No `knowledge_pack_cache` / `intelligence_usage_logs` tables in repo.

---

## D. Catalog / schema fit

**Exists:** `marketplace_assets` / `marketplace_installs` / entitlements, `agent_knowledge_assignments` / `agent_knowledge_references`, `org_intelligence_snapshots`, learning signals.

**Proposed but absent:** `intelligence_pack_sources`, `external_entities`, `external_signals`, `knowledge_pack_cache`, `intelligence_usage_logs`.

**Fit:** Mostly-read Gravitre-managed sources require **new** schema + clients. SEC has a partial read path only.

---

## E. Prospect / governance precedent

No “Prospect Intelligence Pack” in repo. Closest: Wave C intelligence packs (reference-only provenance) + **STA-312 Option B** Memory gate (opaque tokens; org opt-in default off).

**Rule for Sales pack:** Do not persist Crunchbase/hiring/funding signals into Organizational Memory / Knowledge Graph without named data-governance owner sign-off (same bar as STA-312).

---

## F. Monetization — DECIDED (b)

**Signed off 2026-07-13: (b) standalone pack subscriptions.**

| Signal | Meaning |
|--------|---------|
| ~~(a) Bundled~~ | Not selected |
| **(b) Standalone** | Packs sold as paid add-on subscriptions; marketplace entitlements + usage logging; no Stripe charge wiring until concrete SKUs/prices |

Suggested list-price ranges in the build prompt remain product-owned (not encoded as Stripe prices yet).

---

## G. Human-only credentials (do not create)

Agent builds code that consumes these gracefully when absent/invalid — humans add to Railway:

- `FRED_API_KEY`, `FRED_BASE_URL`
- `SEC_BASE_URL`, `SEC_USER_AGENT` (hard config error if missing/malformed)
- `WORLDBANK_BASE_URL`, `OECD_BASE_URL`
- `OPENCORPORATES_API_TOKEN`, `OPENCORPORATES_BASE_URL`
- `CRUNCHBASE_API_KEY`, `CRUNCHBASE_BASE_URL`
- `NVD_API_KEY`, `NVD_BASE_URL`
- `CISA_KEV_URL`
- `HIRING_SIGNALS_ENABLED`, `FUNDING_SIGNALS_ENABLED`
- `MSP_INTELLIGENCE_ENABLED`, `BENCHMARKS_SOURCE`

None present in `backend/.env.example` today. SEC currently uses a hardcoded User-Agent — Phase 1 should move to `SEC_USER_AGENT`.

---

## H. Risks / blockers before Phase 1 code

| Item | Severity | Note |
|------|----------|------|
| No Gravitre-managed lookup infra | High | Build shared `intelligence_packs/{executive,shared}/` in Phase 1 |
| Existing Sales/MSP packs are connector-assignment, not API packs | High | Extend carefully; don’t confuse with new source modules |
| Source-type mismatches in current catalog | High | Some `source_type` values not in `KNOWLEDGE_SOURCE_TYPES` |
| Monetization model unsigned | High | Blocks billing; not source clients |
| OpenCorporates commercial vs standard license | High (legal) | Flag before redistribution |
| Crunchbase Basic vs Enterprise | High (legal) | Hold Sales pack enablement |
| CIS Controls redistribution | High (legal) | Defer ingestion |
| No LinkedIn / unlicensed job scrape | Absolute | Hiring signals = customer URLs/RSS only in v1 |
| Memory/KG persistence for Sales signals | Medium | STA-312-class sign-off |

---

## Sequencing recommendation (unchanged)

1. **Executive** first (public/aggregate sources)  
2. **MSP** second (NVD/CISA + curated docs; CIS deferred)  
3. **Sales** third (Crunchbase licensing + Memory gate)

---

## Decisions needed from you before Phase 1 / Phase 3

1. **Monetization:** (a) bundled into plan tiers, or (b) standalone paid subscriptions per pack?  
2. **Licensing owner:** Who reviews OpenCorporates / Crunchbase / CIS Controls (named contact, like STA-312 for data governance)?

Phase 1 code may proceed on Executive sources + shared infra **after** you say go — without waiting on (1) for usage **logging**, but **with** (1) blocked for any charge wiring.

---

## Product decision — Monetization (2026-07-13)

**Choice: (b) standalone pack subscriptions.**

- Executive / Sales / MSP Intelligence Packs are sold as **standalone paid subscriptions** (not bundled into Node/Control/Command as the sole access model).
- Platform plan may still be a prerequisite for using the product, but pack access/pricing is **à la carte per pack** (or a multi-pack bundle SKU if product later defines one).
- Engineering implications:
  - Prefer marketplace **paid entitlement** patterns (`marketplace_asset_entitlements` / Stripe) over “included in tier” gates.
  - Build **usage logging** in Phase 1+ so subscription metering/quotas can attach later.
  - **Do not** implement Stripe price IDs / subscription charge wiring until product supplies concrete prices and SKUs (prompt suggested ranges only: Executive $99–199/mo, Sales $149–299/mo, MSP $149–299/mo, bundle $399–599/mo).
- Still open: **licensing owner** (decision #2) before Sales enablement / CIS / OpenCorporates redistribution.
