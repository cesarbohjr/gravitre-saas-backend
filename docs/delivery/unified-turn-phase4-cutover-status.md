# Unified turn Phase 4 — cutover status

Updated: 2026-07-22

## Prerequisites

| Gate | Status |
|------|--------|
| Phase 2 batteries | **PASS** — [phase2 status](unified-turn-phase2-live-status.md) |
| Phase 3 streamed TTFT | **PASS (measured)** — [phase3 status](unified-turn-phase3-latency-status.md); **200ms target MISS** (p50 1258ms) |

## Cutover design

| Flag | Default | Meaning |
|------|---------|---------|
| `UNIFIED_TURN_LIVE_ENABLED` | `false` | When `true`, unified-turn text/write-approval outcomes serve the user |
| `UNIFIED_TURN_SHADOW_ENABLED` | (ops) | Shadow-only; skipped when live is on (no duplicate call) |

- Classical pipeline remains in code as the **rollback** path (flag off, or live returns `None` on error/read-tool fallthrough).
- Write tool proposals stage `awaiting_confirm` via the same approval UX — **no execute bypass**.
- Read tool proposals fall through to classical governed execution.
- Audits: `unified_turn.live.completed` when user-visible; `unified_turn.shadow.completed` otherwise.

## Code

- [`backend/app/config.py`](../../backend/app/config.py) — `unified_turn_live_enabled`
- [`backend/app/services/unified_turn_reasoning_service.py`](../../backend/app/services/unified_turn_reasoning_service.py) — `apply_unified_turn_live`
- [`backend/app/operators/agent_intelligence.py`](../../backend/app/operators/agent_intelligence.py) — live branch before classical conversational gate

## Live enable / verify

| Step | Status | Evidence |
|------|--------|----------|
| Code on `main` | **NOT RUN** | Pending push |
| Prod tip includes Phase 4 | **NOT RUN** | |
| `UNIFIED_TURN_LIVE_ENABLED=true` | **NOT RUN** | Set only after tip advances |
| `unified_turn.live.completed` audits | **NOT RUN** | |
| Rollback check (flag off) | **NOT RUN** | |

## Monitoring window (after enable)

Watch for: raw catalog keys in copy, ignored clarifying questions, write without approval, persona/register drift, TTFT regressions vs Phase 3 baselines.
