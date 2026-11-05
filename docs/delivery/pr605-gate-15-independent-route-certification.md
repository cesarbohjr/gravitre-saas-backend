# PR605 gate 15 — independent route certification and integrated CI truth

Date: 2026-11-05. Draft, no merge or production changes.

## New executable checks
- Added `.github/workflows/pr605-route-inventory.yml`: independent exact-commit route/OpenAPI/voice WebSocket certification, with retained JSON artifact, 30-minute job timeout, no live providers or customer data.
- Strengthened `backend/scripts/pr605_runtime_dependency_inventory.py` so the report must include `POST /api/assistant/chat` and `WEBSOCKET /api/voice/pipecat/ws` with nonblank handlers and at least one registered API WebSocket route. OpenAPI does not list WebSockets and cannot substitute for this check.
- Independent workflow enforces JSON parseability, source commit identity, at least 1,000 registered routes, at least 800 OpenAPI paths, zero unresolved router wrappers, zero unexplained OpenAPI path gaps, and zero missing critical endpoints. These baseline minimums are regression thresholds, not proof that every caller is dynamically exercised.
- Dedicated route CI run: [42097730672](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42097730672). Its result and uploaded artifact must be independently inspected before certification.

## Latest inspected evidence and correct interpretation
- Earlier CI [42094961866](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42094961866), artifact `13447667155`: 1,035 registered route entries, 8,707 static import edges, 0 unresolved router wrappers, 877 OpenAPI paths, 12 missing nested-prefix matches.
- All 12 were independently enumerated in the JSON: five enterprise-insights routes, five marketplace asset/outcome blueprint routes and two governed-operator routes. They were present in OpenAPI, showing an inventory path-prefix bug rather than missing FastAPI mounts. Source-level prefix reconstruction repair was committed at `f4c43ef3712f16a6ce804b937e35bf17374f8f6a`.
- Latest full CI is queued behind preserved long-running older CI under `concurrency: group: ci-${{ github.ref }}, cancel-in-progress: false`. We did not change that preservation behavior or cancel production-adjacent tests.

## Isolated PostgreSQL status v2 evidence
- Independent PostgreSQL certification [42096955154](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42096955154) on branch SHA `dd302dd6a943efebe7f11cf1a2c146ab90e4fe8e` passed 12 isolated SQL/PG migration tests and 14 focused status-translation tests, no skipped tests in those scopes.
- This certifies a *staged unapplied* SQL migration on throwaway PostgreSQL, not full backend CI, tenant-aware runtime status consumers, or permission to modify history.

## Required exact-head release gates
1. Inspect independent route job output and report; certify zero unresolved wrappers, zero OpenAPI gaps, assistant and WebSocket paths and handler identities; repair failures at source and rerun.
2. Inspect same-final-commit **full CI** job results, including frontend, shared runtime, backend pytest, integrated PostgreSQL and migration safety. A green independent check cannot replace an integrated check; skipped tests are not passes.
3. Retain Lighthouse and other applicable PR checks at unchanged thresholds.
4. Attest production DB project identity without exposing secrets; obtain separately reviewed per-row historical reconciliation approval by tenant/environment, then migrate only in the authorized release sequence.
5. No merge, no deployment, no production schema mutation or run status backfill until these gates pass.

**Status at creation:** independent route job executing; full CI queued; zero production changes; PR remains draft.
