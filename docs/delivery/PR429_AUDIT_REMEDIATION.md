# PR #429 audit remediation tracker

**Draft PR — not approved for merge, migrations, deploy, or flag activation.**

## Implemented (code on branch)

| Area | Change |
|------|--------|
| Idempotency | `claim_write_invoke_idempotency` RPC; claim-before-invoke; uncertain/failed finalize; service_role GRANTs |
| Ledger security | REVOKE PUBLIC/anon/authenticated on table + RPC; no member RLS policies |
| Approval scope | Digest + missing scope; ReAct + **tool_service run** boundary; **write target fingerprints** |
| MSP | Parent RLS migration **withdrawn** (`MSP_RLS_PARENT_ACCESS_DEFERRED.md`) |
| Queue | Processing list + ack/requeue; `WORKFLOW_QUEUE_FAIL_CLOSED`; event-trigger fail when queue required |
| Lifecycle | `composer_envelope_from_turn`; COMPLETED → customer `verifying` when unverified |
| Defaults | `WRITE_INVOKE_IDEMPOTENCY_ENABLED=false`, `EVENT_TRIGGER_USE_WORKFLOW_QUEUE=false` |

## Tested (local)

| Suite | Command | Result |
|-------|---------|--------|
| Helper / unit | `pytest backend/tests/services/test_write_invoke_idempotency.py backend/tests/services/test_write_approval_fingerprints.py backend/tests/services/test_write_invoke_provider_harness.py backend/tests/workers/test_workflow_queue_recovery.py -q` | Run in CI / dev (see commit message) |
| Real Postgres idempotency | `pytest backend/tests/db/test_write_invoke_idempotency_pg.py -q` | **PASS when `GRAVITRE_PG_BIN` / PostgreSQL installed**; **SKIPPED** otherwise |
| Engineering gates | `python scripts/verify-release-engineering-gates.py` | Updates `release-engineering-gates.json` |

## Production-verified

| Item | Status |
|------|--------|
| Idempotency ledger in prod | **NOT APPLIED** — migration `20261014100000` absent in prod |
| Release 1 authenticated matrix | **NOT RUN** — see `RELEASE1_ACCEPTANCE_STATUS.md` |
| Freshservice / HubSpot E2E | **NOT RUN** |
| Flag activation | **NOT DONE** — keep defaults off in Railway until gates pass |

## Still open

- Full provider-path argument sealing for **dynamic** chat/voice/MCP (constraint contract or fresh approval)
- Lifecycle consumers in **web/voice/ROI** surfaces (backend envelope only)
- **All** model-call attribution paths (ReAct `complete_with_tools`, etc.)
- Redis integration tests: worker death after dequeue, poison DLQ, multi-replica
- Release 1 `/api/sessions` **401/403** (route not in worktree; prod 500 on probe)
- Briefing items (Haiku/Argon, PSA, external MCP) — separate tracks

## Migrations

| File | Disposition |
|------|-------------|
| `20261014100000` | Staging first; service-role claim tests required |
| `20261014110000` | **Withdrawn** |
| `20261014060000` | Authorization review before apply |

See also `provider_idempotency_support_matrix.md`.
