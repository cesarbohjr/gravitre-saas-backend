# Department pipeline assembly (Katie-style UX) — 2026-09-04

Status: **SHIPPED** — prod `161df8f8`; Phase 3/4 PASS via deployed smoke on F6 org.

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

Run after deploy:

```bash
python scripts/verify-department-pipeline-live.py
```

Uses `POST /api/internal/ops/department-pipeline-smoke` on F6 smoke org (Sales 7-stage + Marketing 6-stage pipeline views; execute_plan defer/unlock).

## Phase 4 — Configurable sync-back timing

- Admin toggle on `DepartmentPipelinePanel` (Marketplace → Installed + post-install success)
- API: `PUT /api/department-pipelines/sync-back-policy`
- Deployed proof: `department-pipeline-smoke` gates `sales_early_deferred` + `sales_milestone_unlock`

## Honest gaps (not invented)

- ConnectWise / Datto: profile-only, no connector
- Numeric lead/candidate signal score: heuristic only
- MSP sync stage: Zendesk fallback labeled; ConnectWise not built

## Evidence

- Local: `pytest backend/tests/marketplace/test_department_pipelines.py`
- Script: `python scripts/verify-department-pipeline-live.py` → `docs/delivery/department-pipeline-live.json`
- Prod health git_sha: verify after Railway deploy
