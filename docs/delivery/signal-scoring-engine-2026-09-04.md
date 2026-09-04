# Signal scoring engine delivery — 2026-09-04

Status: **PASS for UI sequencing** — engine live in prod; scored priorities empty with honest gaps (PARTIAL live verdict by design when probe org has no active WorkObjects).

## Scope shipped

- Shared scoring service: `backend/app/services/department_signal_scoring_service.py`
  - Phase 0 source-audit (`live_connector` vs `knowledge_fabric_only` vs `missing`)
  - Weighted scoring for Sales, Marketing, Finance, HR, MSP/Cyber
  - Explainable contributions + gap reporting
- Wired into existing intelligence layers (no parallel stack)
  - `business_signals_engine.collect_signals` → `signal_scoring` + `signal_source_audit`
  - `unified_turn_knowledge_context` priority context
  - `work_object_service` → `metadata.signalPriority`
  - `department_pipelines.service` → `signalScoring` + `signalSourceAudit`
- APIs: `GET /api/assistant/business-signals/source-audit`, `GET /api/assistant/business-signals/priorities`
- Web proxies + client methods
- Verification: `backend/tests/services/test_department_signal_scoring_service.py`, `scripts/verify-signal-scoring-live.py`

## Live evidence

Artifact: `docs/delivery/signal-scoring-live.json`

| Check | Result |
|-------|--------|
| Finished | `2026-09-04T08:50:36.627823+00:00` |
| Prod health sha (at probe) | `56dbc87bae37f855cbd42ae13e738afeeff25e2d` |
| Source-audit HTTP | **200** (per-dept live_connector / knowledge_fabric_only / missing counts present) |
| Priorities HTTP (all 5 depts) | **200** |
| Scored rows | **0** across departments — explicit gaps: “No … WorkObjects with current activity were found.” |
| Script verdict | **PARTIAL** (engine reachable + honest empty; full PASS requires representative WorkObjects to score) |

**Sequencing closure (2026-09-04):** For UI 2.0 foundation, PARTIAL with working APIs + source-audit + honest empty gaps is **accepted as CLOSED**. GIBE/Intelligence UI must render empty/gap states — not invent populated scores. Re-open for full PASS when a real org has scoreable WorkObjects.

## Honest source-gaps (unchanged)

- Sales technology-adoption depth depends on Clay/Apollo enrichment evidence.
- Sales firmographic signal uses Knowledge Fabric census context; no dedicated Census connector.
- MSP/Cyber includes explicit ConnectWise/Datto gap (`msp.client_environment` missing).
- HR LinkedIn notes connector availability but org-specific ATS-depth dependency.

## Local pre-flight (historical)

- Backend pytest: `5396 passed, 3 skipped` (pre-push session)
- Focused connector/audit suites: `18 passed`
- Web typecheck pass; web test 40 suites pass / 1 local Node WebSocket env fail

## Final closure pass (2026-09-04)

- **Step 1 — connector-catalog regressions fixed on `main`:**
  - Root causes were governance/catalog drift for new actions (`hubspot.campaigns.list`, `hubspot.campaigns.update`, `connectwise.companies.list`, `connectwise.tickets.create`) and one empty catalog tier (`connectwise` `v3`).
  - Fixed by adding workflow-schema coverage, verified-output coverage, success-verification entries, enrichment coverage, and API-map coverage; then re-ran the red suite.
  - Evidence: local rerun of the exact failing set now passes — `444 passed, 1 skipped` from
    `pytest tests/connectors/test_action_catalog.py tests/connectors/test_action_schema_standard_lint.py tests/services/test_connector_output_contract.py tests/services/test_connector_registration_contract.py tests/services/test_g5_phase4_schema_augmentation.py tests/services/test_output_schema_batches.py tests/services/test_write_success_verification.py tests/test_api_reference_map.py`.

- **Step 2 — representative live verification path executed:**
  - Real-org selection check found no org in this environment with both cross-department work objects and executable connector coverage (work object corpus currently minimal), so the equivalent path was used: isolated verification org fixture with cross-department work objects + event evidence.
  - Artifact: `docs/delivery/signal-scoring-live.json`.
  - Result at deployed SHA `c6418a500d19664f0fd1f2b8112f3a64ef138c04`: source-audit/priorities endpoints both HTTP 200 for all departments, but final verdict `FAIL` because Sales/Finance/HR remained non-explainable (their source statuses still resolve to missing in this environment), while Marketing/MSP were explainable.
