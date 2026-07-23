# Golden signals ops audit (2026-07-23)

**Question:** Is there a single live dashboard for chat p95, connector failure rate, write-approval abandonment, TTFT trend?

## Finding: **PARTIAL / scattered**

| Signal | Where it exists today | Live dashboard? |
|--------|------------------------|-----------------|
| Chat / unified-turn TTFT | `audit_events` (`unified_turn.*`), battery JSON under `docs/delivery/unified-turn-*-live.json` | No unified view |
| Connector tool failures | `audit_events` (`tool.invoke.*`), Module A outcome record | Admin audit UI; no golden-signal rollup |
| Write approval abandonment | Approvals tables + audit | No dedicated trend |
| Traffic / errors | Railway logs, Vercel analytics | Product analytics only |

## Recommendation (cheap next step)

One read-only internal page or Metabase/ClickHouse view over:

- `audit_events` filtered `action LIKE 'unified_turn.%'` → p50/p95 `latency_breakdown.model_ttft_ms`
- `tool.invoke.failed` rate by vendor (24h)
- Pending approval created vs approved (24h)

**Status:** **NOT RUN** — no dashboard shipped in this pass; data sources proven in prior batteries.
