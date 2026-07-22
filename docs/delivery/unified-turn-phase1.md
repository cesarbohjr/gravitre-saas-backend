# Unified turn — Phase 1 (shadow path) closed

## Goal

One reasoning call per turn (conversation + pending context + narrowed native tools),
with the **full Module D voice specification** as the system instruction — running
**alongside** the classical classify-then-route pipeline. User-visible replies still
come from the classical path. Shadow does **not** execute tools.

## Delivered

| Piece | Role |
|-------|------|
| `unified_turn_pending_context.py` | Pending/ledger/plan → model context (not a classifier) |
| `module_d_unified_voice_spec.py` | Full Module D system instruction (registers, knowledge boundaries, drift self-check, few-shots) |
| `unified_turn_reasoning_service.py` | Single OpenAI tools call; audit `unified_turn.shadow.completed` |
| `AgentIntelligence.execute_task_streaming` | Fire-and-forget `schedule_unified_turn_shadow` when flag on |
| Settings | `UNIFIED_TURN_SHADOW_ENABLED` (default **false**), `UNIFIED_TURN_SHADOW_MAX_TOOLS` (default 32) |

## Standing rule

`catalog_write_authority`, approval flow, Module A outcomes, and audit trail for
**execution** are unchanged. Shadow may only **propose** a tool + args in the audit
payload; it never calls `execute_plan` / ReAct write gates.

## Phase 0

See [`unified-turn-reasoning-phase0.md`](unified-turn-reasoning-phase0.md).

## Live verification

```bash
EXPECT_SHA=2645c011 python scripts/verify-unified-turn-phase1-live.py
```

Artifact: [`unified-turn-phase1-live.json`](unified-turn-phase1-live.json)

### Evidence (PASS — 2026-07-22)

| Check | Result |
|-------|--------|
| Prod tip | `acb44e3b…` (ancestor of Module D voice `2645c011`) |
| Classical user path | SSE reply served (shadow did **not** replace it) |
| Shadow audit | `unified_turn.shadow.completed` @ `2026-07-22T09:48:20.674876Z` |
| Conversation | `51b39f39-f770-46f4-92ee-3584da9bda06` |
| Shadow outcome | `conversational_reply` (`gpt-4o-mini`, 615ms) — distinct from classical house line |
| Flag | `UNIFIED_TURN_SHADOW_ENABLED` inferred **on** (audit fired) |
| Unit tests | `pytest backend/tests/services/test_unified_turn_reasoning.py` → **7 passed** |

Dual-path proof: classical preview was a house greeting line; shadow audit `user_message` was a different conversational reply — same turn, two paths, only classical visible.

## Cutover (not Phase 1)

Phases 2–4 (batteries, TTFT streaming, active traffic, old-pipeline removal) remain
gated. Do not remove `conversational_turn_gate` / `pending_reply_classifier` /
mapper until Phase 4.
