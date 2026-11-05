# PR #605 — Tranche 8: observed traffic, registered-route CI and event-consumer evidence

Date: 2026-11-05. **Evidence is from connected services and read-only SQL. Production Supabase binding remains unverified.**

## Exact-head engineering change
- Branch contains `backend/scripts/pr605_runtime_dependency_inventory.py`, which imports `app.main.app`, enumerates registered FastAPI routes and their dependency-injection functions, and traverses direct absolute Python import edges to depth 3. This is a **runtime route inventory plus partial static module dependency graph**, not an exhaustive route-to-actual-call graph.
- `.github/workflows/ci.yml` now runs this script after backend dependency install and uploads `pr605-runtime-route-dependencies` as a build artifact. Script was committed at `084132fa7b8b6cb5136097c1cf5ce4f8bc1022b2`, workflow integration at `afaf029577f886224edd1188106baf272b8deb8a`.
- CI at `afaf029577f886224edd1188106baf272b8deb8a`: six observed workflows succeeded; main `CI` was pending at last check. **No report artifact inspected and no runtime inventory pass yet claimed.**

## Production traffic coverage: representative, not exhaustive
- Read-only Railway HTTP proxy logs: 301 sampled requests across 29 normalized method/path pairs (sampling window returned by connected service).
- Status distribution: 299 HTTP 200, one 401, one 403. High-volume paths include `GET /api/approvals` (33), `GET /api/auth/me` (32), `GET /api/organizations` (32), `GET /api/metrics/overview` (32). Lower-frequency routes include plays, workflows, enterprise, and inbound HubSpot webhook.
- The sample demonstrates **observed activity at specific HTTP endpoints**. It says nothing conclusive about voice WebSockets, autonomous task completion, every backend route, or handler-specific downstream calls.
- Railway distributed traces query for 2026-11-05 14:26–15:26 UTC returned **zero traces**. Service configuration previously showed tracing disabled. Complete production caller coverage therefore cannot yet be certified.

## Supabase event delivery evidence, with production binding caveat
- Connected project `smyeexlrqdpymwjmgzqu` (not yet proven to be Railway production) contains 44 `execution.outcome_finalized` outbox events, all `delivered`; no pending, retrying or dead events in current snapshot.
- All 44 have `delivered_handlers = {outcome_learning.record_run_outcome}`. This is strong evidence that the relay RPC acknowledged the registered outcome-learning handler **in that project**, but does not by itself prove that every event produced a useful model-learning record. The handler may skip a run without verified business outcome.
- Source trace: `domain_event_relay_scheduler.start_domain_event_relay_scheduler` registers source-lifecycle, customer-observation and conditional outcome-learning handlers. `DomainEventRelay._claim` scopes claims to registered handler types; `_dispatch` executes handlers and `complete_domain_event` marks success. The relevant project had 44 acknowledged deliveries through outcome-learning handler.
- Need actual production flag, worker process, downstream learning writes, observed delivery latency, and failures/replay tests to complete consumer certification.

## Run projection consistency: read-only aggregate check
- Full outer join on `workflow_runs.id = runs.id` in connected project: 801 matched IDs, 2 only in `workflow_runs`, 283 only in `runs`. The 283 may be legitimate run types without workflow counterparts: **not automatically missing mirrors**.
- Of 801 matched records, 38 have different status strings:
  - `partial_success → queued`: 30
  - `pending_approval → needs_approval`: 4 (possibly intentional status normalization)
  - `failed → running`: 2
  - `flagged_for_review → queued`: 2
- `failed → running`, `partial_success → queued`, and `flagged_for_review → queued` warrant investigation for stale projections or deliberate different status semantics. Do not automatically reconcile rows or make transactional behavior stricter until the canonical mapping and consumers are established.
- Earlier SQL inspection found `mirror_workflow_run_status_to_contract` catches exceptions with a warning, which could allow divergence. This remains a **plausible mechanism**, not a proven cause for these rows.

## Engineering remediation and verification gates
1. **ECO-051 / P0:** Certify the exact-head CI inventory artifact, compare registered routes to expected inventory, then add handler *call-site* edges and dynamic dispatch annotations (import edges alone are insufficient).
2. **ECO-052 / P0:** Configure privacy-safe route and span telemetry in a separately governed change; quantify observed production request coverage by route, surface, provider and task mode, including voice WebSockets and events.
3. **ECO-053 / P0:** Obtain a Railway-side non-secret Supabase project-ref attestation; do not infer production binding from which Supabase project has rows.
4. **ECO-054 / P0:** Define canonical workflow→run status mapping and compare matched records, timestamps, run types, sources and trigger transitions; write **read-only** discrepancy report before any mutation.
5. **ECO-055 / P0:** Verify acknowledged outcome events led to intended durable consumer side effects where appropriate; test conditional skip, idempotent replay, lease expiration, handler disablement, and crash/restart.
6. **ECO-056 / P1:** Distinguish legitimate `runs`-only workloads from orphan records and add documented invariant checks per run type.

## Gate conclusion
**Partially advanced, not complete.** A runnable exact-head inventory generator is committed and wired into CI. Production HTTP activity was sampled, and 44 outcome events were acknowledged in the connected project. However, exact-head inventory results, production Supabase binding, voice/caller coverage and full event side-effect certification remain open. No production mutation was executed.
