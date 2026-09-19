# Gravitre 3.0-A baseline (2026-09-19)

**Status:** code + unit tests + live `/health` + isolated-org chat. Voice Metric A/B p50/p95 on this SHA remain **NOT_RUN** (no spoken-turn sample in this window).

## Live pointers (SHA `67944d59`)

- `/health` `git_sha=67944d5984753e73346d440f667188985777b538` @ `2026-09-19T07:18:46.707854Z`
- Isolated org `f07e57c0-1501-4000-8000-c04e57a00001`
- Traffic anchor conversation `f5e968b8-9741-43f8-acc5-15c64836e3fd` — HTTP 200, no schema leaks; honest “analytics not connected this turn” (not a fake report)
- `runtime.turn_latency.critical_path` audit `e17ead51-dd83-438a-9383-f3f432743250` @ `2026-09-19T07:22:17.493466Z` on conversation `edd8adc3-6a7d-44cf-959b-6a73a076c07c`
- Composer `response.composer.completed` `b7e4c3a2-8e34-4d33-a531-6116c3911145` immediately after

## Gate

| Item | Result |
|------|--------|
| Critical-path analyzer | UNIT_TEST + live audit above |
| Stages mapped | NETWORK, RESOLUTION, CONTEXT_BUILD, TOOL_DISCOVERY, PREFLIGHT, PLANNING, MODEL_TTFT, PROVIDER, COMPOSER, VAD, STT, STT_ENDPOINTING, TTS_BUFFER |
| Voice Metric A / B | Standing targets unchanged. Live p50/p95 **NOT_RUN** this SHA |
| HMAC / WRITE | Unchanged; barge-in blocks WRITE commit |
| `compiled_task` | OPTIONAL_PROJECTION |

## Before / after (honest)

| Clock | Before | After `67944d59` | Budget |
|-------|--------|------------------|--------|
| Voice client first_delta (2026-09-09 n=8) | p50 9574ms | not remeasured | Do not treat as Metric A |
| Text critical path | uninstrumented | live `runtime.turn_latency.critical_path` | fail unnamed extra delay |

Do not treat the 2026-09-09 first_delta p50 as Metric A.
