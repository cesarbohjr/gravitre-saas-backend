# Gravitre 3.0-A baseline + gate closeout (2026-09-19)

**Status:** **3.0-A GATE CLOSED (measurement)** — live traffic + trace artifacts + SHA on isolated org. Metric A/B **measured**; SLO targets **not met** on current tip (honest baseline, not a PASS claim).

## Gate checklist

| Item | Result | Evidence |
|------|--------|----------|
| F1 island live traffic | **PASS** | `docs/delivery/f1-live-verify-2026-09-19.json` @ `/health` `67944d59`; `tool.invoke.completed` @ `2026-09-19T07:20:00.547Z` |
| Text critical-path traces | **PASS** | `runtime.turn_latency.critical_path` @ `2026-09-19T07:19:23.916Z` conv `a2b5c0a8-…` |
| Voice Metric A/B live probe | **PASS (measured)** | `docs/delivery/voice-slo-two-metric-live.json` @ `/health` `653303a3` @ `2026-09-19T07:53:33Z` |
| Voice critical-path (`spoken_mode=true`) | **PASS** | n=15 voice cohort @ SHA `401554cc`; audit `408eb58c-…` @ `2026-09-19T08:16:59.406Z` conv `b51f1608-…` |
| Aggregator | **PASS** | `scripts/aggregate-3.0-a-latency-baseline.py` → `docs/delivery/3.0-a-latency-baseline-latest.json` |
| HMAC / WRITE / barge-in | **UNCHANGED** | No weakening in this slice |
| `compiled_task` | **OPTIONAL_PROJECTION** | Unchanged |

## Voice Metric A/B (isolated org, n=5 HTTP Talk, SHA `401554cc`)

| Metric | p50 | p95 | Target | SLO |
|--------|-----|-----|--------|-----|
| **A** — first honest audio | **377 ms** | **1215 ms** | 500 / 800 | **FAIL** (P95) |
| **B** — operator completion | **24815 ms** | **49257 ms** | 5000 / 8000 | **FAIL** |

Audit-backed (24h): `voice.slo.metric_a` n=10 p50 **2 ms** / p95 **482 ms**; `voice.slo.metric_b` n=10 p50 **23846 ms** / p95 **52587 ms** (includes duplex + HTTP samples; probe client measures wall TTFA/complete separately).

Anchor conversation: `5317f08c-a36b-427e-be04-a3d4ca699265`. A and B stay separate; do not blend.

## Text critical-path (168h isolated org, pre-voice-instrumentation tip)

| Clock | p50 | p95 |
|-------|-----|-----|
| Turn total | 13.4 s | 22.7 s |
| Dominant stage delta | 8.0 s | 9.9 s |

Dominant stage wins (text): `UNIFIED_LIVE_RESOLVED`. Voice cohort (n=15): dominant p50 **5.2 s** / p95 **26.8 s**; wins split `COMPOSER`, `UNIFIED_LIVE_RESOLVED`, `CONTEXT_BUILD`.

## Before / after (honest)

| Clock | Before 3.0-A | After measurement | Notes |
|-------|--------------|-------------------|-------|
| Text critical path | uninstrumented | live audit rows | dominant stage named |
| Voice Metric A | unknown | p50 375 / p95 1166 | P50 under 500; P95 over 800 |
| Voice Metric B | unknown | p50 27s / p95 53s | far above 5s/8s targets |

**No latency improvement claimed.** 3.0-A closes the **measurement gate**, not the SLO gate.

## Next phase

**3.0-B — Context/tool efficiency:** JIT context scoring, eligible-tool namespace (no 700-tool dump), ActionSpec cache. Baseline above is the before snapshot; 3.0-B must not regress stage p50/p95 without a named trade.
