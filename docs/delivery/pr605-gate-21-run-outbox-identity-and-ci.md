# PR #605 — Gate 21: exact-head CI, verified outbox/run identity and privacy-reviewed production evidence

Date: 2026-11-05. **Release status: BLOCKED.** This is a source-grounded engineering checkpoint, not production privacy approval.

## 1. CI evidence and remaining certification gate

Previous Gate 18 source-inventory workflow [42111333265](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42111333265) passed 6 focused tests, with 12 owner source modules, 1,001 AST callsites and two retained JSON reports. Previous Gate 19 privacy workflow [42112109177](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/42112109177) passed five tests. These **do not certify subsequent PR heads**.

The Gate 20 exact-head run `42113006545` (privacy) was **queued** when inspected; full CI `42113006427` was **pending**, with other applicable workflows queued. No failure log existed for those queued jobs, so no speculative repair was made. The current head after Gate 21 documentation must receive its own exact-head full CI and isolated privacy-test certification. Skips are not passes.

## 2. Concrete, verified existing linkage found in deployed-baseline code

The existing migration `supabase/migrations/20261012024141_domain_event_outbox.sql` defines a transactional trigger `emit_workflow_run_terminal_event`: on terminal `workflow_runs` updates it inserts `event_type='execution.outcome_finalized'`, `aggregate_type='workflow_run'`, `aggregate_id=NEW.id::text` into `domain_event_outbox`. This is a source-defined FK-equivalent **logical** link between the owning workflow run and the durable event; no timestamp or text-similarity inference is required.

This is distinctly different from the earlier unrelated `plan_id`, `run_id`, and outbox `id`. The trigger establishes the particular run→outbox relationship only for verified `execution.outcome_finalized` rows. It does **not** establish that a plan ID equals a run ID, that every play/connector uses that workflow run, or that a consumer's side effect succeeded.

## 3. New Gate 21 implementation

- `backend/app/services/runtime_execution_edge_telemetry.py` now contains `emit_outbox_run_link`. It requires the existing explicit disabled-by-default flag and dedicated HMAC key, exact event type and aggregate type, numeric outbox primary-key string, and UUID-shaped run aggregate identity. It writes only shortened HMAC digests (`event` and `run`) with a fixed `workflow_run_outbox` label; no raw tenant, run, event, payload or transcript value.
- `backend/app/services/domain_events.py` calls it from the trusted claimed event-row dispatch before handler execution. Generic event types such as `source.disconnected` do **not** produce a workflow-run link.
- `backend/tests/services/test_runtime_execution_edge_telemetry.py` adds three fail-closed and parity tests (now ten focused tests total): actual source-typed outbox/run link matches the canonical outcome HMAC run digest, non-workflow events/invalid identifiers do not link, and missing flag/key stays silent. **These newly added tests are not yet CI-certified.**
- Existing typed agent↔workflow plan-ID and connector↔outcome↔play run-ID groups remain scoped to their own genuine identities. The new link adds *run→event* only for the existing trigger-proven case.

## 4. Production privacy evidence and blockers

Previously inspected Railway production backend's `list_variables` returned only redacted values and variable **names**; neither `PR605_EXECUTION_EDGE_TELEMETRY_ENABLED` nor `PR605_EXECUTION_EDGE_HMAC_KEY` was listed. No production telemetry collection was enabled. Previous read-only Railway `list_traces` queries for the inspected windows returned **zero traces**. This is not proof that no execution occurred; there is no production trace evidence qualifying replacement/retirement yet.

**Approval required before any collection:** security/privacy/operations reviews of HMAC key provisioning and rotation, data classification, sampling, retention, log/sink access restrictions, multi-tenant access, cross-service correlation scope, performance overhead, incident disable/rollback, and test data/consent. This PR did not update Railway/Vercel variables or run provider probes.

## 5. Evidence-based retirement verdict

| Candidate | Verified replacement coverage | Decision |
|---|---|---|
| Classical ReAct and fallback tool loop | No authenticated production caller and same-contract parity tracing | BLOCKED |
| Alternative voice and PCM transport | No real STT/model/TTS/browser continuity and replacement acceptance | BLOCKED |
| Agent/play/workflow engines | Partial typed plan and run IDs; dynamic full-chain usage not yet proved | BLOCKED |
| Connector authorization and tools | Partial canonical-run observation; missing approved provider read/write proof | BLOCKED |
| Workflow/run dual store | Outbox run link now source-provable; status-migration consumers and prod DB binding not certified | BLOCKED |
| Outbox/relay | Proven durable event semantics and protected consumers | KEEP, NO RETIREMENT |
| Redis, Temporal, historical frontend | Service/worker usage, capacity and recovery not fully certified | BLOCKED |

**Individual destructive retirements authorized: ZERO.**

## 6. Next engineering release gates

1. Complete current exact-head independent ten-test privacy CI, route/inventory/status checks and full integrated CI; repair only evidence-backed failures and rerun against final commit.
2. Extend typed root→plan→run linkage through authenticated, durable execution contracts (not synthetic ID equality) and prove actual provider-verified outcomes and event side effects using privacy-safe traces in an approved test environment.
3. Obtain explicit production telemetry privacy signoff and controlled rollout before collecting production evidence; certify trace coverage and replay/approval/cancellation/tenant isolation.
4. Verify deployed Railway Supabase **nonsecret project reference** before labeling any database output as production; historical reconciliation requires its own approval.
5. Independently approve each retirement candidate only after live consumer coverage, migration parity, security regressions, rollback and owner signoff.

No merge, deployment, schema mutation, historical backfill or legacy removal authorized by this audit document. PR remains DRAFT.
