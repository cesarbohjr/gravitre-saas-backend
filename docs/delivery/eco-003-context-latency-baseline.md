# ECO-003 — Tenant-safe context retrieval latency investigation

**Status: instrumentation committed; not certified; no live p50/p95 samples.** Finding ECO-003 (P0, QA30) remains independently release-blocking. Consolidated ECO-002 (including former ECO-001) remains separate and unreleased.

## Source and dependency trace

`IntelligenceRouter.route` calls `ContextAssembler.assemble` after understanding, classification and clarification. The assembler awaits unified retrieval, then company-intelligence context, then optionally external research. `UnifiedRetrievalService.retrieve` awaits org-context snapshot, agent-memory retrieval, then RAG, with conditional graph/hybrid/internet stages gated by previous results. Organizational snapshot drives connected CRM retrieval bias; internal RAG confidence controls later graph/hybrid/external cascade. These dependencies prohibit indiscriminate parallelization.

Source evidence:
- `backend/app/services/context_assembler.py`
- `backend/app/services/unified_retrieval_service.py`
- `backend/app/services/intelligence_router.py`

## First implementation: opt-in metrics, no behavioral changes

`ECO003_CONTEXT_LATENCY_TRACE=true` enables `gravitre_context_stage_duration_seconds` Prometheus histograms and structured duration logs with **only** static stage names and `ok/error` outcome labels. Timing boundaries:
- `unified_retrieval` (outer context-assembly critical-path span)
- `org_context` (per-tenant/org snapshot; blocking I/O remains offloaded)
- `agent_memory` (per-org/agent/user scoped read)
- `rag_retrieval` (org- and environment-scoped hybrid rows)
- `company_intelligence` (per-org contextual read)
- `external_research` (conditional only; do not force network retrieval for benchmarks)

These spans can be nested: **do not sum them** to estimate total request latency, since `unified_retrieval` includes inner steps. The metric never labels prompts, tenant IDs, document IDs, query text or user identifiers. When disabled, the original await and result/exception semantics are unchanged. There is deliberately no new cache, concurrency, provider call, approval bypass or tenant-scope policy.

PromQL examples (only meaningful after representative samples):

```promql
histogram_quantile(0.50, sum by (le, stage) (rate(gravitre_context_stage_duration_seconds_bucket{outcome="ok"}[15m])))
histogram_quantile(0.95, sum by (le, stage) (rate(gravitre_context_stage_duration_seconds_bucket{outcome="ok"}[15m])))
sum by (stage) (increase(gravitre_context_stage_duration_seconds_count{outcome="ok"}[15m]))
```

The 15-minute window is illustrative; separately stratify cold/warm reads, classification, RAG top-k, document count, context payload byte-size, org/agent permission scope and external-search branch **without putting sensitive values in Prometheus labels**. Keep sample counts and variance; no latency threshold or speedup is asserted without observed distributions.

## Dependency/tenant-isolation requirements before optimization

1. Collect isolated QA timings after exact-head CI, deployment and read-only SHA/database/401-or-403 ingress certification; use approved, nonmutating, tenant-scoped requests. The QA no-background-worker safeguard must be effective. Never reuse production tokens or prompts.
2. Compare retrieval results including authorized organization, user, agent, environment, knowledge assignment and strict-assignment policies before attempting concurrency. Confirm timeout and cancellation/fallback behavior stays unchanged.
3. Consider overlap of company-intelligence with unified retrieval **only after** read dependencies and failure semantics are demonstrated independent. Org-context and agent memory are not automatically independent of concurrent DB/client utilization; RAG CRM bias explicitly needs org-context. Graph, hybrid memory and research are conditional cascades.
4. Do not introduce cache storage or cache-key changes before cross-tenant, revocation, permission-change, staleness and negative tests exist. Test denial and missing-access results directly; never cache unscoped authorization-sensitive data.
5. Require measured end-to-end effect, independent consumer observation, exact-SHA full CI, release/rollback and owner approval before setting any register closure boolean.

## Evidence classification

Unit/static tests: `backend/tests/master_qa/test_eco003_context_stage_metrics.py` (source checks and direct wrapper cases). These tests **do not** prove live multi-tenant security, true p50/p95 or acceptable downstream behavior. No parallelization, caching, latency improvement, or provider production effect is claimed.
