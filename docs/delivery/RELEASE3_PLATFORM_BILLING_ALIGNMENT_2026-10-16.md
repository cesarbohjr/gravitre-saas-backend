# Release-3 platform billing alignment and acceptance contract

Status: OPEN — engineering review, not production authorization (2026-10-16).

## Canonical flows

1. **Attribution:** Every billable model/provider activity must have a durable, tenant-scoped, environment-scoped and source-scoped evidence record. Differentiate local cache hits, embeddings, streamed chat/voice model calls, workflow/tool model calls, research lookups and voice minutes; do not silently charge a fallback when evidence is missing.
2. **Usage:** Use one deterministic idempotency key per logical event, consistent across retries and entry points. Assistant model calls use persisted model-call evidence; other allowance-bearing paths use the same org+metric+environment+period advisory lock and atomic usage/overage ledger RPCs.
3. **Allowance:** Resolve included credits from the applicable billing plan and environment. Keep included allowance immutable for the same org, metric, environment and UTC period while durable recovery is enabled; conflicts demand reconciliation, not a silent recalculation.
4. **Settlement:** A model call and its usage/overage ledger transaction must be atomic inside PostgreSQL. Recovery handles only eligible current-month, non-zero-token, sufficiently aged assistant evidence; closed periods, poison rows and untagged legacy calls require an operator report.
5. **Stripe:** Meter events are *not* in the PostgreSQL transaction. Maintain deterministic identifiers per source event/batch, persistent confirmation state and retries; reconcile provider acceptance and local reported state, including ambiguous timeouts. Never mix staging/test environment records into production Stripe meters. Do not equate an HTTP 200 with durable settlement.
6. **Surface parity:** Chat text, voice streaming, tools, agents, workflows, connectors, RAG/research, marketplace and billing UI must consume the same tenant and plan contract. Show measured spend separately from estimated labor ROI and price forecasts.
7. **Corrections:** Refund, credit, replay, period-close, downgrade, plan and included-allowance adjustments use auditable compensating entries; no historical rewriting or double charging.
8. **Visibility:** Billing administration, reports, user-facing limits, entitlement checks and support tooling must read the same canonical usage/allowance ledger, with organization and environment scoping.

## Observed from PR #431 review

- The shared `apply_usage_with_overage` path switches between legacy insert and atomic RPC by `USAGE_ATOMIC_ENABLED`.
- `record_usage_with_overage_atomic` switches to the allowance-locking contract when recovery is active.
- `record_assistant_model_usage_atomic` switches to model-call settlement when recovery is active.
- The synchronous usage scheduler invokes recovery before Stripe usage reporters and requires both atomic flags.
- The AI-credit Stripe reporter previously selected every environment in a period; a production-environment filter and dedicated regression test were committed on this branch.
- The AI-credit reporter groups pending row IDs and uses a batch-derived Stripe identifier. This needs failure-injection proof for retries after a Stripe success but failed mark, changed batch memberships, and concurrent reporters.
- Other reporters (research lookup and voice minutes) retain independent paths and must be audited against the same source/tenant/environment/retry requirements.
- The historical migration reset is still not green: following CI-local reconciliation of older functions and billing-table ordering, the next observed failure is `20260703170000_chat_execution_notifications.sql` referencing missing `public.notifications`.

## Mandatory release verification matrix

| Area | Evidence to collect |
| --- | --- |
| Chat text and voice | Same token/credit calculation for same model-call evidence; no double charge after replay, client disconnect or recovery |
| Tool/agent/workflow | Every model invocation attributed to source run and org; idempotent workflow and tool retries; workflow-run allowances reconciled |
| Connectors/research/RAG | Distinguish billable AI credits, connector activity, research lookups, embeddings, and external provider charges; no accidental double metering |
| Billing plan and quota | Limits, proration and upgrades/downgrades agree in API, UI and Stripe; allowance changes within a period produce explicit exception |
| Ledger/Stripe | No unmatched model calls, usage ledger gaps, orphan overage entries, duplicate meter events or ambiguous reports |
| Security | Cross-org and cross-environment negative tests on ledgers, RPCs, entitlements and invoices |
| Concurrency | Concurrent generic and assistant writers, retry after uncertain commit, two Stripe reporters, provider timeout and partial failure |
| Period boundaries | UTC period-close, Stripe interval semantics, old-period reconciliation, transition across month boundary |
| ROI/customer UI | Clearly label measured cost versus estimated savings; totals and units consistent with backend ledger |
| Operations | Complete migration gate, staging billing reconciliation, 48h alerts, recoverable backup and operator sign-off |

## Gate

Do not activate `USAGE_ATOMIC_ENABLED`, `ASSISTANT_BILLING_ATOMIC_ENABLED`, or `ASSISTANT_BILLING_RECOVERY_ENABLED` in production until CI, staging reconciliation, Stripe comparison, tenant denials, vendor fixture tests and release approval pass. Historical migration files already applied remain immutable.
