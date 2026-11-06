# PR605 Gate 26 — Tranche 2 certification record (pending)

## Exact-head scope

Head after executable test and CI wiring: `0d0a84852cce580ff575860a15c301097a68222f`. PR #605 remains draft. No merge, production deploy, migration, connector invocation, or retirement was authorized.

## Implemented checks

- `backend/tests/services/test_gate26_connector_relay_behavior.py`: reject duplicate event consumer registrations, prove absent consumers do not register, and prove speculative connector outcome deferral prevents immediate persistence.
- Enforced write-authority tests: reject missing authority and policy authority for a mandatory-human-approval action; explicit fixture patches isolate provider/catalog behavior.
- Connector terminal-outcome tests: distinguish proven creates from accepted-async, no-op, already-existing, and unknown results; never report COMPLETED for unverified mutating effects.
- `.github/workflows/connector-governance.yml` now includes the Gate 26 test file as a required scoped test target and pull-request path trigger.

## Evidence boundaries

These are mock and pure-function regressions, not production connector-consent or durable PostgreSQL execution tests. The earlier exact-head `9ee43998` privacy-edge, cross-surface ownership, run-status, migration-safety, and several other workflows passed; full CI remained pending. No run for new head `0d0a8485` was returned at initial inspection. The earlier static caller inventory is not a complete dynamic runtime map. The source-level connector orchestration calls and relay handlers still need an exhaustive typed caller/consumer matrix, including authorization, revocation, cancellation, retry, and idempotency ownership.

## Mandatory closure criteria — not yet met

1. Inspect the exact-head Connector Governance job and all required full-CI checks. Fix failures and rerun at the resulting head. Skipped/pending checks do not count as passing.
2. Prove the scoped new tests pass and add independent revoked-access and post-authorization cancellation cases with service-level mocks, including no unauthorized write and no false completed outcome.
3. Certify repository-wide agent/play/workflow/connector/event-consumer caller ownership and identify unresolved dynamic registrations. Correlate privacy-safe runtime edges using verified shared identifiers; do not infer from AST or timestamps.
4. Verify database durability and idempotent replay in PostgreSQL migration/integration tests, with explicit environment identity and no production writes.
5. Record SHA, run/job URLs, test counts, skipped tests, outstanding blockers, and independent review/approval before declaring Tranche 2 complete.

**Status: IMPLEMENTATION IN PROGRESS — NOT CERTIFIED.** Zero approved retirements.

## 2026-11-05 continuation: cancellation, revocation and durability

- Commit `0df973e` adds four synthetic behavioral/source-contract checks in `backend/tests/services/test_gate26_cancellation_and_outbox_contract.py`: sticky cancellation of mutable writes, expiration of scoped human authority (subsequent write denied in enforce mode), discarded speculative writes never executing, and static Postgres outbox migration invariants (transactional triggers, idempotency unique key, leases/SKIP LOCKED, handler checkpoints and RLS).
- Commit `510db140` wires this file into the Connector Governance workflow's PR trigger and scoped pytest command.
- Commit `70a1a98e` expands the source-owner inventory to chat orchestration, orchestration-run persistence, write authority, speculation, turn cancellation, connector effect truth and typed runtime correlation. The output remains **static AST evidence**, not an exhaustive repository-wide or runtime inventory.
- **Important distinction:** The migration contract check only proves SQL text declares expected features; it does **not** establish successful PostgreSQL migration, transaction rollback semantics, lease-owner enforcement, crash/restart idempotency, RLS tenant isolation or live side effects. Those need independent integration evidence.
- CI lookup immediately after `70a1a98e` returned no runs. The earlier Connector Governance job for `50d76c5d` was cancelled (not a pass). Do not count cancelled, skipped, queued or pending as success.
- **Remediation:** inspect next exact-head scoped tests, fix confirmed failures, run real PostgreSQL integration tests in an authorized isolated environment, and reconcile all source and dynamic caller/consumer gaps. Do not enable production telemetry without privacy approval.

**Tranche 2 remains OPEN. No retirement, migration, deployment or merge approved.**

## Exact-head CI triage and durable acceptance workflow (subsequent continuation)

- The expanded AST source owner registry has **20** source files, but `.github/workflows/pr605-cross-surface-ownership.yml` still asserted 12. Fixed the stale assertion in commit `923a64ae`. This was a deterministic CI contract mismatch identified by inspection, **not** a previously observed failing job log; do not represent it as a CI failure until the job runs.
- Existing `backend/tests/db/test_domain_event_outbox_pg.py` already exercises real disposable PostgreSQL transactions and idempotency (including rollback, concurrent claimers, lease fencing, retry/dead-letter, RLS and multi-relay delivery). New workflow `.github/workflows/pr605-gate26-postgres-outbox.yml` commit `8d172b33` explicitly installs PostgreSQL, refuses to count missing binaries as a skip, and runs that suite on the PR head. No production or Supabase database is touched by this workflow.
- Source-backed caller and consumer matrix committed as `docs/delivery/pr605-gate-26-tranche-2-caller-consumer-map.md` commit `f4be6900`, including three orchestration connector branches, three relay consumer registrations, worker startup gates and six Temporal workflow / eight activity registrations. It is not an exhaustive runtime caller proof.
- At the time of inspection, prior Connector Governance run `42155142972` was **cancelled**, the earlier route inventory job was still running, and GitHub had not returned new-head workflow results. No exact-head CI or PostgreSQL success is claimed. The latest head must be checked again after workflow dispatch.

**Still open:** exact-head CI including the new PostgreSQL suite, real runtime trace / dynamic caller evidence, and any discovered test repairs. No retirements.
