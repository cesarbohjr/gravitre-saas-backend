# P27-04 — Graph executor restart and provider readback evidence

Owner: PR #611. This is an **offline implementation checkpoint**, not production certification.

## Crash/restart scenarios

- `test_graph_checkpoint_process_recovery_pg.py`: a child process persists a uniquely keyed synthetic provider-effect receipt and graph checkpoint in disposable PostgreSQL through production repository methods, then exits abruptly (`os._exit(79)`). A fresh client invokes the production `resume_paused_workflow_graph` scheduler; the checkpointed write node must not execute again. The downstream node is a deterministic fixture; final notification fanout is adapted.
- `test_canonical_repository_persistence_pg.py`: actual outbox SQL claim survives worker-process death and a new relay consumes after lease expiry with no duplicate durable effect.
- Failure boundary: **provider accepted a write but its receipt/checkpoint was not committed**. This is not resolved by skipping checkpointed nodes. A fresh idempotency key or blind replay is prohibited. A provider-specific reconcile/readback must establish `applied` or `not_applied`, otherwise the run remains `verification_inconclusive` and requires operator intervention.

## Sandbox provider acceptance — separately authorized

- Manual-only workflow: `.github/workflows/master-qa-p27-sandbox-readback.yml`.
- **Concrete HubSpot adapter**: `backend/scripts/p27_hubspot_sandbox_readback.py` uses HubSpot `GET /account-info/v3/details`, `POST /crm/v3/objects/contacts/batch/upsert`, `GET /crm/v3/objects/contacts/{id}?properties=email,firstname,lastname`, then repeats the *same* upsert and reads again to detect an unintended duplicate.
- Before creating any record, the adapter checks the exact expected portal ID AND that HubSpot classifies it as `DEVELOPER_TEST`, `APP_DEVELOPER`, or `SANDBOX`. Ordinary `STANDARD` portals are rejected. A unique `p27qa...` marker and an explicitly configured QA-only email domain ensure a synthetic test contact.
- Configure GitHub environment `p27-provider-sandbox` with required reviewers and environment variables `P27_HUBSPOT_SANDBOX_PORTAL_ID`, `P27_HUBSPOT_QA_EMAIL_DOMAIN`; set only the protected environment secret `P27_HUBSPOT_SANDBOX_TOKEN`. The account requires appropriate CRM contact read/write API scopes. Do not use the connected standard/production HubSpot account.
- Operators dispatch the workflow manually and type `APPROVE_NONPRODUCTION_WRITE`. The workflow must NOT be part of PR CI; the PR tests `test_hubspot_sandbox_readback_contract.py` against an offline fake of the actual HubSpot request/response shapes.
- Live execution and cleanup of the created contact must be reviewed and evidenced separately. **No real HubSpot write or authoritative provider GET has occurred in this PR.**

## Exit requirements still blocked

1. Exact-head CI green, including PostgreSQL checkpoint test and readback contract negatives.
2. Provider-specific sandbox adapter independently reviewed against its real API semantics and resource cleanup, with real retrieved object readback.
3. Provider callback/timeout uncertainty, process kill *between provider commit and local checkpoint*, reconciliation, revocation, tenant scoping, and fail-closed retry validated.
4. Full production worker restart, deployed SHA, external readback and P27 production acceptance remain **NOT RUN** until separately authorized.

The recovery SQL migration is committed but NOT applied to production. No deployment, merge, paid live calls or production resource creation are permitted by this checkpoint.

## Ambiguous commit before local receipt — P27-05

- Production `resume_paused_workflow_graph` now runs `_reconcile_interrupted_graph_steps` **before** erasing `_graph_execution` and transitioning to running. It reads outstanding `workflow_steps` through the canonical repository, reconstructs the action, and calls the existing `_reconcile_step`/provider source-of-record path.
- `applied` needs `verified: true` evidence to mark the prior step completed and skip its node. `not_applied` must be supported by a complete result set or authoritative ID-based field comparison to permit a new governed invocation; a bare empty first page is insufficient. `unknown` blocks resume with persisted checkpoint untouched.
- `test_ambiguous_provider_commit_recovery_pg.py` creates a provider-side effect in a separate SQL source, exits an OS process before the workflow receipt is saved, and invokes the actual graph-resume scheduler against a fresh SQL client. Cases: `applied`, `not_applied`, `unknown`, `incomplete_absence`, `unverified_applied`. Provider lookup is deterministic **local source-of-record simulation**, not a production provider call.
- **Remaining risk**: provider adapters that cannot prove exhaustive negative readback and connector families not yet covered by pre-dispatch journaling remain blocked. This is not a blanket exactly-once external execution claim.

## P27-06 — Atomic orphan detection, ownership and recovery (unmerged)

- Migration: `supabase/migrations/20261107235500_p27_graph_recovery_leases.sql` creates service-role-only RPCs for atomic stale-run claim, owner-token validation, renewal and release. Claim selects only runs with a durable `_graph_execution` checkpoint AND an old `running` step, transitions `running -> paused` atomically with lease ownership using `FOR UPDATE SKIP LOCKED`. If the recovery worker itself dies, only a prior `executor_in_flight` paused run with an expired owner lease is claimable again.
- `backend/app/services/workflow_orphan_reconciler.py` calls the existing production `resume_paused_workflow_graph` with a claim token and heartbeat. Unknown provider readback leaves the run paused with checkpoint intact, no outbound retry.
- `backend/app/workers/workflow_worker.py` polls for orphans at the configured interval **only when `WORKFLOW_ORPHAN_RECOVERY_ENABLED=true`**. The default is `false` until migration, sandbox provider readback, staging approval and operational monitoring are complete.
- The graph runtime verifies its SQL recovery owner before further node dispatch, rejects concurrent manual resume while another owner holds a lease, and captures narrow record lookup selectors with a pre-dispatch checkpoint for direct mutating connector nodes and nested workflows. Parallel delegated agents retain their existing execution semantics; they are NOT silently eligible for this automatic recovery path.
- An existing Redis-claimed worker also checks its SQL workflow status before issuing subsequent connector writes while recovery is enabled, preventing it from sending another action after the SQL claim parked the run.
- Regression evidence: `test_orphan_graph_claim_pg.py` (six parallel candidates; one winner; stale token fenced; recent activity ignored; expired crashed owner reclaimed), `test_graph_pre_dispatch_journal_pg.py` (checkpoint persisted before provider transport; manual resume ownership), `test_worker_orphan_tick.py` (enabled vs disabled poll and Redis worker parked-run rejection). All use disposable PostgreSQL or isolated no-network fakes.

### Deployment order and withheld acceptance

1. Merge and apply the SQL migration **before** deploying application code. Require migration success and role-execute denial for `authenticated` and `anon`.
2. Complete independent security/Ops review of lease behavior, long-running calls, cross-tenant RLS, cancellation and rollback.
3. Connect and verify a **separate HubSpot developer-test portal** with expected portal ID; run manual provider readback via protected environment and archive exact evidence.
4. Verify staging kill/restart with real worker processes, concurrent claims, source-of-record idempotency and alerting. Only then consider `WORKFLOW_ORPHAN_RECOVERY_ENABLED=true` in controlled rollout.
5. This PR is draft/unmerged/undeployed; production writes, migrations and activation have **not** been executed.

## P27-07 release-path correction — zero additional infrastructure spend

The operative owner-approved acceptance plan is `docs/delivery/p27-07-sandbox-and-staging-acceptance.md`, updated to use **existing Railway production backend/Redis and the existing STANDARD Gravitre HubSpot portal** for narrowly scoped live QA because there are no live customers yet. A prior separate Railway test environment incurred charges and was removed. **Do not create new staging/test infrastructure or a separate paid account.**

Earlier passages in this file requiring a developer-test HubSpot portal or staging Railway deployment document a superseded proposal; **they are not current release prerequisites**. The HubSpot script currently hard-rejects STANDARD portals and must receive a reviewed explicit-live-test guard plus offline negatives before touching the existing portal. A Railway worker interruption likewise requires a controlled process-specific execution plan and approval; the absence of customers is not blanket consent to kill production. Production rollout stays OFF until live acceptance is demonstrated.
