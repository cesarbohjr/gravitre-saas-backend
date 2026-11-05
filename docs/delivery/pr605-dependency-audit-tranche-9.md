# PR #605 — Tranche 9: CI root-cause correction and evidence-based run-state reconciliation

Date: 2026-11-05. Audit evidence comes from connected GitHub Actions, the source-declared Postgres schema/mirror function, and read-only SQL against connected Supabase project `smyeexlrqdpymwjmgzqu`. **Production Supabase binding has not yet been attested**, so these are findings about the inspected project, not a certified prod-wide incident.

## 1. CI inventory: confirmed failure and repair
- Exact-head PR #605 CI run `42060414251`, job `127385524920`, failed specifically at `PR605 runtime mounted-route and dependency export`: `ModuleNotFoundError: No module named 'app'` while importing `app.main` from a script under `backend/scripts/`.
- Root cause: direct Python script execution puts `backend/scripts/` on `sys.path`, not its parent `backend/`. The previous CI step had not set the required Python import root.
- **Code fix committed:** `backend/scripts/pr605_runtime_dependency_inventory.py` now explicitly places `BACKEND_ROOT` on `sys.path` before importing the FastAPI application. Commit `3b95f6677192e2f957077be283e828b155c5da1a`.
- Subsequent CI workflows were in progress at last inspection. Do not claim a successful exact-head export until the step has passed and the `pr605-runtime-route-dependencies` artifact is inspected. If another import-time error occurs, fix it based on the actual job log and rerun.
- The script traverses registered routes, FastAPI dependency injection and up to three absolute Python import layers, **not** all dynamic caller edges nor production traces. Scope this certification honestly.

## 2. Status contract: facts from the deployed-source migration
- Actual `public.mirror_workflow_run_status_to_contract()` (and migration `supabase/migrations/20261001162827_verified_write_lifecycle_states.sql`) maps:
  - `pending_approval`, `awaiting_approval` → `needs_approval`: **intentional coarse status vocabulary**, not divergence.
  - `partial_success` → `completed`: **intentional current mapping** but loses partiality; inspect downstream semantics before modifying the contract.
  - `verifying` → `running`; `verification_inconclusive`, `error` → `failed`: documented translations.
- `runs.status` CHECK allows only `queued`, `pending`, `running`, `completed`, `failed`, `cancelled`, `needs_approval`; `workflow_runs.status` allows richer statuses including `flagged_for_review`.
- The mirror has **no mapping for `flagged_for_review`**. The product explicitly requires `flagged_for_review` to remain **distinct from failed and verified** (see `docs/delivery/phase6-flagged-for-review-v0-handoff.md`). The mirror's `WHEN OTHERS RAISE WARNING; RETURN NEW;` swallows constraint violations. This is a **confirmed representational incompatibility**, and can leave a stale contract projection. Do not map flagged to failed/completed or fabricate an approval state.

## 3. Actual inspected-project reconciliation
Read-only FULL JOIN by shared run ID:
- 801 IDs present in both tables, 2 only in `workflow_runs`, 283 only in `runs`. Runs-only may be legitimate direct/agent actions; establish `run_type` and origin before calling them orphaned.
- 767 of the 801 matched records align **after** the source-defined translation.
- 34 differ after translation:
  - 30 `workflow_runs.partial_success` vs `runs.queued` (expected `completed` per current mirror, **not approved as a truthful outcome contract**).
  - 2 `workflow_runs.failed` vs `runs.running` (expected `failed`).
  - 2 `workflow_runs.flagged_for_review` vs `runs.queued` (no representable status).
- 4 `pending_approval` / `needs_approval` lexical differences are **intentional and already counted aligned**.
- All 34 mismatched rows checked had no `metadata.mirrored_by` marker; this is a clue for historical/unmirrored writes, not proof of exactly when/why divergence occurred. The 30 partial-success mismatches span Aug 2–Sep 29, the 2 failed/running records date to Jul 20, and 2 flagged/queued records to Sep 1–4. No records were updated.
- Aggregates and exact source query: `docs/delivery/pr605-run-status-reconciliation-readonly.sql`.

## 4. Engineering remediation — protect truth and avoid unsafe mass UPDATE

### Gate A — contract decision (P0)
- Choose an authoritative run status owner for each workload and define a **lossless canonical lifecycle contract**. Current `runs.status` is a coarse projection; its `completed` value must not be equated with verified full success if source was `partial_success`.
- Preserve `flagged_for_review` as a distinct, non-success, non-failure human-review state. Preferred engineering direction: extend a **versioned typed contract** with distinct review and partiality indicators and update all consumers, DB CHECKs, serializers, API DTOs and UI badges in one compatibility migration. Do not shoehorn review into `failed`, `completed` or an invented approval grant.
- Inventory every `runs.status` reader, workflow/run writer, RPC, trigger, FKs, approval and analytics consumer; add regression tests for all statuses across the intended contract.
- Decide if a mirror trigger should fail closed, persist an explicit reconcile-needed event, or use a durable repair queue. The current warning-only catch cannot silently hide a partial write indefinitely. Any change must preserve intentional async boundaries, idempotency and workflow acceptance.

### Gate B — future-write correctness and certification (P0)
- Build contract tests in ephemeral PostgreSQL for all workflow statuses, including `flagged_for_review`, `partial_success`, `failed`, `pending_approval`, `verifying`, and `verification_inconclusive`.
- Simulate a denied mirror write / constrained status, test no silent stale terminal outcome or unauthorized write; verify no false success and correct review badge.
- Test status transitions on INSERT and UPDATE, concurrent retry and process restart, including metadata/provenance retention. CI must report pass/fail without treating skipped PG tests as passed.

### Gate C — historical records (P0, no automatic mutation)
- Investigate provenance, affected workflow types, timestamps, audit/outbox events, and which system owns these 34 records. Distinguish historical test or acceptance fixtures from operational customer data under tenant guardrails.
- Produce a **preview-only** per-run reconciliation report available to authorized operators, with expected target and side-effect risk. Require explicit approval of mapping and dry-run output before any backfill.
- If approved, implement a bounded idempotent backfill that updates only selected rows, guarded by original status/version; preserves historical lifecycle metadata; avoids generating duplicate terminal outbox events; has stop/resume, backup and rollback.
- Run post-repair diff and downstream read-model consistency verification, and retain counts & exact migration SHA as evidence. No automated production row modifications in this tranche.

## 5. CI, database binding and roll-forward status
- CI import fix committed, awaiting confirmed pass and artifact.
- Read-only reconciliation SQL committed.
- **Not yet repaired:** 34 mismatched historical records, unmapped review-state contract, old warning-only trigger. These cannot be safely treated as repaired merely by documentation.
- Production database binding still requires a non-secret Railway deployment attestation.
- No schema, production data or deployment mutated.

## Priority updates to PR #605 register
- ECO-057 P0: fix runtime inventory import path and certify artifact (code fix committed; CI pass pending).
- ECO-058 P0: preserve distinction of flagged_for_review and partial_success in canonical run status representation and all consumers.
- ECO-059 P0: eliminate warning-only mirror failure ambiguity through governed contract migration and observable reconciliation failure.
- ECO-060 P0: investigate 32 stale/inconsistent translated statuses and 2 unrepresentable review records; approve only precise idempotent backfill.
- ECO-061 P1: ensure 283 runs-only rows are classified by origin rather than falsely labeled orphans.
- ECO-062 P0: certify truth across approval, business outcome, UI and analytics under changed status contract.

## Confirmed additional application mirror defect and scoped code fix
Source `backend/app/workflows/schema_sync.py` defines `contract_run_status` with `_LEGACY_TO_CONTRACT_RUN_STATUS.get(raw, "queued")`. Until now, this mapping omitted both `partial_success` and `flagged_for_review`, so the application-side mirror would **turn both into queued**. This is a concrete source-level mechanism consistent with the 30 partial/queued and 2 flagged/queued historical mismatches (not proof that this exact function wrote each historical row).
- **Code fix committed:** `partial_success` maps explicitly to the existing DB projection `completed` and `mirror_legacy_run_to_contract` now preserves original `execution_lifecycle` and `mirrored_by=schema_sync` metadata.
- `flagged_for_review` now raises an explicit `ValueError` rather than falling back to `queued`; the surrounding legacy mirror catches and logs failure. This prevents the application's silent false requeue but **does not yet persist a correct lossless review status in `runs`**, and the DB trigger still requires the planned schema/consumer migration.
- Tests committed in `backend/tests/workflows/test_schema_sync.py` assert explicit partial translation and refusal to requeue review-state results. Applicable exact-head CI results must be inspected; not yet certified.
- Existing historical rows were **not modified**. Do not represent the remaining warning-only trigger or 34 mismatched records as repaired; the full contract, lifecycle truth and approved row-scoped reconciliation gates remain open.
