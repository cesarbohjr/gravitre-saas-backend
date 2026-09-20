# Gravitre 3.0-C — eval lanes A / B / C (2026-09-19)

**Status:** **3.0-C GATE CLOSED (2026-09-20)** — Lane A measured; barge-in WRITE live-proven. Lanes B/C: **NOT_RUN**. No production swap.

Production serving lane is always **A_CASCADE** even if `VOICE_REALTIME_EVAL_LANE=B`.

| Lane | Path | Prod audio? | Tools |
|------|------|-------------|-------|
| A CURRENT CASCADE | Deepgram STT → `execute_task_streaming` → ElevenLabs | **Yes** | Canonical kernel only |
| B NATIVE REALTIME | Speech/audio model → same kernel for tools → audio | **No** | Provider-native tools **forbidden** |
| C HYBRID | Realtime conversation frontend + Gravitre work backend | **No** | Canonical kernel only |

Eval hypothesis if B fails governance/trace: **C**. That is not a measured winner.

Benchmark dimensions (A and B latency separate; no blended SLO): semantic accuracy, interruptions, tool correctness, Metric A, Metric B, cost, naturalness, traceability, governance, context parity, WebRTC startup/RTT/jitter/loss/reconnect/region.

## Gate closed (2026-09-20)

- Metric A not worse vs 3.0-A: **PASS (P95)** — see [gravitre-3.0-c-kickoff.md](./gravitre-3.0-c-kickoff.md).
- Metric A SLO @ re-probe: **PASS** (p50 **425** / p95 **521**).
- Metric B SLO: **NOT MET** (p50 **22729** / p95 **41933**) — documented, not blended with A.
- Barge-in WRITE: **LIVE_USER_PROVEN** — `voice.barge_in.write_gate` @ `2026-09-20T05:51:27.253Z`.
