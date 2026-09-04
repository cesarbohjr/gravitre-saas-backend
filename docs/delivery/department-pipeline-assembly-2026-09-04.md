# Department pipeline assembly (Katie-style UX) — 2026-09-04

Status: **PARTIAL** — assembly + sync-back policy shipped to prod (`c5b59964`); CI fix pending for Twilio import boundary + proxy route TS; full prod chat E2E **NOT RUN**.

## Phase 0 — Real audit (confirmed)

### Existing pieces per department

| Department | Intelligence pack | Department pack | Key connectors (real) | WorkObject type |
|------------|-------------------|-----------------|----------------------|-----------------|
| Sales | prospecting-intelligence-pack | revenue-operations-pack | Apollo, Clay, HubSpot, Salesforce, Gmail | opportunity |
| Marketing | marketing-intelligence-pack | marketing-operations-pack | GA4, GSC, HubSpot, Canva | campaign |
| Finance | finance-intelligence-pack | — | Stripe, QuickBooks, Gmail | financial_issue |
| HR | hr-talent-intelligence-pack | hr-operations-pack | Greenhouse, Gmail, Calendar | candidate |
| MSP/Cyber | msp-intelligence-pack | msp-operations-pack (Slack-lite) | NVD, CISA KEV, Apollo, HubSpot; **ConnectWise gap** | vulnerability |

### F6 verified completion — timing (honest)

| Layer | Behavior today |
|-------|----------------|
| CRM **write** invoke | **Immediate** on user approval / auto-run |
| F6 **verification** | **Deferred async** after user-visible response (`schedule_write_success_verification`) |
| List membership proof | Settle loop ~81s (`collection_population_verify`) |

**Phase 4 scope confirmed:** customers need configurability for **when the CRM write fires**, not weakening F6 proof. Default remains immediate write; optional defer until named pipeline milestone.

### Prompt C / signal scoring

No standalone 0–100 signal score product. Real pieces: PackSignal, BusinessSignalsEngine, recommendation_quality_engine.

## Phase 1 — Named pipelines (assembly)

Catalog: `backend/app/marketplace/department_pipelines/catalog.py`

- Five pipelines with staged labels matching Katie-style UX
- Each stage references real invoke actions, packs, workflows, or signals
- `requires_new_capability` + `honestGaps` for ConnectWise, unified score SKU, MSP ops lite pack

## Phase 2 — Visible UI

- API: `/api/department-pipelines`, `/by-department/{dept}`, `PUT /sync-back-policy`
- UI: `DepartmentPipelinePanel` on Marketplace → Installed cards
- Composes with connect-and-go: `connectAndGoReady` when intelligence/department pack installed

## Phase 3 — Live E2E

**NOT RUN** — requires prod chat trace per department with connected Apollo/Clay/HubSpot (Sales) and second department. Run after deploy:

1. Install prospecting-intelligence-pack
2. Open Marketplace → Installed → confirm Sales pipeline stages visible
3. Run full Apollo → Clay → HubSpot flow; confirm F6 completion on final sync step

## Phase 4 — Configurable sync-back timing

Service: `backend/app/services/sync_back_policy_service.py`

- Org setting: `settings.department_pipelines.syncBack.{department}`
- Modes: `immediate` (default) | `defer_to_milestone`
- Gate in `ChatConnectorExecutionService.execute_plan` → `sync_back_deferred` without vendor write
- Milestone unlock via `pipeline_milestone_stage_id` in approved params or sync-tier stage

Local pytest: `backend/tests/marketplace/test_department_pipelines.py`

## Honest gaps (not invented)

- ConnectWise / Datto: profile-only, no connector
- Numeric lead/candidate signal score: heuristic only
- MSP sync stage: Zendesk fallback labeled; ConnectWise not built

## Evidence

- Local: `pytest backend/tests/marketplace/test_department_pipelines.py`
- Script: `python scripts/verify-department-pipeline-live.py` → `docs/delivery/department-pipeline-live.json`
- Prod health git_sha: verify after Railway deploy
