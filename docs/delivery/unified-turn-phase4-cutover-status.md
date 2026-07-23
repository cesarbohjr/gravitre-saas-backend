# Unified turn Phase 4 — cutover status

Updated: 2026-07-23

## Prerequisites

| Gate | Status |
|------|--------|
| Phase 2 core batteries | **PASS** — workflow [29909107895](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/29909107895) |
| Phase 3 streamed TTFT | **PASS (measured)** — [phase3](unified-turn-phase3-latency-status.md); **200ms target MISS** |

## Cutover design

| Flag | Meaning |
|------|---------|
| `UNIFIED_TURN_LIVE_ENABLED` | When `true`, unified-turn text + write-approval outcomes serve the user |
| `UNIFIED_TURN_SHADOW_ENABLED` | Shadow audits; skipped when live already ran the call |

Classical pipeline remains rollback (`LIVE=false` or live returns `None`). Writes stage `awaiting_confirm`.

## Progress

| Step | Status | Evidence |
|------|--------|----------|
| Cutover code + health flags on prod | **PASS** | `/health` `git_sha=e0210cf4…` @ `2026-07-23T01:30:13Z` (`unified_turn_live_enabled=true`) |
| `unified_turn.live.completed` | **PASS** | Cutover probe — e.g. `2026-07-22T22:57:35.668737Z` / Actions [29964616788](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/29964616788) |
| Monitoring window | **PASS (closed)** | [monitor JSON](unified-turn-phase4-monitor-live.json) — see section below |

## Monitoring window (closed 2026-07-23)

Script: `scripts/verify-unified-turn-phase4-monitor-live.py`  
Artifact: [`unified-turn-phase4-monitor-live.json`](unified-turn-phase4-monitor-live.json)  
Tip: `e0210cf4c68f12b1250a9771269e8f96b4898cad`

| Gate | Verdict | Evidence |
|------|---------|----------|
| LIVE enabled | **PASS** | `/health` live=true @ `2026-07-23T01:30:13.794893Z` |
| Copy / catalog leaks | **PASS** | greeting `unified_turn.live.completed` @ `2026-07-23T01:30:19.60872Z` conv `84df687c…`; thanks @ `01:30:30.763364Z` conv `8789dc88…`; email_intent @ `01:30:38.443055Z` conv `0e40fde8…` — `leaks=[]` |
| Write approval staged | **PASS** | conv `a447beb5-6e3e-4240-ac89-145a26e4ab05` — pending `awaiting_confirm`, `apollo.lists.create`, `tool.invoke.completed` n=0, live `connector_tool_proposal` / `live_served=true` |
| TTFT &lt;200ms | **MISS** | n=4, min 369 / p50 **481** / max 2184 ms — not claimed met |

## Shipped (2026-07-22 → 2026-07-23)

LIVE cutover + monitoring window closed on tip `e0210cf4…`. Write authority unchanged (stage only). Phase 3/4 **200ms TTFT remains MISS**.

Rollback: `UNIFIED_TURN_LIVE_ENABLED=false` + redeploy (or bump `UNIFIED_TURN_RESTART_NONCE`).

## Next

1. Optional: wire monitor script into `workflow_dispatch` for soak re-runs.
2. Keep tip promoting via green CI + Railway when auto-deploy stalls.
3. Do not remove classical pipeline until a longer soak is acceptable.
4. Do not claim 200ms TTFT.
