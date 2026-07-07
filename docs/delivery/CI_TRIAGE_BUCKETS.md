# CI triage buckets (pre-existing failures)

Full CI (`.github/workflows/ci.yml`) runs the entire backend, web, marketplace, security, and billing suites. Several jobs fail for **known, unrelated** reasons. Connector governance work must **not** block on fixing all of these at once.

## Merge-blocking (connector scope)

Use **Connector Governance** (`.github/workflows/connector-governance.yml`) as the required check for connector/chat execution changes. It runs only:

- `test_connector_registration_contract.py` — allowlist shrink contract (14 orphan + 6 API import + 166 pending schema)
- `test_connector_action_workflows.py` — preflight, capability fallback, validation, approval envelopes
- `test_connector_parameter_inference.py` — Feature 1 context-aware inference
- `test_action_workflow_validation.py` — Feature 2 schema-driven validation
- Registry, import boundary, capability, session, chat execution, orchestration, and connector smoke suites

## Known pre-existing failures (full CI — ticket, do not block connector PRs)

| Bucket | Job / test area | Owner track | Notes |
|--------|-----------------|-------------|-------|
| Marketplace seed | `backend` → Marketplace QA | Platform / marketplace | `test_catalog_asset_counts` drift |
| HubSpot tier | Backend unit tests | Integrations | HubSpot v4 tier assertion |
| Meson / network | Backend unit tests | Infra | Network-dependent tests in CI sandbox |
| Dependency audit | `security-scan` → pip-audit | Security | `ecdsa` advisory (transitive) |
| Web lint | `web` → Lint | Frontend | Pre-existing lint debt |
| Rate limit flakes | Various backend tests | Platform | Intermittent timing |

## Process

1. **Connector PRs:** green scoped governance job + code review. Admin-merge full CI only when scoped job is green and failures match this table.
2. **Triage side task:** open Linear tickets per bucket above; link failing test paths. No requirement to close before Step 1–3 connector work.
3. **Do not expand scope:** fixing marketplace seed or web lint in the same PR as allowlist shrink adds review noise and repeats the “fix everything red” trap.

## Allowlist shrink pattern (Steps 1 and 3)

The registration contract test is the progress tool — not a bare assertion:

- Each allowlist names debt explicitly (`ORPHAN_HANDLER_ALLOWLIST`, `API_IMPORT_EXCEPTION_ALLOWLIST`, `PENDING_WORKFLOW_SCHEMA_ALLOWLIST`).
- Fix debt **and** remove the name in the same PR.
- Startup logs and CI summary print remaining counts (trending down).

Re-use this pattern for future governance lists; do not invent parallel “audit-only” tests.
