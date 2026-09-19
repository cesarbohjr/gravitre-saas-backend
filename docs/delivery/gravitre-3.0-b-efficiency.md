# Gravitre 3.0-B — Context/tool efficiency (2026-09-19)

**Status:** **PARTIAL GATE** — live JIT rows PASS (n≥10); stage regression **FAIL** on `TOOL_DISCOVERY` p95 (+7 ms vs 3.0-A frozen snapshot).

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

## Live verification (2026-09-19)

| Check | Result | Evidence |
|-------|--------|----------|
| Deploy | **PASS** | `/health` SHA `622c7afcb11cee4ef26cc3d62616f737ef6d6359` |
| Isolated-org turns | **PASS** | 32/32 HTTP 200 — conv `1632a0dd-…`, `3940c536-…`, `6221f9ff-…` (`docs/delivery/3.0-b-jit-efficiency-live-probe.json`) |
| `runtime.jit.tool_namespace` n≥10 | **PASS** | n=**26** p50 visibleTools **20** / totalTools **86** (23% of catalog) |
| `runtime.jit.context_profile` n≥10 | **PASS** | n=**10** shadow+active ranking; sample audit `ffa68118-…` @ `2026-09-19T09:04:01Z` |
| Stage regression vs 3.0-A | **FAIL** | `TOOL_DISCOVERY` p95 **125→132 ms** (+7 ms); `CONTEXT_BUILD` p95 **8543→7623 ms** (improved) |
| Aggregator | **PASS** | `docs/delivery/3.0-b-efficiency-baseline-latest.json` @ SHA `622c7afc` |

**Gate:** `any_regression=false` **not met** — requires named trade for +7 ms `TOOL_DISCOVERY` p95 or post-3.0-B baseline refresh before claiming Done.
