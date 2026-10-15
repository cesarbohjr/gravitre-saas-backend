# Master-plan engineering closeout

The user authorized completion of the existing plan on 2026-10-15. Continue
implementation on draft #431 without asking which track to implement next.
Keep production evidence separate from code/test completion. Existing release
instructions still govern exact migration approval and production activation.

## Current evidence

At `7ad397d`, CI run 38817159040 passed 11,006 backend tests (7 unrelated skips),
web tests/lint/typecheck/build, text/voice parity, integration smoke, PostgreSQL
idempotency and billing gates, and Redis recovery. Billing Playwright skipped.
The historical `20250220000006` reset failure remains a release blocker;
do not edit applied history or silently disable its CI gate.

## Execution order and remaining deliverables

| Order | Existing platform capability to extend | Engineering closeout | Acceptance still required |
|---|---|---|---|
| 1 | Billing/model_calls/usage scheduler | Durable recovery with immutable per-call evidence, bounded retries and allowance consistency; closed-period handling and historical audit | New PG gates, staging, ledger/Stripe reconciliation |
| 2 | Shared write governance/lifecycle | Dynamic resolved-argument review across chat/voice/MCP; durable verification and stale-run proof | Provider commit/timeout and late UI/voice/ROI proof |
| 3 | Source lifecycle/intelligence | Complete document/memory/snapshot revocation and consent lineage; correlated context spans and latency report | Source delete/disconnect through every recall path; P50/P95 evidence |
| 4 | Existing service-desk outcomes | PSA baseline/time-entry coverage, per-run actual cost, measured versus estimated ROI | Freshservice and HubSpot live fixtures, baseline comparison |
| 5 | Existing org membership | Explicit MSP grants and client switching across credentials/runs/approvals/audit | Real-DB cross-client denials and authenticated UI |
| 6 | Existing workflow runner | Scoped hashed API credentials, external MCP over the governed runner, OAuth lifecycle | Revocation/rotation/scope tests and external client proof |
| 7 | Model catalog/router/guardrails | Quality evaluation harness, atomic budget reservations, routing eligibility | Measured workflow quality/cost/latency and concurrency |
| 8 | Release verification | Reconcile migration history, prepare exact flag/migration rollout and rollback package | Release 1 authenticated matrix, production deployment alignment, vendor reviews |

## Durable recovery draft

Migration `20261015232327` adds billing evidence/retry columns to `model_calls`,
a service-only period allowance contract, and RPCs that reuse the existing
atomic ledger functions. Client writes to `model_calls` are revoked so tenant
admins cannot forge billable evidence. Inspect direct client writers in staging
before applying that change; existing backend writes keep service-role access.

When the recovery flag is enabled, the streamed chat/voice context reads the
plan before dispatch and persists the included allowance and computed credits
with each billable model call. Local response-cache hits and embeddings billed
by the RAG path do not receive assistant recovery evidence. Missing schema or
cross-org attribution never falls back to untagged recovery evidence.

The usage scheduler settles at most 100 calls per tick using row locks with
SKIP LOCKED, the same allowance advisory lock, and atomic usage/overage writes.
Calls must be at least ten minutes old and within the current UTC month. Failed
calls back off for up to eight attempts; errors retain SQLSTATE only. Legacy
untagged calls, poison rows after the retry limit, and closed billing months
require an explicit reconciliation report; the sweep never guesses charges.

Rollout order: reviewed migrations `20261015032117` then `20261015222156` then
`20261015232327`; schema-compatible app; `USAGE_ATOMIC_ENABLED=true`, then
`ASSISTANT_BILLING_ATOMIC_ENABLED=true`, finally
`ASSISTANT_BILLING_RECOVERY_ENABLED=true` after staging acceptance. All remain
off in production here. A mid-period allowance change blocks settlement;
proration/credit adjustments need a defined business rule and reconciliation.

## Completion rule

No row is shipped solely because its code is merged or CI passes. Close each
row against its user-facing consumers and cited production acceptance. Keep
engineering work moving while named credential/vendor/product decisions remain
in the final operator package.
