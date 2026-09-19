# Gravitre 3.0-A baseline + gate closeout (2026-09-19)

**Status:** **3.0-A GATE CLOSED (measurement)** — live traffic + trace artifacts + SHA on isolated org. Metric A/B **measured**; SLO targets **not met** on current tip (honest baseline, not a PASS claim).

## Gate checklist

| Item | Result | Evidence |
|------|--------|----------|
| F1 island live traffic | **PASS** | `docs/delivery/f1-live-verify-2026-09-19.json` @ `/health` `67944d59`; `tool.invoke.completed` @ `2026-09-19T07:20:00.547Z` |
| Text critical-path traces | **PASS** | `runtime.turn_latency.critical_path` @ `2026-09-19T07:19:23.916Z` conv `a2b5c0a8-…` |
| Voice Metric A/B live probe | **PASS (measured)** | `docs/delivery/voice-slo-two-metric-live.json` @ `/health` `653303a3` @ `2026-09-19T07:53:33Z` |
| Voice critical-path (`spoken_mode=true`) | **PARTIAL → ship on next backend tip** | HTTP Talk + Pipecat now call `record_voice_turn_critical_path`; re-probe after deploy |
| Aggregator | **PASS** | `scripts/aggregate-3.0-a-latency-baseline.py` → `docs/delivery/3.0-a-latency-baseline-latest.json` |
| HMAC / WRITE / barge-in | **UNCHANGED** | No weakening in this slice |
| `compiled_task` | **OPTIONAL_PROJECTION** | Unchanged |

## Voice Metric A/B (isolated org, n=5 HTTP Talk, SHA `653303a3`)

| Metric | p50 | p95 | Target | SLO |
|--------|-----|-----|--------|-----|
| **A** — first honest audio | **375 ms** | **1166 ms** | 500 / 800 | **FAIL** (P95) |
| **B** — operator completion | **26989 ms** | **53054 ms** | 5000 / 8000 | **FAIL** |

Anchor conversation: `5317f08c-a36b-427e-be04-a3d4ca699265`. A and B stay separate; do not blend.

## Text critical-path (168h isolated org, pre-voice-instrumentation tip)

| Clock | p50 | p95 |
|-------|-----|-----|
| Turn total | 13.4 s | 22.7 s |
| Dominant stage delta | 8.0 s | 9.9 s |

Dominant stage wins: `UNIFIED_LIVE_RESOLVED` (11/13). Voice cohort was n=0 before `record_voice_turn_critical_path` ship.

## Before / after (honest)

| Clock | Before 3.0-A | After measurement | Notes |
|-------|--------------|-------------------|-------|
| Text critical path | uninstrumented | live audit rows | dominant stage named |
| Voice Metric A | unknown | p50 375 / p95 1166 | P50 under 500; P95 over 800 |
| Voice Metric B | unknown | p50 27s / p95 53s | far above 5s/8s targets |

**No latency improvement claimed.** 3.0-A closes the **measurement gate**, not the SLO gate.

## Next phase

**3.0-B — Context/tool efficiency:** JIT context scoring, eligible-tool namespace (no 700-tool dump), ActionSpec cache. Baseline above is the before snapshot; 3.0-B must not regress stage p50/p95 without a named trade.
