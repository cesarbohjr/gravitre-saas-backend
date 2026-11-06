# PR #605 — Gate 25: real relay acceptance harness and independent approval status

Date: 2026-11-05. **Status: implementation committed; independent CI rerun pending; deployed acceptance explicitly blocked by approval issue #607.**

## Verified CI baseline

On commit `73cb4ea28ad3eaf60d4de74bbc80085137075a4d`, the isolated [PR605 privacy contract workflow 42122248473](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42122248473) completed SUCCESS: **14 passed** and one pytest configuration warning. Independent ownership, registered routes, run status, migration safety and connector governance workflows succeeded. The previous integrated [CI run 42122248795](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42122248795) was **IN PROGRESS** on the last inspection: web build, dependency audit, shared text/voice gate successful, backend pytest still in progress. Thus full integrated CI was not yet certified.

The new latest-head [CI run 42136130688](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42136130688) was PENDING and the new [privacy/relay workflow 42136130387](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42136130387) QUEUED immediately after commits. This document does not assert either is green. CI must be checked against the **final** SHA after documentation; past-head passes are not a substitute.

## GitHub file-write remediation

Earlier GitHub file-create/update actions returned internal tool errors and left no new test file. Retrying a minimal `create_file` succeeded (commit `cd5d8d2ea47f9f1b77f2dd84a0a73a79e173b395`); subsequent `update_file` calls committed the actual harness and CI workflow. The connector write path is demonstrably functioning again; the root cause of intermittent tool failure was **not** established. Do not interpret a transient successful retry as a repository-wide reliability certification.

## Actual application-level relay acceptance preflight (synthetic)

New `backend/tests/services/test_pr605_relay_acceptance.py` invokes the **real** `DomainEventRelay.run_once` implementation rather than calling telemetry log helpers alone. It supplies a synthetic in-memory outbox/RPC state machine and registers actual event handlers. No credentials, providers, external network, Postgres or customer records are accessed.

The three cases assert:
1. **Consumer side effect and settlement:** a real registered handler mutates an observable in-memory effects list exactly once, the outbox becomes `delivered`, only one `complete_domain_event` call occurs, and no raw workflow-run/event ID leaks into correlation logs.
2. **Failure / retry / partial handler bookkeeping:** a stable handler effect persists across a subsequent flaky handler failure, a second relay tick retries only the flaky handler and completes the event. `fail_domain_event` and `complete_domain_event` are exercised and their calls checked.
3. **No registered consumer:** `_claim` returns no event and leaves the synthetic outbox pending rather than falsely completing an event.

`.github/workflows/pr605-runtime-edge-contract.yml` now runs both this real relay preflight and the existing **14-test** privacy contract under `--noconftest`, then compiles the implicated runtime modules. **Expected 17 focused tests**, subject to actual CI logs. No skipped test counts as a pass.

**Strict evidence boundary:** Because the RPC is a fixture, these are real *Python dispatch and handler side effects*, not actual deployed Postgres durability, external provider effects, authenticated HTTP ingress or production end-to-end trace equivalence. No claim of production business side-effect certification is permissible.

## Approval and deployment status

Formal [Security/Privacy + Operations issue #607](https://github.com/cesarbohjr/gravitre-saas-backend/issues/607) has **zero approval comments** at inspection; PR #605 also has zero formal reviews. Neither has a recorded Security/Privacy signoff or Operations signoff. The accountable reviewers are not established. Opening the issue and making code changes **does not** grant authority for live collection.

The authorized acceptance rollout requires both named, dated signoffs with data-purpose/notice and retention controls, synthetic acceptance tenancy, HMAC key provisioning/rotation, log sink and tenant access restrictions, sampling/cost/latency and rollback owner, plus a defined start/end collection window and no customer-data reuse. Separately complete final-SHA full integrated CI. Only then run an isolated, explicitly approved acceptance-environment exercise showing authentic HTTP/agent/plan/run/connector→outbox→consumer operations, controlled write denials and cancellations, evidence of actual durable writes and real consumer effects, tenant isolation and a tested telemetry off-switch. **Do not configure production telemetry or execute paid/provider writes to shortcut this gate.**

## Candidate retirement eligibility

ReAct/voice/agent/workflow/connector alternatives, dual run projections, Redis, Temporal, and alternate frontend remain **NOT CERTIFIED** for removal. Domain outbox/relay remains KEEP. Synthetic application preflight does not establish all active consumers or replacement coverage. Historical reconciliation/migration and production database identity remain separate unresolved gates.

**PR remains draft, unmerged, undeployed. No legacy retirement, production config change, migration or reconciliation was performed.**
