# Unified turn — old pipeline removal (post Phase 4 sign-off)

Status: **R1 IN PROGRESS → ship then verify**  
Prerequisite: Phase 4 sign-off on tip `e5886123…` ([cutover status](unified-turn-phase4-cutover-status.md)).  
STA-305 live exception cleared 2026-07-23 (conversation `6b920797-…`).  
Human authorization 2026-07-23: proceed through R1 → commit → push main → deploy.

## Intent (from program Phase 4)

Once LIVE is stable, remove the duplicate classical generators so there is one reasoning path:

- `conversational_turn_gate` as primary turn-shape router for user-visible replies
- `chat_action_mapper` regex/phrase matching as primary NL→catalog planner
- Phrase-bank / expression banks as **primary** conversational generator

Keep write governance (`catalog_write_authority`, approval staging, Module A) unchanged.

## Do not remove (still on LIVE hot path)

| Component | Why it stays |
|-----------|----------------|
| `pending_reply_classifier` + `format_unrelated_hold_prompt` | Owned by `unified_turn_pending_live` for hold/abandon / meta / ambiguous |
| `generate_social_ack` / mixed ack helpers | Prepended on LIVE mixed turns; classical mixed ack kept for tool fallthrough |
| `generate_conversational_reply` for meta capability bank | Served by `resolve_unified_live_meta_capability_reply` |
| `chat_action_mapper` as **library** for tests / STA-305 local mapper / non-chat surfaces | May shrink; not a blind delete |
| Classical fallthrough when `apply_unified_turn_live` returns `None` | Rollback + intentional tool SSE defer |

## Removal phases

### R0 — Soak gate

Phase 4 monitor + Phase 2 combined already green on tip `e5886123…`. STA-305 live PASS after OAuth clone. Human OK to open R1: **granted 2026-07-23**.

### R1 — Dead-path flags (this ship)

1. **Narrow defer** — `standard` mode pure conversational is LIVE-owned again. Blanket `standard ∈ _CLASSICAL_TOOL_SSE_MODES` from `4261014e` was over-broad (broke LIVE greetings while classical phrase-bank still answered). Keep defer for:
   - `connector_tool_proposal` (classical tool SSE / react_write_gate)
   - `reasoning` / `agent` modes
   - `requires_action` classification
   - `message_requires_classical_tool_sse` (connectors/KB/Apollo/Slack probe utterances)
2. **Skip phrase-bank primary** when `UNIFIED_TURN_LIVE_ENABLED=true` (classical conversational early-exit gated off). Mixed social ack retained for tool fallthrough.
3. **Metrics** — audit action `unified_turn.live.fallthrough` with `fallthrough_reason` when LIVE returns `None`.

Rollback: `UNIFIED_TURN_LIVE_ENABLED=false` restores phrase-bank primary.

### R2 — Delete unused classical generators

**Not in this ship.** Wait until prod `unified_turn.live.fallthrough` rates show unintentional conversational fallthrough ≈ 0 (excluding `defer_*` / `read_tool_classical`).

Then:

1. Delete conversational early-return block (helpers stay for LIVE imports)
2. Demote mapper-as-primary only where unused
3. Phrase banks remain as ack / meta fragments

### R3 — Cleanup

- Update pipeline map docs
- Re-run Phase 2 combined + Phase 4 monitor on tip; cite evidence
- Close [STA-334](https://linear.app/staqbot/issue/STA-334)

## Explicit non-goals

- Not a rewrite of ReAct / Meson / canvas write gates.
- Not removing Module B ledger / turn controller.
- Not deleting `pending_reply_classifier` or mapper library.

## Migrations

None — flag + code path only.
