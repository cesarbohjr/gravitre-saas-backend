# Signal scoring engine delivery — 2026-09-04

Status: **IN PROGRESS** (implementation + regression complete locally; deployment verification pending)

## Scope shipped in this pass

- Added a shared cross-department scoring service: `backend/app/services/department_signal_scoring_service.py`
  - Phase 0 source-audit output per department (`live_connector` vs `knowledge_fabric_only` vs `missing`)
  - Phase 1/2 weighted scoring definitions for Sales, Marketing, Finance, HR, MSP/Cyber
  - Explainable score contributions and explicit gap reporting
- Wired scoring into existing intelligence layers (no parallel stack)
  - `business_signals_engine.collect_signals` now includes `signal_scoring` + `signal_source_audit`
  - `unified_turn_knowledge_context` injects scored priority context for prioritization queries
  - `work_object_service.record_execution_work_object` now attaches persisted `metadata.signalPriority`
  - `department_pipelines.service` surfaces `signalScoring` + `signalSourceAudit`
- Added API surfaces for live reads:
  - `GET /api/assistant/business-signals/source-audit`
  - `GET /api/assistant/business-signals/priorities`
- Added web proxy routes + API client methods for the new assistant scoring endpoints.
- Added verification tooling:
  - `backend/tests/services/test_department_signal_scoring_service.py`
  - `scripts/verify-signal-scoring-live.py`

## Pre-flight evidence

- CI on `main` before implementation: **NOT GREEN**
  - `CI` run `33850038016`: failed
  - `CI` run `33849372776`: failed
- Local full backend regression:
  - `python -m pytest -q` in `backend`
  - Result: `5396 passed, 3 skipped, 679 warnings in 781.04s`
- Local focused rerun of prior failing backend suites:
  - `python -m pytest -q tests/services/test_connector_api_import_boundaries.py tests/services/test_connector_catalog_audit.py tests/services/test_connector_registry_verification.py tests/test_audit_instruments_have_real_actor.py`
  - Result: `18 passed in 35.99s`
- Local web checks:
  - `pnpm -s typecheck` in `apps/web`: pass
  - `pnpm -s test` in `apps/web`: 40 suites passed, 1 failed due local Node WebSocket runtime requirement from Supabase (`Node.js 22+` required)

## Honest source-gaps encoded

- Sales technology-adoption depth depends on available Clay/Apollo enrichment evidence.
- Sales firmographic signal uses Knowledge Fabric census context; no dedicated customer-owned Census connector.
- MSP/Cyber client-environment scoring includes explicit ConnectWise/Datto gap (`msp.client_environment` missing).
- HR LinkedIn signal notes connector availability but org-specific ATS-depth dependency.

## Pending verification before final PASS

- Commit and push to `main`.
- Confirm GitHub Actions CI turns green on pushed SHA.
- Confirm Railway production deploy SHA.
- Run `scripts/verify-signal-scoring-live.py` against production and archive:
  - per-department scored priority sample (or explicit no-data gap),
  - source-audit status counts,
  - explainability payload presence.
