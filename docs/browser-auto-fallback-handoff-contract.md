# Automatic Browser Use → Playwright handoff contract

Status: implementation contract, not evidence of an operational fallback or certification.

## Atomic authority transfer

The trusted broker must execute a single durable compare-and-swap transaction that checks the current job generation, original worker lease, tenant and task identity, cancellation/revocation state, and recovery reservation. It must verify an authenticated pre-action checkpoint and independent side-effect reconciliation. The transaction must invalidate the Browser Use lease, increment the execution generation, and allocate exactly one exclusive Playwright lease. Concurrent recovery claims must lose. A failed transaction must not launch an adapter.

## Launch and restore

The scheduler may launch a new isolated Playwright sandbox only after the broker commits the lease transfer. The sandbox receives scoped checkpoint data, task identity, and a short-lived lease token; it never receives reusable approval grants. Before each external effect, the broker checks the active lease generation, tenant scope, cancellation, revocation, and action-specific approval. Browser Use and Playwright must use the same write-audit and idempotency boundaries.

## Fail-closed outcomes

If the last action may have produced an external effect, do not replay it. Enter reconciliation until independent evidence resolves the outcome. Cancellation, revoked approval, stale lease, missing checkpoint, malformed checkpoint, and ambiguous side effects must block automatic launch. Retries are bounded and must not spawn competing sessions.

## Acceptance tests

- Two recovery coordinators race for one reservation: exactly one Playwright lease is issued.
- Browser Use worker attempts an action after fencing: broker rejects it.
- Cancellation/revocation races with lease transfer: no unauthorized write occurs.
- Browser crash before a verified pre-action checkpoint: no automatic replay.
- Crash after a possible submit but before acknowledgment: reconciliation, not resubmit.
- Broker process restarts after transfer commit: the durable generation prevents double launch.
- Playwright restores verified task context, requests fresh action approvals, and continues safely.
- Independent external write audit records zero unauthorized or duplicate writes across both adapters.
- Measure p50/p95 recovery latency separately for detection, fencing, launch, restoration, and authorization.

Do not merge, deploy, or enable production fallback until the executable handoff and matched end-to-end tests pass against the exact release SHA.
