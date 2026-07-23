# Unified turn Phase 4 — cutover status

Updated: 2026-07-23

## Prerequisites

| Gate | Status |
|------|--------|
| Phase 2 core batteries | **PASS** on tip `e5886123…` — see [combined live](unified-turn-phase2-combined-live-status.md) |
| Phase 3 streamed TTFT | **Measured** — [phase3](unified-turn-phase3-latency-status.md); **200ms target MISS** |

## Cutover design

| Flag | Meaning |
|------|---------|
| `UNIFIED_TURN_LIVE_ENABLED` | When `true`, unified-turn text + write-approval outcomes serve the user |
| `UNIFIED_TURN_SHADOW_ENABLED` | Shadow audits; skipped when live already ran the call |

Classical pipeline remains rollback (`LIVE=false` or live returns `None`). Writes stage `awaiting_confirm`.

## Progress

| Step | Status | Evidence |
|------|--------|----------|
| Cutover code + health flags on prod | **PASS** | tip line including `e5886123…` with `unified_turn_live_enabled=true` |
| `unified_turn.live.completed` | **PASS** | Cutover + monitoring + Phase 2 combined suite |
| Monitoring window | **PASS (closed)** | [monitor JSON](unified-turn-phase4-monitor-live.json) |
| Phase 2 combined functional matrix | **PASS** (named STA-305 exception) | [combined](unified-turn-phase2-combined-live-status.md) on tip `e5886123…` |

## Sign-off (2026-07-23)

**VERDICT:** Phase 4 signed off. Unified-turn architecture proven live and correct across all core batteries (targeted 21/21, imperfect 16/16, pending-reply 24/24, conversational 20/20, knowledge-boundary, run-history/stale-plan, persona-drift, send-email), on deployed tip `e5886123`.

**NAMED EXCEPTION:** STA-305 live connector verification remains outstanding, blocked on HubSpot + Slack connection in the isolated test org. Mapper-level logic confirmed correct via local check; this is **not** equivalent to a live proof and must not be represented as one. Harness exit-code framing reverted so BLOCKED stays exit **2** / matrix **BLOCKED — OPEN**, not a silent green pass, until real connectors are in place and the live flow is actually run.

Evidence pointer for the core close: [`unified-turn-phase2-combined-live.json`](unified-turn-phase2-combined-live.json) — tip `e58861233291c61452ddf480f13dc0fa782ec3f7`, suite `ok=true`. STA-305 artifact same window: `verdict=BLOCKED`, `live.skipped=true`, `connected=['apollo']`, no conversation id.

Rollback: `UNIFIED_TURN_LIVE_ENABLED=false` + redeploy (or bump `UNIFIED_TURN_RESTART_NONCE`).

## Next steps (separate from this sign-off)

1. Connect HubSpot + Slack in the isolated org (still the one remaining human action, unchanged across several rounds now).
2. Run the real STA-305 live flow once connected — get an actual conversation ID and Slack draft transcript.
3. Schedule removal of the old pipeline code (`conversational_turn_gate`, `chat_action_mapper` regex path, the old phrase-bank-as-primary-generator), per the original Phase 4 plan, as its own reviewed step now that sign-off has happened — **not** bundled into this close.

## Monitoring window (closed earlier 2026-07-23)

Script: `scripts/verify-unified-turn-phase4-monitor-live.py`  
Artifact: [`unified-turn-phase4-monitor-live.json`](unified-turn-phase4-monitor-live.json)

| Gate | Verdict |
|------|---------|
| Copy / catalog leaks | **PASS** |
| Write approval staged | **PASS** |
| TTFT &lt;200ms | **MISS** (not claimed) |
