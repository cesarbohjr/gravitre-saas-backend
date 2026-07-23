# Unified turn Phase 3 — first-token latency / streaming

Updated: 2026-07-22

## Gate from Phase 2

**PASS (core)** — see [unified-turn-phase2-live-status.md](unified-turn-phase2-live-status.md).

## Live measurement (tip `444371f9…`)

Artifact: [`unified-turn-phase3-latency-live.json`](unified-turn-phase3-latency-live.json)

| Metric | Value |
|--------|------:|
| Streamed samples | **5/5** (`streamed=true` in shadow audits) |
| TTFT min | 876ms |
| TTFT p50 | 2062ms |
| TTFT max | 4240ms |
| Target &lt;200ms | **NOT MET** |

Example audit: `unified_turn.shadow.completed` @ `2026-07-22T17:33:43.315276Z` conv `4ff90783-…` — `streamed=true`, `first_token_proxy_ms=876`.

Classical plan-bar / SSE: probes saw intelligence/plan events (`saw_plan_or_intel=true`); user-visible path unchanged for measurement (cutover flag may already be on tip — see Phase 4).

## Notes

- Streaming shadow is live on tip that includes `2f764ef6`.
- 200ms target is not met on `gpt-4o-mini` full tool-aware completion; report honest numbers rather than soft-pass.
- **Social TTFT decision (2026-07-23):** Option A rejected — accept ~500–750ms social; do not chase social &lt;200ms via classify-then-route. **Active latency lane:** task-shaped **C/D** — see [unified-turn-task-latency-cd-status.md](unified-turn-task-latency-cd-status.md) and [unified-turn-ttft-investigation.md](unified-turn-ttft-investigation.md).
- **Phase 3 script:** `verify-unified-turn-phase3-latency-live.py` reads `unified_turn.live.completed` when LIVE is on (not shadow-only).
