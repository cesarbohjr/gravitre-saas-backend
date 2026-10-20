# Codex implementation increment — 2026-10-14

Branch: `codex/master-plan-completion-20261014`, based on draft #429 at `7fd10c4a5c7315b9f5e5ec8cefab7bb80ca78c92`. No production writes, migration applications, deployments or flag activations were performed.

## Features augmented and contracts reused

| Change | Existing feature augmented | Shared contract / evidence |
|---|---|---|
| Atomic queue claim, ack, recovery, per-run ownership, heartbeat and fencing | Existing workflow/event/schedule queue and worker | Existing workflow run identifiers; unique Redis delivery claim; provider writes still pass tool_service and ReAct governance. Queued writes require enabled idempotency. |
| Complete write fingerprints | Existing workflow approval scope, canvas and ReAct gates | Exact JSON arguments (excluding dispatcher metadata), resolved connector; nested static params accepted; dynamic sources require resolved review. Arrays, nulls, whitespace and types retained. |
| Ordered conversation snapshots | Existing task_state persistence and speculative adoption | Server-owned task_revision plus compare-and-set retry; UI stale-snapshot guard. Fake Supabase now actually evaluates JSON-path equality/null predicates instead of ignoring them. |
| Lifecycle consumers | Existing AI workspace, execution panel, desktop/mobile runtime, mission spine | Existing lifecycle_envelope; uncertainty and verification stay distinct from provider success. |
| Honest verification | Existing business-outcome projection and reporting | Reuses outcome_verification.evidence_is_verified; accepted writes no longer set verified=true. The verified test fixture now includes an actual verifier method, as the shared contract requires. |
| Tool metering | Existing model_calls writer, catalog cost estimator and turn/run context | Every successful ReAct and unified LIVE/shadow tool round writes through ModelRouter. Synthetic handoffs are not model calls. Anthropic cache read/write token counts survive normalization. |
| Pricing/catalog | Existing backend catalog, picker and model registry | Haiku 5.5 standard/long-context/cache rates and Sonnet 5.5 cache-read correction. No route defaults or customer credit multipliers changed. Source: https://www.anthropic.com/claude-haiku-5-5 (verified October 14; announcement October 7). |
| ROI evidence coverage | Existing agent ROI service | Bounded pages below REST row caps; incomplete cost/job/outcome evidence suppresses unsupported metrics and ROI multiples. Estimates remain estimates. |
| MSP isolation | Existing parent relationship scaffold and org context | Parent membership alone cannot grant child access. Explicit child membership remains authoritative. Full client-specific delegation is still outstanding. |
| Freshservice UI build fix | Existing connector trigger setup panel | Uses the existing TYPE.body token, replacing nonexistent TYPE.bodySm. |

## Executed checks

- Full web Vitest suite: **1,735 passed / 270 files**.
- Web TypeScript: **PASS**; production `next build`: **PASS**.
- Changed web components/helpers ESLint: **0 errors**; existing AI workspace warnings remain.
- Consolidated backend safety/routing/metering/lifecycle/reporting battery: **170 passed**.
- Shared fake-database consumers: **196 passed** after installing the repository's Pipecat constraint. An earlier missing-Pipecat environment failure was resolved without modifying the test assertion.
- Real Redis queue/worker/event tests: **14 passed**, including a terminated child process, recovery, per-run duplicate ownership, stale ack/requeue, renewal, expired write fencing and poison bounds.
- Additional ROI report page/coverage tests: executed separately; recorded in the final delivery summary.
- `git diff --check`: **PASS**.

The focused commands run from backend with pytest; Redis integration uses a private local server on port 16379/database 15. No real vendor provider is used by these acceptance tests.

## Limits and deployment prerequisites

This is not the entire master plan or production acceptance. No full 10k-test backend run, authenticated customer UI proof or live Freshservice/HubSpot delivery was performed here. Original #429's 9 PostgreSQL tests passed in GitHub before this increment; they were not rerun locally because the host cannot switch from root to a PostgreSQL server user. No new SQL is introduced by this increment.

Pending #429 migration sequence: review/apply `20261014100000` then `20261014100001` in staging first. `20261014060000` still requires MSP link-management review. **`20261014110000` was withdrawn.** Keep idempotency/event-queue/MSP/relay production rollout gates unchanged until acceptance.

The queue uses a single Redis deployment. Redis Cluster requires hash-slot-compatible keys before activation. Inspect/reconcile the old processing list before deployment; never automatically replay unknown provider effects. A lease fence cannot undo an external request already in flight; the idempotency ledger's uncertain/reconciliation state is the protection against replaying that request.

Full JSON binding is intentionally conservative: narrower old approval fingerprints or dynamically resolved arguments may require fresh approval. Do not silently accept the old fingerprint format. A durable resolved-argument approval UI remains work in the master plan.

Metering now captures successful tool-calling rounds but is not complete billing reconciliation. Missing provider usage, interrupted calls, provider-specific one-hour cache prices, historical usage and attribution backfill need explicit treatment before claiming complete cost coverage. ROI pagination is bounded at 10,000 rows per evidence source; aggregation for larger populations remains future engineering, and bounded results are labeled incomplete.

The source-memory and ML purpose/consent decisions retain Gravitre's existing owner requirements. The completion matrix lists the remaining client delegation, external MCP/OAuth/API keys, intelligence/revocation, evaluations, PSA baselines, live acceptance and third-party work.
