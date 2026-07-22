# Unified turn Phase 4 — cutover status

Updated: 2026-07-22

## Prerequisites

| Gate | Status |
|------|--------|
| Phase 2 core batteries | **PASS** on tip `444371f9…` |
| Phase 3 streamed TTFT | **Measured** — p50 ~2.0s; **200ms target MISS** (documented) |

## Cutover design

| Flag | Meaning |
|------|---------|
| `UNIFIED_TURN_LIVE_ENABLED` | When `true`, unified-turn text + write-approval outcomes serve the user |
| `UNIFIED_TURN_SHADOW_ENABLED` | Shadow audits; skipped when live already ran the call |

Classical pipeline remains rollback (`LIVE=false` or live returns `None`). Writes stage `awaiting_confirm`.

## Progress

| Step | Status | Evidence |
|------|--------|----------|
| Cutover code on prod | **PASS** | tip `444371f9…` |
| Railway vars LIVE=true | **PASS** | Actions log [29949446998](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/29949446998): `UNIFIED_TURN_LIVE_ENABLED='true'` |
| Process reload / tip with health flags | **BLOCKED** | `railway up` failed streaming Metal build logs; `/health` still lacks `unified_turn_*` keys (schema tip not deployed) |
| `unified_turn.live.completed` | **NOT RUN** | Blocked on process restart with LIVE env |
| Monitoring window | **NOT RUN** | |

## Next

1. Redeploy current serving image (no Metal log stream) so LIVE env loads into `444371f9` process.
2. Probe `unified_turn.live.completed` with `live_served=true`.
3. Rollback: `UNIFIED_TURN_LIVE_ENABLED=false` + redeploy.

Workflow: [unified-turn-phase4-cutover.yml](../../.github/workflows/unified-turn-phase4-cutover.yml) (redeploy-first; `railway up` best-effort).
