# P27-04 — Graph executor restart and provider readback evidence

Owner: PR #611. This is an **offline implementation checkpoint**, not production certification.

## Crash/restart scenarios

- `test_graph_checkpoint_process_recovery_pg.py`: a child process persists a uniquely keyed synthetic provider-effect receipt and graph checkpoint in disposable PostgreSQL through production repository methods, then exits abruptly (`os._exit(79)`). A fresh client invokes the production `resume_paused_workflow_graph` scheduler; the checkpointed write node must not execute again. The downstream node is a deterministic fixture; final notification fanout is adapted.
- `test_canonical_repository_persistence_pg.py`: actual outbox SQL claim survives worker-process death and a new relay consumes after lease expiry with no duplicate durable effect.
- Failure boundary: **provider accepted a write but its receipt/checkpoint was not committed**. This is not resolved by skipping checkpointed nodes. A fresh idempotency key or blind replay is prohibited. A provider-specific reconcile/readback must establish `applied` or `not_applied`, otherwise the run remains `verification_inconclusive` and requires operator intervention.

## Sandbox provider acceptance — separately authorized

- Manual-only workflow: `.github/workflows/master-qa-p27-sandbox-readback.yml`.
- Script: `backend/scripts/p27_sandbox_provider_readback.py`.
- Secrets are NEVER added to PR CI. Configure GitHub environment `p27-provider-sandbox` with required reviewers/protection, `P27_SANDBOX_BASE_URL`, `P27_SANDBOX_ALLOWED_HOST` and `P27_SANDBOX_TOKEN`. Do not point at production or customer accounts.
- The generic contract assumes an approved provider adapter with `POST /actions` returning `id` and `idempotency_key`, `GET /actions/{id}` returning an authoritative `status: applied` and the same identifiers. Duplicate POST with identical key must identify the same object. **A real provider-specific mapping is required**; generic contract green is not evidence of an actual HubSpot/Slack/etc operation.
- The workflow must be deliberately dispatched with `APPROVE_NONPRODUCTION_WRITE` after sandbox operator consent. No automatic live operation runs on a PR.

## Exit requirements still blocked

1. Exact-head CI green, including PostgreSQL checkpoint test and readback contract negatives.
2. Provider-specific sandbox adapter independently reviewed against its real API semantics and resource cleanup, with real retrieved object readback.
3. Provider callback/timeout uncertainty, process kill *between provider commit and local checkpoint*, reconciliation, revocation, tenant scoping, and fail-closed retry validated.
4. Full production worker restart, deployed SHA, external readback and P27 production acceptance remain **NOT RUN** until separately authorized.

No migrations, deployment, merge, paid live calls or production resource creation are permitted by this checkpoint.
