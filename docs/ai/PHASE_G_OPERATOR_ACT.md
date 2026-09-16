# Phase G — Operator act (vague prompts + connector reachability)

**Status:** Implemented in this increment (local pytest). Dual-path live `/ai` + `/agents/[id]/chat` **NOT RUN**. E6 GA4 OAuth remains `EXTERNAL_BLOCKED`. Writes stay confirm-gated; this phase does **not** authorize silent writes.

Phase F closed stop, honesty, typed parts, replay, prefix cache, and interrupt extras. The remaining chat deficit is **acting on underspecified prompts** with connected systems as computable context — not another Intelligence hub slice.

## Why this exists

Users type `help`, `fix it`, `handle this`, or a one-line ask with no vendor or fields. The operator must:

1. Infer intent from history, parameter ledger, interrupt extras, and connected integrations.
2. Treat listed connectors as **reachable** for READ this turn.
3. Treat WRITE as reachable only after explicit confirm (existing write gate).
4. Emit actions, reads, and requests as JSON the model can parse (`<operator_act_json>`).

## Constraints

- No invented prices, badges, Enable toggles, or “live ChatGPT-level” claims.
- Dual paths: classical ReAct (`_build_system_prompt`) and unified live (`unified_turn_reasoning_service`) both receive the block.
- Disconnected vendors are not reachable; absence is not uncertainty.
- Confirm policy unchanged: `policy.silent_writes = false`.

## This increment

`backend/app/services/operator_act_context.py` classifies `vague | read | write | mixed`, lists connected vendors (`read` + `write_gated`), compact catalog actions (v1 reads, v2 writes when the intent needs them), and ledger slots.

Injected as:

- `## Operator Act Context` in the **volatile** system tail (prompt-cache prefix stays stable).
- Unified-turn user/context part `operator_act` so Module D system text stays cache-stable.

## Done when

A vague prompt on a tenant with HubSpot connected results in a connected READ (or a confirm-gated write plan) without asking the user to restate what ledger + catalog already encode.

Live evidence required before PASS. Local tests: `test_operator_act_context.py`.

## Out of scope

- Auto-executing writes without confirm.
- Completing GA4 OAuth for the smoke org (human).
- Expanding connector OAuth surfaces.
