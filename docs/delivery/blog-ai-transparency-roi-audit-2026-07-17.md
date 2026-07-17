# Blog audit: AI transparency & department ROI (2026-07-17)

Phase 0/1 findings for customer-facing copy. Status: **VERIFIED** = shippable as present-tense claim with cited mechanism. **PARTIAL** = real but scoped; must qualify. **NOT BUILT** = cut or roadmap-only.

## Transparency & explainability

| # | Claim | Status | Evidence / gap |
|---|--------|--------|----------------|
| 1 | Audit trails | **PARTIAL** | `write_audit_event` dual-writes `audit_events` + `audit_logs` (`backend/app/workflows/audit.py`). UI reads **`audit_logs` only** via `/audit` (`apps/web/app/audit/page.tsx`) with CSV/JSON export. Chat adds "View audit trail" link on tool runs (`assistant-source-links.tsx:104`). Gated by billing feature `audit_logs`; dual-write gaps logged as `audit_dual_write_gap`. |
| 2 | Approvals (chat, ReAct, canvas) | **VERIFIED** | Catalog write authority + HITL: `react_write_gate.py`, `chat_connector_execution_service.py`, `canvas_write_gate.py`. Canvas STA-322 live: `docs/delivery/sta322-canvas-write-reverify-live.json` — `pending_approval`, zero `tool.invoke.completed` before approve. STA-323 human_approval hydration: `test_human_approval_hydration.py`, `docs/delivery/sta323-human-approval-live.json`. UI: `ChatExecutionPanel`, `/approvals`, workflow builder approval nodes. |
| 3 | Evidence-backed recommendations (STA-314) | **PARTIAL** | Live heuristic cards: `recommendation_heuristics_service.py`, `GET /recommendations/heuristics`, `HeuristicSuggestionCards` on `/intelligence`. Cards include `kind`, human `reason`, `evidence` dict, `advisoryOnly: true`. **No `reason_code` field** in schema. Execute surface explicitly banned in tests. |
| 4 | Source attribution ("Sources checked") | **PARTIAL** | Real numbered citations when `searchKnowledgeBase` returns results (`assistant-source-links.tsx:23–55`, `113–125`). **Gap:** empty KB hit → static link to `/sources` labeled "Sources checked" (`:75–81`), not per-source proof. |
| 5 | Action verification (`result_url`, summary) | **PARTIAL** | Chat writes: `assert_execution_result_verifiable` (`connector_output_contract.py`). UI surfaces `unverifiable_output`, verified deep links, or "inline summary only" (`chat-execution-panel.tsx:249–334`). **Not catalog-wide:** many actions allow null `result_url` by design (`connector_output_verified_batches.py`). |
| 6 | Assumption labeling | **PARTIAL** | `assumption_notes` on successful execution (`chat-execution-panel.tsx:302–334`). Backend: `_assumption_notes_from_plan` + `enrich_plan_inference_metadata` (`chat_connector_execution_service.py`). **Narrow scope:** primarily inferred connector plan fields (e.g. Apollo omit-name default), not all model reasoning. |
| 7 | Human accountability (admin vs member) | **VERIFIED** | Member write → Decision Queue, copy "Your request will be sent for approval" (`chat-execution-panel.tsx:417–420`, `chat_connector_execution_service.py:1080–1094`). Admin/owner (or HITL approver) sees confirm/approve. Config: `/settings/approvals`, `/approvals`. Tests: `test_chat_connector_execution.py:130–155`, `test_hitl_policy_service.py`. |

## ROI / department metrics

| # | Claim | Status | Evidence / gap |
|---|--------|--------|----------------|
| 8 | Marketing KPIs (content time, CPL, launch speed) | **NOT BUILT** (ops **PARTIAL**) | `PackKpiPanel` shows signals/entities/agents for Marketing Intelligence Pack when GSC invoked — **not** campaign ROI (`pack-kpi-panel.tsx`, `kpis.py`). Marketplace catalog `estimated_hours_saved` is **estimate-only** (`OUTCOME_ESTIMATE_LABELING.md`). No cost-per-lead computation. |
| 9 | Sales KPIs (meetings, pipeline, prospecting hours) | **NOT BUILT** (labeling **VERIFIED**) | Sales/Prospecting intelligence packs: empty vendor map → zero signals. Apollo BYO plan-tier labeling live (`apollo_discovery_capability.py`, connector catalog copy). Pipeline **read** tools exist; no "meetings booked" or "hours saved" dashboard. |
| 10 | MSP/IT KPIs (ticket MTTR, resolution time) | **NOT BUILT** (intel **VERIFIED**) | MSP Intelligence Pack ingests NVD/CVE + CISA KEV signals (`msp_install.py`, `mappers.py`). **No** ticket resolution-time KPI. MSP Operations Pack workflow is agent summarize → Slack scaffold. |
| 11 | Support KPIs (health scores, Zendesk metrics) | **PARTIAL** | Customer Success pack workflows list Zendesk tickets / HubSpot deals (`seed_catalog.py`). **STA-124 integration health score ≠ account health.** `churn_risk_scorer` is advisory ML, not a CS dashboard KPI. |
| 12 | Executive KPIs (decision speed, reporting effort) | **PARTIAL** | Executive Intelligence Pack: macro/regulatory signal ingestion + advisory platform scorecard (`executive_intelligence_scoring_service.py`). Intelligence Reports ROI tab shows **"—"** for hours saved, revenue, cost (`intelligence/reports/page.tsx:93–95`). Weekly digest = workflow scaffold, not measured rollup. |

## Numeric examples flag (awaiting Cesar)

Brief placeholders ("40 hours → 10 hours", "20 hours → 5 hours", "30 min → 20 min") have **no** backing in code, delivery JSON, or customer pilot data in this repo. Pricing testimonial "2 days → 20 minutes" exists but is gated off (`SHOW_MARKETING_TESTIMONIALS = false`). **Do not publish as measured outcomes** until Cesar confirms real customer/pilot data.

## Cut from brief (not verified)

- Black-box-free recommendation **reason codes** (use `kind` + `reason` + `evidence` instead)
- Universal source attribution solved
- Platform-wide verified deep links on every connector action
- Department ROI dashboards (CPL, meetings booked, ticket MTTR, account health scores)
- Before/after hour or minute savings as real customer results
- "AI shows full chain-of-thought reasoning" (assumption_notes are scoped inference labels only)

## LinkedIn companion drafts (post-publish)

**Piece 1 — AI Transparency and the Approval Question**

Most “AI transparency” posts list values. Few show the mechanics.

In Gravitre today: catalog-backed write gates on chat, ReAct, and canvas (STA-322 re-verified in prod). Members queue writes; admins approve. Successful chat writes need a real summary or deep link, or the run fails as unverifiable_output.

We still do not claim perfect source attribution on empty knowledge search, or full assumption labeling on every action. We say that out loud.

Post: https://gravitre.app/blog/ai-transparency-and-approval

**Piece 2 — Measuring What AI Actually Changes**

Department ROI is where AI marketing goes to die.

Gravitre’s Pack KPI panels count ingestion signals and install scaffolding, not cost per lead or ticket MTTR. Intelligence Reports shows “—” for hours saved until ground-truth measurement ships. Marketplace hours-saved numbers are labeled estimates.

We did not publish “40 hours → 10 hours” style ratios. No pilot data in repo to support them.

Post: https://gravitre.app/blog/measuring-what-ai-changes

**Combined hook (optional single post)**

Transparency without metrics is theater. Metrics without governance is liability.

We wrote two posts on what Gravitre can prove today: approval gates + verified outputs, and operational counts vs estimate-only ROI. Everything else waits for builds and data, not adjectives.
