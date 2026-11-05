# PR #605 — Gate 11: Versioned run-status contract, consumer audit, and historical reconciliation
Date: 2026-11-05. Baseline: production-deployed source 557be844f191767ea51c9f1d1d4958e5b046ca53. This gate is **IMPLEMENTED IN DRAFT / NOT PRODUCTION CERTIFIED**.

## Source of truth and new contract
Source-of-truth run lifecycle remains `workflow_runs.status`. V1 contract `runs.status` collapsed `partial_success` to `completed` and lacked `flagged_for_review`. Application-side legacy mapping also defaulted some unknown lifecycle statuses to `queued`. The former can overstate success; the latter can falsely portray a terminal run as pending work.

New v2 contract staged in PR #605:
- `backend/app/workflows/run_status_contract.py`: version constant 2; explicit mapping for all known source states; unknown statuses fail rather than becoming queued. `partial_success`, `flagged_for_review` and `paused` retain separate statuses. Approval aliases map to `needs_approval`; verifying to running; inconclusive to failed, with original lifecycle metadata kept.
- `supabase/migrations/20261105090000_run_status_contract_v2.sql`: adds `partial_success`, `flagged_for_review`, `paused` to the `runs.status` CHECK; replaces mirror trigger function with a versioned lifecycle projection and status_contract_version metadata; removes warning-only catch so failed mirroring fails the workflow update transaction rather than causing silent divergence. This is **not applied to connected Supabase or production**.
- `backend/app/workflows/schema_sync.py`: application mapper uses the same explicit v2 contract and records source `execution_lifecycle`, `mirrored_by`, and version 2. **Deploy only after the v2 schema migration is certified and applied to the intended environment.**
- `apps/web/types/api.ts`: exposes `flagged_for_review`, `partial_success`, `queued` and `needs_approval`.
- `backend/tests/workflows/test_schema_sync.py`: v2 partial/review, aliases, version metadata, strict unknown-status rejection.
- `backend/tests/db/test_pr605_run_status_contract_pg.py`: isolated PostgreSQL status mapping, insert/update, failure rollback, reapply; CI has explicit mandatory PostgreSQL certification step.

## Downstream consumer impact register
| Class | Inspected primary implementation | Observed contract dependency | Required parity / risk |
|---|---|---|---|
| Workflow writes and dual-write | `backend/app/workflows/repository.py`, `schema_sync.py` | create/update/approval recovery call application mirror after `workflow_runs` write; DB AFTER trigger independently mirrors | Migration first; test that both mirror writers agree and retries are idempotent; avoid misleading two-stage success claims |
| Canonical terminal outcomes | `backend/app/services/execution_outcome.py` | already recognizes `partial_success` and `flagged_for_review` as distinct terminal values | Preserve terminal truth, verified outcome checks, notification and audit classifications |
| Business outcome DTO | `backend/app/services/business_outcome/projector.py` | distinct review state; partial can enter write-effect success heuristics | Verify no partial or flagged state is shown as verified success without source-of-record evidence |
| Business outcome UI | `apps/web/components/gravitre/business-outcome/business-outcome-view.tsx` | explicitly detects review-required state | Preserve separate review badge and next-actions; verify partial badge, no false verified claim |
| Shared status styling | `apps/web/lib/design-system.ts`, `apps/web/components/gravitre/status-badge.tsx` | already defines partial and review tone; badges derive from status | Snapshot tests for both states across activity/run detail/chat |
| Assignment queues | `apps/web/lib/assignments-list.ts` | logic distinguishes `completed` and `needs_approval` with narrow filters | Verify `partial_success` and `flagged_for_review` remain visible and do not enter completed-only actions |
| Metrics/overview | `backend/app/routers/metrics.py`, `backend/app/metrics/service.py` | some metrics query `workflow_runs`; others may use contract tables/RPCs | Audit all status predicates; partial must not inflate verified-completed KPI; review must not be counted as a success or fail |
| Recovery | `backend/app/services/stale_run_recovery.py` | can emit review status; catches application mirror errors on recovery | Verify v2 transition, audit, restart, and reconcile state; remove silent failure after migration |
| Legacy run contract APIs | `backend/app/services/org_seed_service.py`, `backend/app/services/marketplace_sandbox_service.py` and workflow schema sync | direct reads/writes against `runs` | Ensure new enum values do not cause 4xx, default-to-queued or unintended terminal normalization |
| Frontend API schema | `apps/web/types/api.ts` | RunStatus previously lacked review state | Updated, but all consumers must pass typecheck and runtime tests |
| Database readers & FKs | `runs`, `workflow_runs`, `run_steps`, approvals, agent handoffs, audit and triggers | multiple distinct run family references | Maintain FK/approval boundaries and inspect functions, materialized reporting and RLS under verified prod binding |

**Coverage caveat:** This is a documented source-based consumer inventory, not evidence that all dynamic/runtime consumers or production branches have been traced. Do not claim holistic graph completion on this basis.

## Historical data findings (connected project, production binding unverified)
- Read-only full outer join: 801 matching run IDs; 2 workflow-only; 283 contract-only (potentially valid nonworkflow runs, do not mark orphaned).
- Under the old coarse translation, 767 matched; 30 `partial_success/queued`, 2 `failed/running`, and 2 `flagged_for_review/queued` were inconsistent. Four `pending_approval/needs_approval` were intentional.
- Under proposed v2, 34 matched pairs require reconciliation and two workflow-only records require investigation; the source status for those review-required records has never had a lossless contract representation.
- `docs/delivery/pr605-v2-historical-reconciliation-preview.sql` is an aggregate-only READ-ONLY preview. There is no backfill or mutation script enabled.

## Controlled data-repair protocol — NOT authorized for production execution
1. Attest deployed Railway Supabase project by non-secret project reference and verify migration ledger against the target DB.
2. Complete exact-head isolated PostgreSQL contract tests, application and frontend tests, RLS/approval and concurrent-write regression tests.
3. Inventory tenant/workflow type for each impacted row with authorized review, preserving user and org privacy. Separate fixture/acceptance from customer records.
4. Freeze an approved, per-org run-ID allowlist; output proposed before/after effects and obtain explicit authorization for historical repair.
5. Apply database migration in acceptance first, then deploy compatible application readers/writers after schema verification. For production, sequence migration before readers/writers.
6. Execute idempotent, compare-and-set bounded repair only against allowlisted rows; preserve historical timestamps and source lifecycle and prevent duplicate terminal outbox events; record audit evidence and checkpoint for rollback.
7. Re-run parity checks, downstream metrics, UI snapshots, event delivery and approvals; stop on unrecognized statuses or new mismatches.
8. If reviewer rejects lossless contract or migration cannot be certified, do not modify records or silently relabel outcomes.

## Certification blockers
- New v2 migration and PG tests committed; full CI outcome pending. No migration applied.
- Runtime route inventory has previously passed one CI step but output was invalid nested-router containers; recursive exporter was committed and awaits exact-head artifact inspection.
- Production DB binding remains unconfirmed. Complete downstream traffic correlation and all dynamic event consumers unverified.
- No historically affected row repaired, no production service or policy changed.

## Additional read-only run-family evidence
An aggregate grouped by `workflow_runs.run_type` shows all 34 mismatched pairs comprise **execute** runs: 30 `partial_success/queued`, 2 `failed/running`, and 2 `flagged_for_review/queued`. This narrows the authorized reconciliation candidate population; it is **not** permission to alter them. Two additional workflow-only review records still require separate investigation, and 283 `runs`-only records must not be mistaken for failed mirrors.

## Important gate limitation
The current audit lists known readers/writers and their documented contracts, but **complete downstream consumer/runtime certification remains open** pending exact-head CI artifacts, source-graph expansion, production traffic sampling across all execution surfaces, and validation of the connected database as production. The staged v2 migration is not applied and the historical records have not been changed.
