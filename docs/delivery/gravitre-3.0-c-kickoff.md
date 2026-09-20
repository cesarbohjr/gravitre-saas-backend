# Gravitre 3.0-C — Voice realtime eval (2026-09-20)

**Status:** **GATE CLOSED (2026-09-20)** — Metric A not worse vs 3.0-A (P95 improved); barge-in WRITE live trace proven. Metric B SLO **NOT MET** (honest). Lanes B/C **NOT_RUN**. Production remains cascade A only.

## Gate closeout

| Gate item | Result | Evidence |
|-----------|--------|----------|
| Metric A not worse vs 3.0-A | **PASS (P95)** | P95 **521 ms ≤ 1215 ms** frozen baseline; P50 **425 vs 377 ms** (+48 ms, in-family) |
| Metric A SLO P50&lt;500 / P95&lt;800 | **PASS** @ `f50ea3f1` re-probe | `voice-slo-two-metric-live.json` @ `2026-09-20T05:50:35Z` |
| Metric B SLO P50&lt;5s / P95&lt;8s | **NOT MET** | P50 **22729 ms** / P95 **41933 ms** — plan-hold operator path |
| Barge-in WRITE live trace | **LIVE_USER_PROVEN** | `voice.barge_in.write_gate` @ `2026-09-20T05:51:27.253Z` conv `934dbecd-…` |
| Lane B/C eval scores | **NOT_RUN** | Eval-only; prod stays A |

## Lane A re-baseline @ SHA `f50ea3f1` (2026-09-20T05:50:35Z)

Probe: `scripts/verify-voice-slo-two-metric-live.py` → `docs/delivery/voice-slo-two-metric-live.json`  
Aggregator: `scripts/aggregate-3.0-c-voice-baseline.py` → `docs/delivery/3.0-c-voice-baseline-latest.json`  
Org: `f07e57c0-1501-4000-8000-c04e57a00001` (isolated)

| Metric | p50 | p95 | Target | SLO |
|--------|-----|-----|--------|-----|
| **A** — first honest audio | **425 ms** | **521 ms** | 500 / 800 | **PASS** |
| **B** — operator completion | **22729 ms** | **41933 ms** | 5000 / 8000 | **FAIL** |

Metric A samples ms: `[521, 360, 425, 365, 472]`.  
Metric B samples ms: `[26500, 41933, 22286, 22729, 18467]`.

Prior probe (`05:35:04Z`) had two tail outliers (10029 / 8865 ms); re-probe confirms intermittent tails, not steady-state regression.

## Compare vs 3.0-A frozen probe (`3.0-a-voice-probe-frozen.json` @ SHA `401554cc`)

| Metric | 3.0-A | 3.0-C @ `f50ea3f1` | Δ | Not worse? |
|--------|-------|-------------------|---|------------|
| A p50 | 377 ms | **425 ms** | +48 ms | Marginal (in-family) |
| A p95 | 1215 ms | **521 ms** | **−694 ms** | **Yes** |
| B p50 | 24815 ms | 22729 ms | −2086 ms | — |
| B p95 | 49257 ms | 41933 ms | −7324 ms | — |

## Source fixes (post-`f50ea3f1`, deploy pending)

| Fix | Path | Targets |
|-----|------|---------|
| Defer voice entitlement check after `voice.session.accepted` | `backend/app/routers/voice.py` | Pre-stream stall class |
| Async ElevenLabs TTS (`asyncio.to_thread`) | `backend/app/services/voice_session_service.py` | Event-loop block / TTS gap |
| PERCEIVE TTS warm at worker startup | `voice_session_service.warm_perceive_tts_cache` + `main.py` lifespan | Cold PERCEIVE outliers |
| Plan-hold skip redundant OBSERVE + compose | `backend/app/operators/agent_intelligence.py` | Metric B trim (partial) |
| Barge-in WRITE live probe | `scripts/verify-voice-barge-in-write-live.py` | Gate evidence |

## Barge-in WRITE evidence

Probe: `scripts/verify-voice-barge-in-write-live.py` → `docs/delivery/voice-barge-in-write-live.json`

**PASS — `voice.barge_in.write_gate` @ `2026-09-20T05:51:27.253306Z`** (audit id `8f16c1b2-7918-4d5d-b990-c5765c92b170`, conv `934dbecd-75bb-4d66-9b52-f77d91e31925`, `uncommitted_write: true`). HTTP cancel @ 200. No mutating `tool.invoke.completed` on probe conv.

## Already shipped (3.0-C source)

| Item | Status |
|------|--------|
| Eval lanes A/B/C table | `voice_realtime_eval.lane_comparison()` |
| Barge-in WRITE safety | UNIT_TEST + **LIVE_USER_PROVEN** (write_gate arm) |
| TTS context cancel on barge-in | `voice.tts.context_cancelled` |
| ASR catalog lexicon (READ ActionSpec names) | Shipped |
| WebRTC eval card | Eval-only; `production_allows_webrtc_media() == false` |
| Pipecat Metric B on composed final | `voice.slo.metric_b` |

See also [gravitre-3.0-c-eval-lanes.md](./gravitre-3.0-c-eval-lanes.md).

## Remaining (post-gate, honest)

1. **Metric B** — plan-hold operator completion still 18–42 s; needs kernel short-circuit or faster plan path (not a 3.0-C gate item per platform table).
2. **Deploy** source fixes above for tail hardening.
3. **Lane B shadow eval** — when product authorizes; never swap production transport.

**NOT RUN:** native realtime (lane B) production audio, WebRTC media in prod, browser-mic barge-in human verify.

## Live re-probe @ SHA `2c0a85b5` (2026-09-20T06:22:45Z)

Does not replace the 05:50Z `f50ea3f1` table.

| Metric | p50 | p95 | Target | SLO |
|--------|-----|-----|--------|-----|
| **A** | **234 ms** | **1121 ms** | 500 / 800 | **FAIL** (P95; samples 273, **1121**, 234, 163, 147) |
| **B** | **27039 ms** | **58654 ms** | 5000 / 8000 | **FAIL** |

Not worse vs 3.0-A A P95 1215: **yes**. Barge-in: **PASS — `voice.barge_in.write_gate` @ `2026-09-20T06:20:42.448557Z`** audit `a3091179-…` conv `ae1a538f-…`.

Seat lookup no longer blocks first SSE; warmed PERCEIVE can flush during seat check. One remaining ~1.1 s accepted+audio stall on a cold worker.
