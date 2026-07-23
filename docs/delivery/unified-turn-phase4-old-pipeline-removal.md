# Unified turn — old pipeline removal (post Phase 4 sign-off)

Status: **R1 PASS on tip `23dfa298`** (pending-modify follow-up pending deploy; R2 deletes not started)  
Prerequisite: Phase 4 sign-off on tip `e5886123…` ([cutover status](unified-turn-phase4-cutover-status.md)).  
STA-305 live exception cleared 2026-07-23 (conversation `6b920797-…`).  
Human authorization 2026-07-23: proceed through R1 → commit → push main → deploy.

## Intent (from program Phase 4)

Once LIVE is stable, remove the duplicate classical generators so there is one reasoning path:

- LIVE owns pure conversational text (even when connectors upgrade `standard` → `agent`)
- Classical owns tool SSE / `connector_tool_proposal` / Module B confirm-modify-slot
- Phrase-bank primary skipped when LIVE enabled (rollback via flag)

Keep write governance (`catalog_write_authority`, approval staging, Module A) unchanged.

## Do not remove (still on LIVE hot path)

| Component | Why it stays |
|-----------|----------------|
| `pending_reply_classifier` + `format_unrelated_hold_prompt` | Owned by `unified_turn_pending_live` for hold/abandon / meta / ambiguous |
| `generate_social_ack` / mixed ack helpers | Prepended on LIVE mixed turns; classical mixed ack kept for tool fallthrough |
| `generate_conversational_reply` for meta capability bank | Served by `resolve_unified_live_meta_capability_reply` |
| `chat_action_mapper` as **library** for tests / STA-305 local mapper / non-chat surfaces | May shrink; not a blind delete |
| Classical fallthrough when `apply_unified_turn_live` returns `None` | Rollback + intentional tool SSE defer + pending confirm/modify |

## Removal phases

### R0 — Soak gate

Phase 4 monitor + Phase 2 combined green on tip `e5886123…`. STA-305 live PASS after OAuth clone. Human OK to open R1: **granted 2026-07-23**.

### R1 — Dead-path flags (shipped on `23dfa298`)

1. **Narrow defer** — LIVE owns pure conversational text even when mode upgrades to `agent`. Defer only `connector_tool_proposal` + wave67 tool-SSE probe patterns.
2. **Skip phrase-bank primary** when `UNIFIED_TURN_LIVE_ENABLED=true`.
3. **Metrics** — `unified_turn.live.fallthrough` + `fallthrough_reason`.
4. **Pending ownership** — when pending family active and resolver returns None (confirm/reject/modify/slot), return immediately to classical (do not run shadow).

**Prod evidence:** tip `23dfa2989285231066f4924ed6f6d71738f29c53` — Phase 4 monitor `ok=true` (copy PASS, write staged PASS, TTFT MISS). Imperfect 16/16 after harness accepts `live.fallthrough`.

Rollback: `UNIFIED_TURN_LIVE_ENABLED=false`.

### R2 — Delete unused classical generators

**Not in this ship.** Wait until prod fallthrough rates show unintentional conversational fallthrough ≈ 0.

### R3 — Cleanup

- Update pipeline map docs
- Full Phase 2 combined green on tip
- Close [STA-334](https://linear.app/staqbot/issue/STA-334)

## Migrations

None — flag + code path only.
