# PR #605 — Gate 27: release readiness and production acceptance

Status: **OPEN — preparation only; NOT CERTIFIED**. Owner direction: production-only live acceptance, no paid staging environment. Related: PR #605, issue #607, Gate 26 execution plan.

## 1. Scope and authority

Gate 27 is the release-readiness and post-deploy acceptance gate for the existing PR #605 modernization. It does not authorize a merge, deployment, production migration, telemetry activation, provider write, backfill, or legacy retirement. The owner's November 5 decision records same-person Security/Privacy and Operations/SRE approval as a **documented exception to independent review**, not independent certification. No new environment or paid-provider tests are to be provisioned for pre-merge certification.

## 2. Pre-merge exact-head evidence ledger

For the **final** PR SHA, record a URL, conclusion, relevant test count and skip count for each applicable check. Any code/documentation commit changes the head; recertify the resulting head.

| Check | Required evidence | Status at preparation |
| --- | --- | --- |
| Full CI | Backend pytest, web lint/typecheck/build, dependency audit, shared text/voice gate | **PENDING** at SHA `94a03d6`, run 42161171502 |
| Gate 26 isolated PostgreSQL | Actual temporary PostgreSQL migration, trigger, relay and durable idempotent consumer effect; zero skipped | Prior SHA `efc48dc6`: 26 passed; current SHA run 42161171425 in progress |
| Registered route inventory | Zero unexplained OpenAPI mismatches and unresolved wrappers | Current SHA run 42161171504 in progress |
| Cross-surface ownership | Source owner and caller/consumer inventory with no unexplained gaps | Current SHA run 42161171551 success |
| Privacy-safe edge telemetry | HMAC privacy contract and disabled-by-default checks | Current SHA run 42161171560 success |
| Run status contract | Versioned run-state contract and migration checks | Current SHA run 42161171661 success |
| Connector Governance | Authorization and governed-action checks | Current SHA run 42161171509 in progress |
| Other applicable workflows | Inspect all required checks; distinguish passed, failed, skipped and not run | In progress |

No skipped, queued or pending job counts as a pass. Investigate actual failing logs and rerun on repaired SHA. Track remaining gaps and explicitly defer paid-provider and deployed end-to-end acceptance.

## 3. Pre-merge decision packet (owner approval required)

Record: exact tested head SHA; required check conclusions and run URLs; material defects and dispositions; migration compatibility and rollback plan; feature flags default OFF; production backend/frontend service identifiers and intended deployment commit; owner approval timestamp. **Do not merge solely because this document exists.**

## 4. Production deployment readiness (separate approval)

Before deployment, record operator, deployment window, service/version identity, existing production version for rollback, health checks, error/latency baseline, incident abort criteria, tested rollback command/path, monitoring owner and on-call escalation. Do not enable telemetry, change database schema or execute provider writes as an implicit side effect of deployment. Verify the actual deployed commit equals the approved commit; stop if mismatched.

## 5. Post-deployment production acceptance matrix

Execute with explicitly scoped synthetic test tenants/accounts and least-privilege permissions. Start with non-mutating checks. Do not access real customer content. Live writes to providers, production migrations or enabling runtime telemetry require separate, specific approval and a defined expiry/rollback procedure. If telemetry is not authorized, mark correlation-dependent assertions **BLOCKED**, not passed.

| ID | Scenario | Evidence and pass condition |
| --- | --- | --- |
| P27-01 | Deployed version and health | Commit match, successful health probes, no new material error/latency regression |
| P27-02 | Real agent → play → workflow → connector | Real dispatch and provider authorization/readback, persisted typed causal IDs, not synthetic span-only logging |
| P27-03 | Workflow outcome → outbox → registered consumer | Triggered outbox event, relay delivery, registered consumer checkpoint and durable effect, no duplicate replay |
| P27-04 | Denied write and human approval | Unauthorized writes produce zero external effects; authorized write only with separately approved test account |
| P27-05 | Cancellation, revocation and retries | No post-cancel side effects; revoked credentials denied; restart/retry exactly-once durable effect |
| P27-06 | Privacy and tenant isolation | No cross-tenant read; no raw IDs, transcripts, tokens, provider payloads or secret keys in retained telemetry |
| P27-07 | Text and voice regression | Real text turns, voice continuity/barge-in/reconnect, bounded errors and latency, with actual recordings only if separately approved |
| P27-08 | Kill switch and rollback | Feature flag off verified, abort/rollback executed or safely rehearsed, service health restored |

Record per scenario: UTC time, operator, deployed SHA, tenant/test-account pseudonym, redacted evidence location, test action, expected vs observed, PASS/FAIL/BLOCKED, cleanup and rollback status. Do not equate the 26 isolated PostgreSQL tests with the complete deployed chain.

## 6. Release decisions

- **GO to merge:** all required exact-head checks passed, no unresolved critical defects, explicit owner merge approval.
- **GO to deploy:** explicit owner deployment approval, rollback readiness, production-safe flags OFF, operator and window recorded.
- **GO to production acceptance:** scoped test accounts, risk limits, monitoring and rollback owner confirmed; extra permission before telemetry or external writes.
- **FINAL CERTIFIED:** all required production scenarios independently evidenced and passed; unresolved blocks disclosed. Otherwise **PARTIAL / NOT CERTIFIED**.
- **Retirement:** separate decision only after replacement coverage, verified rollback and production evidence. No automatic legacy deletion.

## 7. Current gate status

Preparation initiated November 5, 2026. At the time of initial drafting PR head was `94a03d6db34efcf4439b9da4b3a96773e3e73f40` and draft/unmerged. Exact-head CI pending/in progress. Production not deployed or tested for this PR. Gate 27 remains **OPEN / NOT CERTIFIED**.
