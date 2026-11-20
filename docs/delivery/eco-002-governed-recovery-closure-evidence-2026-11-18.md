# ECO-002 — governed execution and recovery closure ledger (2026-11-18)

**Engineering status: active and release-blocking. Finding NOT CERTIFIED.** This document is evidence bookkeeping for the existing 43-finding register; it is not a new plan and does not authorize merge, deployment, DB rollback or external customer writes. ECO-002 inherits ECO-001's cross-surface authority requirements.

## 1. Evidence already established (bounded development verification)

- Exact-head `980eace16daa3b881d9e7d4d3a7edfb39ea88b90`: isolated connector_chat approval/crash/restart acceptance **passed**, QA01 core job 134935375838 in run 44341558359. Synthetic provider receiver, real QA Supabase approval and fenced ledger. Expected duplicate/rejected HTTP results, two expected provider effects, one canonical completed claim, no unauthorized claims.
- Exact-head `2b73e42e134a891ebd11ae310804e84fcce134da`: QA04 governed execution run 44350086557 **passed**; independent PostgreSQL provider-receiver development job 134965083574 reports **9 + 38 passed**. Outcome ownership job 134965083601 reports **134 passed**. Isolated approval crash/restart job 134964122631 **passed**, including no duplicate dispatch after simulated worker exit. All are synthetic provider or isolated QA evidence, **not independently verified live third-party provider effects**.
- New lease-token comparison, malformed-queue rejection and authoritative-negative readback protections were committed later and require **new exact-head targeted tests**. Historical passing runs do not certify changed head source.

## 2. Canonical caller and recovery ownership

| Boundary | Current source | Already demonstrated | Still outstanding |
| --- | --- | --- | --- |
| Signed Chat approval | `app/routers/workflows.py` -> `chat_connector_execution_service.py` -> `tool_registry.py` -> `tool_service.py` | Isolated QA authenticated approval, tenant-owned connector, original arguments, denied/rejected/replayed approval | All native OAuth providers, in-flight actual provider revocation, production feature flags |
| Chat/Agent durable write | `tool_service.invoke_tool` -> `write_invoke_idempotency.py` -> PostgreSQL claim/bind/finalize RPC | Joined Chat/Agent PostgreSQL receiver and synthetic crash/restart; provider-side effect count independently observed in local receiver | All active callers: Voice, ReAct, Plays, Canvas, alternate tools and live provider receipt |
| Leased recovery after uncertain delivery | `write_recovery_worker.py` -> `write_recovery_service.py` -> `outcome_reconciliation.py` -> fenced SQL settle/defer | Real PostgreSQL lease, persisted original arguments and account, no unleased/stale-token readback intended; synthetic readback positive/negative | New exact-head targeted regression result and provider-specific GET under original OAuth identity |
| Historical reconciliation and domain events | Ledger, outcome writer and independent domain-event/outbox subscriber in joined tests | Bounded synthetic consumer acceptance | Historical completeness, authorized backfill, actual deployed consumer/readback |

The source inventory above is deliberately non-exhaustive. Retire no legacy execution path until caller-by-caller parity is shown against the canonical ledger.

## 3. Provider readback closure protocol — NOT EXECUTED

Requires an approved **test-only** connected provider account and a disposable resource; never use an unknown customer account. Record provider name/account, tenant ID, OAuth consent scope, run SHA, server request ID, ledger claim token, original arguments, provider-generated record ID, independent provider audit/GET evidence and cleanup receipt **without storing tokens or PII**.

1. Test denied approval and cross-tenant connector IDs: no provider request, no ledger claim.
2. Approve one harmless disposable write through signed Chat and one Agent/Play path: compare tenant, connector, action and exact arguments across ingress, durable ledger and independently observed provider record.
3. Drop the provider acknowledgement after the provider accepted one request; restart the worker and verify no second write. Acquire a real recovery lease, then GET the **same** original account's record.
4. For a verified applied effect, settle completed through fenced CAS and prove replay returns the original result; for unknown/paginated/format-mismatched results keep claim uncertain and blocked.
5. Permit a negative result only with provider-specific, exhaustive, filtered and **authoritative_absence** evidence. A generic empty list or mismatched formatting is **not** sufficient.
6. Revoke approval before dispatch; confirm no provider request. Test revocation during dispatch and verify it cannot be falsely reported as cancelled. Verify second approval and stale recovery lease cannot read or write.
7. Independently inspect provider audit/readback and durable SQL state after restart; prove cleanup and no leaked QA data.

**No live account or provider evidence is recorded here.**

## 4. Deployment and rollback closure protocol — NOT EXECUTED

Requires explicit release approval; this document performs no deployment. In an approved isolated environment first record exact commit SHA, schema migration version, prior known-good executable and current connected provider list. Dry-run migration compatibility, critical ingress checks, a controlled provider canary and independent receiver readback. Preserve persisted approval/claim/outbox states.

For an actual failure, stop **new** governed writes/worker scheduling through verified controls, leave uncertain/in-progress claims fenced, roll back **application code to the recorded prior deployment**, do not drop or downgrade ledger tables containing unsettled claims, then independently reconcile and read back original provider effects before reopening writes. Prove CAS, tenant denial, replay blocking, data/state conservation and restored service health; record rollout/rollback SHA, timestamps, operator authorization and external receipt. A written procedure is not rollback execution evidence.

## 5. Closure decision

The master register stays `fix_verified=false`, `rollback_verified=false`, `downstream_effect_verified=false`, `owner_approval=false`, and release-blocking until **all** original finding-specific criteria pass at one current exact SHA, with independent provider/consumer proof, deployed rollback and owner signoff. A green development workflow is not one of the twelve final QA certifications.
