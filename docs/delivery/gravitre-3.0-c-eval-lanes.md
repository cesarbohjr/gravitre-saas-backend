# Gravitre 3.0-C — eval lanes A / B / C (2026-09-19)

**Status:** Architecture table in source (`voice_realtime_eval.lane_comparison`). **No production swap.** Measured scores: **NOT_RUN**.

Production serving lane is always **A_CASCADE** even if `VOICE_REALTIME_EVAL_LANE=B`.

| Lane | Path | Prod audio? | Tools |
|------|------|-------------|-------|
| A CURRENT CASCADE | Deepgram STT → `execute_task_streaming` → ElevenLabs | **Yes** | Canonical kernel only |
| B NATIVE REALTIME | Speech/audio model → same kernel for tools → audio | **No** | Provider-native tools **forbidden** |
| C HYBRID | Realtime conversation frontend + Gravitre work backend | **No** | Canonical kernel only |

Eval hypothesis if B fails governance/trace: **C**. That is not a measured winner.

Benchmark dimensions (A and B latency separate; no blended SLO): semantic accuracy, interruptions, tool correctness, Metric A, Metric B, cost, naturalness, traceability, governance, context parity, WebRTC startup/RTT/jitter/loss/reconnect/region.

## Gate still open

- Metric A P50&lt;500 / P95&lt;800 and Metric B P50&lt;5s / P95&lt;8s: **FAIL** on latest HTTP Talk samples (see `docs/delivery/voice-slo-two-metric-live.json`).
- Barge-in WRITE: UNIT_TEST on `c549ec47`; **not LIVE_USER_PROVEN**.
