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

| # | Step | Status | Notes |
|---|------|--------|-------|
| 1 | Connect HubSpot + Slack in isolated org `f07e57c0-1501-4000-8000-c04e57a00001` | **PASS** | [STA-333](https://linear.app/staqbot/issue/STA-333). OAuth clones from operator workspace via `scripts/provision-isolated-hubspot-slack-connectors.py` (not UI OAuth). Artifact: [`isolated-hubspot-slack-connector-provision.json`](isolated-hubspot-slack-connector-provision.json). |
| 2 | Run real STA-305 live (`STA305_LIVE=1`) | **PASS** | Same ticket. See **STA-305 live exception cleared** below. |
| 3 | Old pipeline removal (reviewed step) | **R1 PASS** | [STA-334](https://linear.app/staqbot/issue/STA-334). Tips `23dfa298` / `6801a82f` — LIVE conversational + fallthrough audits + pending modify → classical. Phase 4 monitor PASS; imperfect 16/16. R2 deletes wait on soak. |

## STA-305 live exception cleared (2026-07-23)

**PASS** — live Slack draft omit-detail path in isolated org (not mapper-only).

| Field | Value |
|-------|--------|
| Provision | hubspot `41175658-…`, slack `98d82730-…` healthy in `f07e57c0-…` @ `2026-07-23T08:57:14Z` |
| Probe | `STA305_LIVE=1 python scripts/smoke-sta305-slack-draft.py` |
| Health tip | `5b515b56b3e9f850ad7075a9e957dec5faecbe04` |
| Conversation | `6b920797-f6ec-4dd2-ac0d-aaf2b963c69a` |
| Labels | `Search contacts`, `Post message` (`list_channels_seen=false`, `post_like_seen=true`) |
| Transcript head | 2-step orchestration; write steps require approval; reply **yes** |
| Artifact | [`sta305-catalog-kind-prod.json`](sta305-catalog-kind-prod.json) — `verdict=PASS` |

Named exception in the sign-off section above is **cleared by this evidence**. Operator workspace tokens were cloned read-only into the smoke org (shared OAuth install — smoke-only).

## Monitoring window (closed earlier 2026-07-23)

Script: `scripts/verify-unified-turn-phase4-monitor-live.py`  
Artifact: [`unified-turn-phase4-monitor-live.json`](unified-turn-phase4-monitor-live.json)

| Gate | Verdict |
|------|---------|
| Copy / catalog leaks | **PASS** |
| Write approval staged | **PASS** |
| TTFT &lt;200ms | **MISS** (not claimed) |
