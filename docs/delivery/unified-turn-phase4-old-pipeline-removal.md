# Unified turn — old pipeline removal (post Phase 4 sign-off)

Status: **SCHEDULED — not started**  
Prerequisite: Phase 4 sign-off on tip `e5886123…` ([cutover status](unified-turn-phase4-cutover-status.md)).  
This work is a **separate reviewed step** — do not bundle with STA-305 or cutover docs.

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
| `generate_social_ack` / mixed ack helpers | Prepended on LIVE mixed turns |
| `generate_conversational_reply` for meta capability bank | Served by `resolve_unified_live_meta_capability_reply` |
| `chat_action_mapper` as **library** for tests / STA-305 local mapper / non-chat surfaces | May shrink; not a blind delete |
| Classical fallthrough when `apply_unified_turn_live` returns `None` | Rollback until soak criteria met |

## Removal phases (proposed)

### R0 — Soak gate (no code delete)

Documented window after Phase 4 sign-off. Exit criteria:

- Zero raw catalog keys in live chat copy (monitor / battery)
- Zero write invokes bypassing approval
- Core Phase 2 batteries still green on tip
- Explicit human OK to open R1

### R1 — Dead-path flags (reviewable PR)

- When `UNIFIED_TURN_LIVE_ENABLED=true`, skip classical conversational early-exit and mapper-first planning that never run after LIVE `stop_pipeline` (audit with coverage / call counts first).
- Add metrics: `unified_turn.live.served` vs `unified_turn.live.fallthrough` rate.

### R2 — Delete unused classical generators

Only after R1 shows fallthrough ≈ 0 for the soak window:

1. Conversational path early-return in `agent_intelligence` that duplicates LIVE meta/social (keep helpers used by LIVE).
2. Mapper-as-primary segment planning for chat NL (retain mapper for STA-305 local probe or move that probe to unified audit assertions).
3. Phrase-bank-as-primary for non-pending conversational replies (banks may remain as few-shot / ack fragments).

### R3 — Cleanup

- Remove obsolete shadow-only flags if any.
- Update `docs/delivery/unified-turn-reasoning-phase0.md` pipeline map.
- Re-run Phase 2 combined + Phase 4 monitor on tip; cite evidence.

## Explicit non-goals

- Not a rewrite of ReAct / Meson / canvas write gates.
- Not removing Module B ledger / turn controller.
- Not claiming STA-305 live PASS (still **BLOCKED — OPEN** until HubSpot+Slack in isolated org).

## Human gate before R1 merge

Named owner approval: “fallthrough rate acceptable; rollback still works via `UNIFIED_TURN_LIVE_ENABLED=false`.”
