# ECO-002 — routing latency baseline and dependency review

Status: **IMPLEMENTED INSTRUMENTATION; NOT CERTIFIED; NO P50/P95 SAMPLES YET**.
Source: 43-finding master register, ECO-002 (P0, QA30). ECO-001 remains open and release-blocking.

## Source dependency trace

The active `IntelligenceRouter.route` path has the following observed order. This is a source dependency review, not a sampled live production trace.

1. Overview policy loading; dialogue settings loading; then request sentiment derived from settings.
2. Understanding(request, history, org), then classification(understanding), then query-cluster augmentation(classification).
3. Clarification(classification, understanding). Clarification may return early; later stages do not run on this branch.
4. Context assembly(classification). Risk evaluation uses classification and is conditional on action intent. Dialogue policy then consumes classification, clarification, sentiment and risk.
5. Model selection(classification), then optional enrichment based on classification and context. `_run_enrichments` already concurrently gathers eligible, bounded optional sources with a 1.5-second per-source timeout.
6. Knowledge response or governed-execution path based on `requires_action`; post-response refinement and proactive guidance are downstream.

**No parallelization is authorized based on the source graph alone.** In particular, understanding → classification, classification → clarification/context, and selection/enrichment → response dispatch are data dependencies. Overview-policy and dialogue-settings loads may be parallelization candidates, but only after real profiles and caller side-effect/failure parity tests. The existing optional enrichment `asyncio.gather` must not be replaced without measurement.

## Instrumentation

`backend/app/services/routing_stage_metrics.py` adds opt-in `ECO002_ROUTING_LATENCY_TRACE=true` timings. Each observation records only a fixed stage label, fixed outcome (`ok`/`error`) and elapsed seconds. Prometheus histogram: `gravitre_intelligence_route_stage_duration_seconds` with `stage` and `outcome` labels. Structured log: `eco002_route_stage stage=... outcome=... duration_ms=...`. No tenant IDs, payloads, prompts, context, tokens, or conversation content become metric labels. Disabled mode simply awaits and returns the identical task result; exceptions are re-raised intact. Existing await order, approvals and dispatch are unchanged. Clarifying requests legitimately emit only early-path stage samples.

Example stage-level p50 (Prometheus):

```promql
histogram_quantile(0.50, sum by (le, stage) (rate(gravitre_intelligence_route_stage_duration_seconds_bucket{outcome="ok"}[15m])))
```

Example p95:

```promql
histogram_quantile(0.95, sum by (le, stage) (rate(gravitre_intelligence_route_stage_duration_seconds_bucket{outcome="ok"}[15m])))
```

The 15-minute range is illustrative only; sampling windows, cold/warm starts, branch mix, request/context size and confidence intervals must be specified in an actual controlled run. **No p50/p95 values or speedup percentages are claimed.** Actual baseline requires representative approved test traffic and an independently observed telemetry store. Voice time-to-first-audio and prompt/context payload size remain separate acceptance requirements and are not inferred from routing histograms.

## Gates that remain open

- Exact-head CI must pass for instrumentation and targeted parity tests.
- Enable timing only in an approved isolated environment after ECO-001 QA-scheduler isolation is separately certified; preserve production flags unchanged.
- Collect reproducible per-stage p50/p95, request-shape/context-size strata, critical-path and sample-count evidence.
- Measure observed effects before any concurrency change; use positive/negative parity tests including clarification early return, error propagation, cancellation, authority and side-effect boundaries.
- Independently verify downstream consumer behavior, release/rollback and owner approval; keep register `live_status=NOT_RUN`, `fix_verified=false`, `release_blocking=true` until proven.
