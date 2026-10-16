# PR #429 audit remediation tracker

**Draft PR — not approved for merge, migrations, deploy, or flag activation.**

## Implemented (code on branch)

| Area | Change |
|------|--------|
| Idempotency | `claim_write_invoke_idempotency` + **claim_token / generation**; expired lease → **uncertain + reconciliation** (no re-invoke); `finalize_write_invoke_idempotency` rejects stale workers |
| Ledger security | REVOKE PUBLIC/anon/authenticated on table + RPC; no member RLS policies |
| Approval scope | Digest + missing scope; ReAct + **tool_service run** boundary; **action-specific argument sealing** (amount/status/body/permissions; case-preserving ids; fail-closed empty targets) |
| MSP | Parent RLS migration **withdrawn** (`MSP_RLS_PARENT_ACCESS_DEFERRED.md`) |
| Queue | Processing list + ack/requeue; `WORKFLOW_QUEUE_FAIL_CLOSED`; event-trigger fail when queue required |
| Lifecycle | `composer_envelope_from_turn`; COMPLETED → customer `verifying` when unverified |
| Defaults | `WRITE_INVOKE_IDEMPOTENCY_ENABLED=false`, `EVENT_TRIGGER_USE_WORKFLOW_QUEUE=false` |

## Tested (local)

| Suite | Command | Result |
|-------|---------|--------|
| Helper / unit | `pytest backend/tests/services/test_write_invoke_idempotency.py backend/tests/services/test_write_approval_fingerprints.py backend/tests/services/test_write_invoke_provider_harness.py backend/tests/workers/test_workflow_queue_recovery.py -q` | Run in CI / dev (see commit message) |
| Real Postgres idempotency | `pytest backend/tests/db/test_write_invoke_idempotency_pg.py -q` with `GRAVITRE_REQUIRE_PG=1` | **CI gate on `ubuntu-latest`** (installs PostgreSQL; fails if skipped) |
| Redis queue integration | `pytest backend/tests/workers/test_workflow_queue_redis_integration.py -q` | **CI gate** with local `redis-server` |
| Release 1 sessions route | `pnpm test` → `__tests__/api/sessions-route-auth.test.ts` | Auth before org; sanitized 503 errors |
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
- Multi-replica Redis queue semantics (visibility timeout / exclusive consumer)
- Release 1 authenticated matrix on **gravitre.app** after merge (not helper-only)
- Briefing items (Haiku/Argon, PSA, external MCP) — separate tracks

## Migrations

| File | Disposition |
|------|-------------|
| `20261014100000` | Staging first; service-role claim tests required |
| `20261014110000` | **Withdrawn** |
| `20261014060000` | Authorization review before apply |

See also `provider_idempotency_support_matrix.md`.
