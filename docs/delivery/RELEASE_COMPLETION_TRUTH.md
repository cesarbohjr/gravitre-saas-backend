# Master plan implementation and shipping truth — 2026-10-14

Implementation continues on `codex/master-plan-completion-20261014`, based on draft #429 at `7fd10c4a`. This branch is reviewable engineering; no merge, production migration, deployment, or flag activation has been performed here.

## Current implementation increment

- Redis workflow claims move atomically from queued to owned processing. Ownership tokens, leases, heartbeat, bounded recovery and dead-letter transitions prevent lost jobs and fence stale acknowledgements. Concurrent deliveries for the same org/run share a single owner. Subsequent provider writes require a live claim and enabled write idempotency.
- Workflow approval fingerprints seal the full JSON provider payload, including connector, webhook path/headers, CC/BCC, attachments and extension arguments. Dynamic parameter templates remain unsealed and require review after resolution. Existing narrower approvals may require renewed approval.
- Conversation persistence adds server-owned revisions and compare-and-set retries. UI rejects stale revisions, presents uncertainty without a completion claim, and carries the existing lifecycle envelope through desktop/mobile runtime and mission status.
- Provider acceptance without verifier evidence is unverified in the existing business-outcome projection. Its accepted confidence remains visible.
- ReAct and unified LIVE/shadow tool-calling rounds use the existing ModelRouter model_calls writer and attribution context. Synthetic handoffs are not charged as model calls. This does not close all failure/cancellation metering or historical billing reconciliation.
- The deterministic agent-roster response no longer creates estimated AI credits when no provider model ran. Streamed turns still need per-model-call billing reconciliation; the current whole-turn text-length estimate is not actual token usage.

## Streamed billing follow-on (draft)

The assistant stream now captures persisted `model_calls` ids and measured provider tokens for each model round, including tool-calling, and charges each id separately through the existing idempotent usage writer. A same-process model cache hit records zero provider tokens/cost and is excluded from billing. A stream without persisted model-call evidence is logged as unmetered rather than charged from text length. Cancellation and early error paths attempt to settle captured calls before completion, with a final attempt on stream close. This augments the existing billing ledger and intelligence stack; it adds no second cost store.

The usage writer now fails closed if its idempotent upsert errors. It no longer retries the charge with a plain INSERT, which could double-charge after a commit followed by timeout. This requires the already defined billing-idempotency migration `20260531000100` to be applied in each target environment before deployment.
The writer also pages usage totals past PostgREST's default row limit, avoids a minimum credit for a measured zero-token call, and attributes a model call to its database creation month when the provider reply crosses a billing boundary.
The assistant stream mints one `assistant:<uuid>` turn identifier and shares it with its cognitive trace and model-call attribution, including across voice task resumption. This avoids reusing an old conversation trace as the next billing turn. `scripts/report_assistant_billing_gap.py --since <UTC timestamp>` reports aggregate new-stream calls without matching assistant usage by model-call id, with no customer identifiers in output. It is read-only and **must not** be used as an automatic charge or historical backfill. Production currently has no turn-attributed `model_calls` rows; the draft has not been deployed.

**Production baseline, read-only on 2026-10-14:** `20260531000000`, `20260531000100` and `20261013080000` are recorded as applied; the usage and overage uniqueness indexes and org/turn index exist. The last 30 days contain 5,093 `model_calls` (zero with `turn_id` or `run_id`) and 11 assistant usage rows (five estimated-turn sources). These are aggregate counts, not a safe basis to infer which historical calls should be charged. The two `20261014100000/100001` idempotency migrations are not recorded in production. No production write was performed.

**Remaining billing gate:** a process crash or database billing failure after `model_calls` insert can leave an unbilled call. A durable reconciler and a historical credit backfill decision are still required before calling billing complete. The current per-call usage writer also performs sequential plan reads/writes; high-volume load and overage correctness need a real-database concurrency proof. A persistent billing-scope marker on `model_calls` plus an atomic reconciler is the next schema increment. The local Supabase CLI is unavailable for generating and validating a new migration, and no production schema change has been applied. This draft remains unmerged and unactivated.
- Haiku 5.5 joins the existing catalog/selector/registry; its 100,000-token price threshold and cache rates are accounted for. Sonnet 5.5 cache reads use the vendor's October 7 price. No routing defaults or customer credit multipliers change.
- MSP parent links cannot grant child access by themselves. Explicit child membership remains required until client-specific delegation, role enforcement and RLS are delivered.
- A follow-on draft increment fixes the scenario fake database's PostgREST revision comparison, carries model attribution across voice task resumption, uses verifier evidence before lifecycle completion, and requires a runtime-equivalent backend SHA at deployment. Its direct provider model gate reuses existing policy and budget checks, which are not yet fail-closed or atomic.

## Gates and configuration

Existing #429 migrations remain separate from this increment: `20261014100000` then `20261014100001`; `20261014060000` requires link-management review. **`20261014110000` is withdrawn and must not be applied.** No new migration is added here.

Keep `WRITE_INVOKE_IDEMPOTENCY_ENABLED`, `EVENT_TRIGGER_USE_WORKFLOW_QUEUE`, `MSP_PARENT_ORG_ENABLED` and the domain relay off in production until their staging and authenticated acceptance gates pass. Queued writes require the idempotency ledger to be active. `WORKFLOW_QUEUE_LEASE_SECONDS` defaults to 60; leases renew every third of that interval. The existing fail-closed queue setting remains part of the production runbook.

The new claim hash/lease/owner keys coexist with the old processing list. Before rollout, inspect old `gravitre:workflow-runs:processing` entries and reconcile their run/provider evidence; do not blindly replay them. Atomic scripts currently target Gravitre's single Redis deployment, not Redis Cluster.

## Remaining master-plan work

The completion matrix remains open for authenticated Release 1 acceptance, staging migration application, durable verification recovery and production activation; full argument-approval flows for resolved dynamic tasks; complete billing/failure attribution and PSA baselines/ROI; Freshservice/HubSpot live proofs; intelligence latency and complete document-memory lineage/resurfacing; client-scoped MSP delegation and switching; external MCP/API-key/OAuth distribution; model quality evaluations and adaptive routing; and third-party verification and marketplace reviews.

Draft #431 CI has green focused Postgres, Redis and web gates, but its full backend run was red on scenario fake-database behavior and approval fixture expectations. The historical migration `20250220000006` also blocks a clean staging replay through a function return-type change. These are acceptance blockers until the corrected backend suite and clean replay pass; they do not justify activation of any production flags.

The restored increment passed 83 focused lifecycle, approval, voice, model metering and attribution tests and a local Git-history deploy-revision test. Automatic approval review blocked its broader scenario run after detecting attempted external provider storage traffic; the suite has no completed verdict in this environment. CI must prove provider calls are intercepted before replaying it. The draft branch has not been merged or deployed.

These remain implementation or external acceptance work. Passing local tests does not close those rows or authorize a production flag flip. Source privacy and Memory Option B retain the existing owner/consent requirements.

## Evidence

See `CODEX_IMPLEMENTATION_2026-10-14.md` for executed checks and limitations, and `MASTER_PLAN_COMPLETION_MATRIX.md` for the full scope.
## Assistant billing transaction (draft #431, 2026-10-15)

The new `20261015032117_assistant_usage_atomic.sql` is **unapplied**. With
`ASSISTANT_BILLING_ATOMIC_ENABLED=true` and that exact migration reviewed and
applied, a namespaced assistant model call can record its usage and overage in
one transaction, serialized with other calls using this RPC for the same org,
period and environment. The flag defaults off. The real-Postgres test in CI
checks concurrent allowance use, replay, tenant boundary, grants and rollback
on overage failure; its result must be checked before a rollout. The legacy
writer and other usage sources do not share the advisory lock, so mixed-source
concurrency and historical billing still require separate reconciliation.
The read-only gap report does not charge customers.
