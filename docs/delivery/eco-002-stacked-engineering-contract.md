# ECO-002 engineering baseline and integration contract

**Finding:** ECO-002 (P0, routing-latency; QA30) in `docs/delivery/master-qa-remediation-register.v2.json`.

**Tracking:** GitHub issue #614. **Parent:** PR #611 (`feat/master-qa-tranche27-orchestration`). **Fork point:** `ce68f98353387338c0fa5344a5b535594bf297f5`.

## Stacked integration policy
- This branch is deliberately based on PR #611's certified head, **not an older main**. Open the ECO-002 PR against the PR #611 branch until #611 merges; then reconcile the latest main and retarget with exact-head tests.
- ECO-001 and P27 remain owned by PR #611. No copy of the master plan, no parallel register, no premature closure.
- Before each integration, compare current PR #611 head, this PR head, and target main. Resolve upstream changes explicitly; never force-push away or silently overwrite a prior advancement.
- Changes to shared router paths must retain canonical execution, authorization, approval, tenant isolation, cancellation and durable ledger behavior.
- Engineering may advance independently; merge/release certification retains original dependency order.

## ECO-002 baseline plan
1. Trace actual chat/text/voice entrypoints to `IntelligenceRouter.route` and document the critical-path stage DAG.
2. Instrument monotonic stage timings with safe bounded labels; exclude raw prompts, PII, credentials, tenant IDs and request payloads.
3. Capture reproducible per-stage p50/p95 with sample sizes and request/context sizes. Voice time-to-first-audio where supported.
4. Optimize only proven independent waits after baseline; preserve behavior on exception, timeout and cancellation.
5. Add negative/positive regression tests and compare before/after. Targeted tests for iteration; full exact-SHA CI for certification.
6. Update ECO-002 evidence in the **existing** register only when all closure criteria are met.

## Gate status at branch creation
- PR #611 helper fix `ce68f98`: General CI 43163057076 PASS; Master QA P0 43163057125 PASS.
- Protected P27 HubSpot retest: pending **fresh explicit owner authorization**. This branch must not trigger or reuse it.
- ECO-001: NOT CERTIFIED; no merge, deployment or register PASS authorized.
