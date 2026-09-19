# Gravitre 3.0-B — Context/tool efficiency (2026-09-19)

**Status:** **SHIPPED (source)** — JIT audits + eligible-tool namespace wiring + ActionSpec cache. Gate compare requires live traffic after deploy.

## Scope

| Item | Change |
|------|--------|
| Eligible-tool namespace | `classification` passed on unified-turn keyword + embed narrow paths; embed path applies `_capability_eligible_prefixes` |
| JIT audits | `runtime.jit.tool_namespace`, `runtime.jit.context_profile` via `jit_efficiency_service.py` |
| ActionSpec cache | Revision-keyed `@lru_cache` on `get_action_spec` hot path |
| Baseline aggregator | `scripts/aggregate-3.0-b-efficiency-baseline.py` → `docs/delivery/3.0-b-efficiency-baseline-latest.json` |

## Gate (3.0-B)

Compare against frozen 3.0-A snapshot (`docs/delivery/3.0-a-latency-baseline-latest.json`):

- **Token/stage p50/p95** for `CONTEXT_BUILD` and `TOOL_DISCOVERY` must **not regress** without a named trade.
- Tool namespace: median `visibleTools` ≪ catalog `totalTools` (no 700-tool dump).
- Context profile: shadow ranking audits include/exclude trace (`excludedSources`, `selectedSourceIds`).

## Before snapshot (3.0-A @ SHA `401554cc`)

See `docs/delivery/gravitre-3.0-a-baseline.md`. Text turn total p50 **13.2 s** / p95 **23.8 s**; dominant stage wins include `CONTEXT_BUILD`, `UNIFIED_LIVE_RESOLVED`.

## Verification

```bash
cd backend && pytest tests/services/test_jit_efficiency_baseline.py tests/connectors/action_catalog/test_action_spec_cache.py -q
python scripts/aggregate-3.0-b-efficiency-baseline.py --hours 24
```

Live gate: merge → Railway redeploy → isolated-org turns → aggregator `any_regression=false` with n≥10 JIT rows.

**NOT RUN (prod):** JIT audit rows on production tip pending deploy.
