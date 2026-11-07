# PR #605 — Gate 26 tranche 2: execution caller and consumer contracts
Date: 2026-11-05. Evidence class: branch source inspection, **not production usage**. Additive to Gate 26 tranche 1, the governing modernization plan, ECO gap register and DEC retirement register.

## Verified call and handoff edges
| Producer / owner | Source location | Observed downstream | Constraint / implication |
|---|---|---|---|
| Chat orchestration start | `backend/app/services/chat_orchestration_service.py:1386-1405` | `start_orchestration_run` then stores `orchestration_run_id` in task parameters | A run ID may be absent; inspect restart/recovery and caller behavior |
| Chat orchestration step | `chat_orchestration_service.py:1487,1513-1530,1628,1846` | connector `execute_plan`; conditional `emit_plan_run_link`; `sync_orchestration_step` | Plan/run telemetry only when both identities exist; multiple connector execution call sites need branch coverage |
| Orchestration orphan terminal | `chat_orchestration_service.py:1971-1995` | `finalize_execution_outcome(... persist_run=False)` | Deliberate no-run fallback still fans out; verify consumer semantics and whether it should create a canonical run, not assume safe deletion |
| Connector execution | `chat_connector_execution_service.py:1999-2034,3156-3193` | `_execute_plan`; `_finalize_connector_outcome` (lightweight workflow run) | Speculative/unconfirmed voice execution defers outcome fanout until adopted; preserve this write fence |
| Connector verified outcome | `chat_connector_execution_service.py:3493-3515` | `finalize_execution_outcome` | Provider acceptance without independent verification becomes `verification_inconclusive`, not success; preserve this distinction |
| Domain event registration | `domain_events.py:61-82` | `register_domain_event_handler` / `handlers_for` | Stable handler names persisted in `delivered_handlers`; renaming risks duplicate retry effects |
| Domain event relay | `domain_events.py:205-245,247-265` | dispatches registered handler, tracks completed names, releases claims without handlers | Source shows retry/partial completion semantics; deployed durable delivery still unproven |

## Findings and targeted remediation gates
**G26-EX-005 / P1 — Orchestration orphan outcome.** A terminal path calls `finalize_execution_outcome` with `persist_run=False` when no run ID and no steps exist. Determine whether notification/audit/learning consumers require a durable run; add contract tests for this path and do not silently manufacture a run.

**G26-EX-006 / P0 safety invariant — Speculative connector writes.** `_finalize_connector_outcome` defers its fanout when speculative execution has not been adopted. Regression matrix must prove speculative, denied, revoked and accepted paths cannot generate unauthorized run/audit/notification effects. Preserve deferral while consolidating execution.

**G26-EX-007 / P0 truth invariant — Independent provider verification.** Unverified provider acceptance is terminalized as `verification_inconclusive`. Test all connector write and retry branches against source-of-record confirmation; do not convert accepted API response into verified completion.

**G26-EX-008 / P1 retry identity — Event consumer registration.** Persisted `delivered_handlers` names are idempotency identities. Inventory all registration call sites and deployed consumers before renaming/removing a handler; test partial success and retry across restart.

**G26-EX-009 / P1 coverage — Multiple connector entrypoints.** Orchestration invokes `execute_plan` at several distinct locations. Enumerate conditional paths and prove consistent authorization, canonical outcome and correlation; static occurrence count is not production frequency.

## Next inspection and test plan
Search repository-wide registration call sites (`register_domain_event_handler`) and canonical terminal writer calls (`finalize_execution_outcome`); build an owner/caller/event/consumer table with file and line evidence, marking dynamic or unknown paths explicitly. Test orphan outcomes, speculative deferral, unverified provider acceptance, and handler retry identities in isolated CI before changing contracts. For production proof, await issue #607 Security/Privacy and Operations approvals and an authorized acceptance environment. Full exact-head CI remains separate; no retirement, merge, deployment or production telemetry is authorized by this document.
