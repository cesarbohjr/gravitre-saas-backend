# Unified turn Phase 4 — cutover status

Updated: 2026-07-22

## Prerequisites

| Gate | Status |
|------|--------|
| Phase 2 core batteries | **PASS** — workflow [29909107895](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/29909107895) |
| Phase 3 streamed TTFT | **PASS (measured)** — [phase3](unified-turn-phase3-latency-status.md); **200ms target MISS** (p50 ~1258ms) |

## Cutover design

| Flag | Meaning |
|------|---------|
| `UNIFIED_TURN_LIVE_ENABLED` | When `true`, unified-turn text + write-approval outcomes serve the user |
| `UNIFIED_TURN_SHADOW_ENABLED` | Shadow audits; skipped when live already ran the call |

Classical pipeline remains rollback (`LIVE=false` or live returns `None`). Writes stage `awaiting_confirm`.

## Progress

| Step | Status | Evidence |
|------|--------|----------|
| Cutover code + health flags on prod | **PASS** | `/health` `git_sha=83c23f272f9c7f24139169a6befa25474f55d9d2` @ `2026-07-22T22:57:29Z` |
| `UNIFIED_TURN_LIVE_ENABLED` in process | **PASS** | `/health` `unified_turn_live_enabled=true` (same timestamp) |
| `unified_turn.live.completed` | **PASS** | `live_served=true` @ `2026-07-22T22:57:35.668737Z` (Hey, conv `6e39a470…`) and `2026-07-22T22:57:42.327375Z` (Thank you, conv `b618f965…`) — [probe JSON](unified-turn-phase4-live-probe.json) |
| Monitoring window | **NOT RUN** | Start copy-leak / write-approval / TTFT watch vs Phase 3 |

## Shipped (2026-07-22)

LIVE cutover verified on tip `83c23f27…` with health flags true and two `unified_turn.live.completed` audits (`live_served=true`). First-token proxies on probe: 642ms / 338ms (not a 200ms claim).

Rollback: `UNIFIED_TURN_LIVE_ENABLED=false` + redeploy (or set `UNIFIED_TURN_RESTART_NONCE` to force restart).

## Next

1. Open monitoring window (copy leaks, write approvals still stage `awaiting_confirm`, TTFT vs Phase 3).
2. Keep tip promoting via green CI (Billing E2E off main push) + Railway / `railway up` path when GitHub auto-deploy stalls.
3. Do not claim Phase 3 200ms TTFT met — still MISS.
