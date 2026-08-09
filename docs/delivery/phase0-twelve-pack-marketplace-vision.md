# Phase 0 — 12-Pack Marketplace Vision Reality Audit

**Date:** 2026-07-14  
**Mode:** Investigation only (no pack build code)  
**Parent program:** `docs/delivery/master-knowledge-intelligence-packs-program.md` (extended, not replaced)  
**Canvas:** `canvases/twelve-pack-phase0-audit.canvas.tsx`

Standing gates (`docs/ENGINEERING_STANDARDS.md`) unchanged. Prod evidence required for any Done claim.

---

## Clarifications (2026-07-14, pre–Phase 3.5)

### Finance / HR connector code — dormant, not live

Prod DB probe (`connectors` where type in quickbooks/xero/netsuite/plaid/workday/greenhouse/bamboohr/gusto):

- **1** QuickBooks row at `pending_auth`
- **0** usable (`active`/`healthy`/`connected`) for any of these vendors

So “code exists” = **pre-existing platform scaffolding** (OAuth + tool executors), same class as OpenCorporates: **dormant / unused until governance sign-off**. Not live for any tenant today. Stays gated like Sales contact-data sources (STA-312) until Cesar signs Finance and HR categories — **do not** treat as already-activated.

### Sales + Prospecting — both ship; reuse wiring

Both packs remain in the plan:

| Pack | Role |
|------|------|
| Sales Intelligence (#3, shipped) | Pipeline/CRM |
| Prospecting & Lead Scouting (#5) | Outbound lead gen |

Prospecting **reuses** Apollo/PDL/Crunchbase/ZoomInfo BYO connector + auth_mode wiring from the Sales/stop-line work — it must not re-implement those clients. New work is pack catalog/agents/workflows on top.

### Manual agent pick — tracked separately

Linear **[STA-321](https://linear.app/staqbot/issue/STA-321)** — Cross-cutting UX: remove manual agent selection from Assignments / Workflow builder / Swarm. Not tied to pack #4–#12 order.

---

## Verdict (one paragraph)

Gravitre already has the Marketplace Pack Framework, `auth_mode` catalog, Phase 1.5 shared ingestion/KG/signals, department-agent scoping, approval gate, and `emit_notification` taxonomy. The 12-pack vision is mostly **EXTEND** (rename/wire existing agents + orchestrate existing actions) plus a small set of **NEW** surfaces: Account Intelligence agent, AI Visibility agent, Compliance Agent, Google Search Console, compliance-doc sources, shared Pack KPI dashboard / Settings→Intelligence Packs / `intelligence_usage_logs`, and Churn Prediction as ML (held). Finance/HR/Compliance **live** connectors are governance-gated even where code stubs exist.

---

## 1. Agents

| Pack | Vision agent | Class | Evidence |
|------|--------------|-------|----------|
| Executive | Executive Advisor | EXTEND | `Executive Macro Analyst` — `catalog.py` / `executive_install.py` |
| Executive | Board Reporting | EXTEND | `cfo-agent` + board-reporting capability — `seed_catalog.py` |
| Sales | Pipeline Analyst | **REUSE** | Exact `Sales Pipeline Analyst` demo install |
| Sales | Deal Risk | EXTEND | `pipeline-forecast-agent` / Sales Pipeline Agent |
| Sales | Account Intelligence | **NEW** | Knowledge assignment placeholder only |
| Prospecting | Lead Scouting | EXTEND | `Lead Qualifier Agent` — not scouting |
| Prospecting | ICP Builder | EXTEND | `product-icp-strategist` |
| Marketing | SEO Agent | EXTEND | `seo-analyst` |
| Marketing | Campaign Planning | EXTEND | Campaign Coordinator / Marketing Ops |
| AI Search | AI Visibility Agent | **NEW** | Research DONE — path C + S2; see `phase8-ai-search-research-spike.md` |
| MSP | Security Agent | EXTEND | `MSP Vulnerability Analyst` |
| CS | QBR Agent | EXTEND | QBR workflow → CS agent step |
| CS | Health Score Agent | EXTEND | CS Agent `health-scoring` capability |
| Finance | Cash Flow Agent | EXTEND | AR Analyst / CFO / Variance |
| HR | Recruiting Agent | EXTEND | `talent-pipeline-agent` |
| Compliance | Compliance Agent | **NEW** | Knowledge pack + council mock only |
| RevOps | RevOps Agent | **REUSE** | `revenue-operations-agent` |
| Business OS | Rollup agent | EXTEND | Workflow chain only |

**Scorecard:** REUSE 2 · EXTEND 15 · NEW 3

**Existing intelligence-pack demo agents only:** Executive Macro Analyst, Sales Pipeline Analyst, MSP Vulnerability Analyst. Marketing/Support intelligence packs are assignments-only (no demo agent).

---

## 2. Workflows

| Vision workflow | Class | New connector actions first? |
|-----------------|-------|------------------------------|
| Weekly Executive Brief | EXTEND | No |
| Deal Reviews | REUSE/EXTEND | No |
| Build ICP | EXTEND | No |
| Campaign Planning | REUSE | No (`demo-launch-campaign`) |
| Client Risk Review | REUSE | No (`demo-customer-risk`) |
| Churn Prediction | NEW | Yes (ML + usage signals) — held this pass |
| Invoice Follow-Up | EXTEND | Partial (QB actions exist) |
| Candidate Screening | EXTEND | Connectors exist; pack workflow missing |
| Audit Readiness | NEW | Yes (no SOC2/ISO/CMMC doc connectors) |
| Revenue Forecasting | EXTEND | Heuristic OK; ML deferred |
| Daily Business Briefing | EXTEND | No |

**Pattern:** Most vision workflows are **orchestration** of existing `invoke_tool` + `agent_task` + `rag_retrieve` under `workflows/constants.py` schema. Do not invent a second workflow engine.

---

## 3. Connectors

| Vision source | In repo? | auth_mode | Gate |
|---------------|----------|-----------|------|
| QuickBooks / Xero / NetSuite / Plaid | Partial yes | `customer_owned` | **Finance governance** before live pack |
| Workday / Greenhouse / BambooHR / Gusto | Partial yes | `customer_owned` | **HR governance** before live pack |
| SOC2 / ISO / HIPAA / CMMC **documents** | **No** | — | NEW + Compliance scope = guidance docs only |
| ChatGPT / Perplexity / Bing Copilot visibility | **No** | — | **Research spike** — no scrape |
| Google Search Console | **No** (GA4 exists) | OAuth TBD | NEW for Marketing |
| FRED / NVD / CISA / SEC | Yes | `gravitre_managed` | LIVE |
| HubSpot / Apollo / Zendesk | Yes | `customer_owned` | LIVE / Apollo BYO |
| ZoomInfo / LI Sales Nav | Catalog | `byo_required` | Fail-closed |
| Crunchbase / PDL / OpenCorporates | Scaffold | `gravitre_managed` | Existing stop-lines |

Catalog: `backend/app/intelligence_packs/shared/auth_mode.py`.

---

## 4. Dashboards / meters / notifications

| Capability | Class | Note |
|------------|-------|------|
| `emit_notification()` + event taxonomy | **REUSE** | `notification_emitter.py` |
| Verified output / `result_url` | **REUSE** | `connector_output_contract.py` |
| StatTile / marketplace ROI | **EXTEND** | Org/marketplace KPIs, not pack KPIs |
| Shared Pack KPI dashboard | **NEW** | Must ship **once** before Customer Success |
| Settings → Intelligence Packs | **NEW** | Install is Marketplace-only today |
| `intelligence_usage_logs` | **NEW** | Still absent (Phase 0 MSP doc noted) |

**Finding:** “Cohesively and seamlessly across all pages” is **not** true yet — it is a Phase 3.5 precondition before pack #4.

---

## 5. Organizational Memory / Signal Engine

**Required path for every new pack source:**  
`run_shared_ingestion` → normalize → `write_external_entity_with_provenance` → `PackSignalDefinition`  
(`backend/app/intelligence_packs/shared/pipeline.py`, `provenance.py`, `signals.py`)

**Proven live:** FRED, NVD, CISA KEV, SEC EDGAR.

**Existing bypasses (findings, do not copy):**
- Intelligence pack install that only creates knowledge assignments
- `external_knowledge_service` Wikipedia/PubMed/SEC parallel path
- world_bank / oecd fetch modules without Phase 3 `invoke_tool` → shared ingestion

If a vision source cannot fit this interface, **report and stop** — do not invent a per-pack KG writer.

---

## Sales vs Prospecting

**Boundary is real — do not consolidate into one pack:**

| Pack | Job |
|------|-----|
| **Sales Intelligence** (shipped) | Pipeline / CRM ops — HubSpot pipelines, deal risk, Pipeline Analyst |
| **Prospecting & Lead Scouting** (#5) | Outbound lead gen — Apollo, PDL, Crunchbase, ZoomInfo/LI BYO |

Building Prospecting as a second “Sales” would duplicate Phase 4 Sales work. Treat Prospecting as the gated external-source pack originally sketched under Sales Phase 3 in older prompts.

---

## Manual agent/tool pick (MCP-replacement UX)

Chat path: user does **not** pick tools (auto-route). Pack install: connectors via `needs_connection` stubs.

**Remaining manual picks (gaps to close for pack UX, not new infra):**
- Assignments modal — choose agent
- Workflow builder — vendor/action/council agents
- Swarm / Training / Goal wizard — agent select

Pack install must remain the only setup step for pack consumers.

---

## Governance flags (new)

| Pack | Category | Rule |
|------|----------|------|
| Finance | Banking / QB / Xero / NetSuite | Cesar sign-off before any live financial-account connector |
| HR | HRIS / ATS / Payroll | Cesar sign-off — employee PII / compensation |
| Compliance | Framework docs vs PHI | Scope = **guidance documents only** (NIST-style). If PHI possible → stop; engineering cannot decide |

Pack definitions / mocked agents OK before sign-off. Live activation gated.

---

## Sequencing (locked extension)

1–3. Executive → MSP → Sales — **DONE** (Phase 4 PARTIAL; Apollo BYO)  
**3.5 Shared Pack UX** — Pack KPI component + Executive notify/result_url evidence — **before CS**  
4. Customer Success  
5. Prospecting  
6. Marketing (GSC)  
7. RevOps (after Sales+Marketing+CS; Finance when live)  
8. AI Search — **research spike DONE** (C + S2); tip smoke = build follow-on  
9–11. Finance / HR / Compliance — held on governance  
12. Business Operating System — **last**

Phase 5 ML v1 (CRM outcomes / ranked heuristics) is **orthogonal** to this pack-extension pass; do not fold CF/churn ML into pack builds this pass.

---

## Next (after review)

1. Human review of this Phase 0  
2. Phase 3.5: shared Pack KPI + Executive cohesion smoke  
3. Pack #4 Customer Success only after 3.5 PASS
