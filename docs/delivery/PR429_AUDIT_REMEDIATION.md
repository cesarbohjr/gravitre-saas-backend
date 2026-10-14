# PR #429 audit remediation (2026-10-14)

Tracks engineering fixes from `Gravitre_Shipping_Audit_2026-10-14.md` (user audit). Production was not changed.

## Addressed in this branch (engineering)

| Finding | Remediation |
|---------|-------------|
| Idempotency cache-only | Atomic `claim_write_invoke_idempotency` RPC + in_progress/uncertain states; claim before invoke |
| Ledger member tampering | REVOKE authenticated/anon; no RLS member policies; SECURITY DEFINER claim only |
| Repeat-suppression key | Chat key includes `turn_id`, connector, optional `_write_idempotency_nonce` |
| Default-on unsafe flags | `WRITE_INVOKE_IDEMPOTENCY_ENABLED` and `EVENT_TRIGGER_USE_WORKFLOW_QUEUE` default **false** |
| Approval scope gaps | Digest verification, missing scope for approved runs, ReAct canvas path uses `block_invoke_by_approval_scope` |
| MSP RLS broader than flag | **Removed** migration `20261014110000`; see `MSP_RLS_PARENT_ACCESS_DEFERRED.md` |
| Queue crash loss | `BRPOPLPUSH` to processing list + ack/requeue in worker; optional `WORKFLOW_QUEUE_FAIL_CLOSED` |
| Event trigger queue fallback | Fail-closed path when queue required but unavailable |

## Local test evidence (2026-10-14, pre-merge review)

Remediation slice (not production / not pg concurrency):

```
pytest tests/services/test_write_invoke_idempotency.py \
  tests/services/test_workflow_approval_scope_audit.py \
  tests/services/test_workflow_approval_scope.py \
  tests/services/test_canvas_write_approval_scope.py -q
→ 10 passed, 1 warning in ~8s
```

Full engineering gate bundle: `python scripts/verify-release-engineering-gates.py` → `docs/delivery/release-engineering-gates.json`.

**NOT RUN:** Postgres concurrent claim races, worker crash after dequeue, authenticated Release 1 matrix.

## Still open (requires follow-up PRs / acceptance)

| Finding | Status |
|---------|--------|
| Lifecycle envelope consumers (UI/voice/ROI) | Persist only; wire composers/projectors |
| Full argument binding per approved step | Action-name scope only; parameter fingerprints not sealed |
| Provider-specific idempotency support matrix | Generic header only |
| Cost capture for all model iterations | Not in #429 scope on this branch |
| Real-DB concurrency / crash tests | Add pg integration tests before enablement |
| Authenticated Release 1 acceptance | Operator runbook |

## Migration disposition

| Migration | Action |
|-----------|--------|
| `20261014100000` | Apply only after staging claim/replay tests with service role |
| `20261014110000` | **Withdrawn** |
| `20261014060000` | Review link-management before apply |
