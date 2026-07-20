# Module D — Gravitree Voice Layer (STA-332)

## Standing rule

No per-surface tone patches. If VOICE prose only lands in `assistant.py`, only in
Meson, or only for Slack/Gmail, it is the wrong fix. One module; every surface
calls in — same pattern as `catalog_write_authority`.

## Goal

One persona every chat reply, error message, notification, and Meson response
pulls from: calm expert, facts-first, Connected / Healthy / Executable / Verified
vocabulary, no buzzwords, light rare humor, never cute. Leads with the fact,
shows its work, states uncertainty plainly, never over-apologizes, never hedges
with "I think" when it has a real answer.

## Architecture

| Piece | Module |
|-------|--------|
| Voice SoT | [`backend/app/services/gravitree_voice.py`](../../backend/app/services/gravitree_voice.py) |
| Planner ownership (chat / ReAct / canvas) | [`conversation_turn_controller.py`](../../backend/app/services/conversation_turn_controller.py) attaches `voice_section` |
| Shared LLM prompt builder | [`agent_intelligence._build_system_prompt`](../../backend/app/operators/agent_intelligence.py) injects `voice_system_prompt_section()` |
| Domain overlays | [`persona_service.py`](../../backend/app/services/persona_service.py) — domain focus only; cannot replace Voice |

```
Surfaces (chat · ReAct · canvas · Meson · errors · notifications)
        │
        ▼
 gravitree_voice  (voice_system_prompt_section / apply_voice / format_operator_message)
        ▲
        │
 conversation_turn_controller (Module B) — ownership for connector-turn copy
```

Meson still bypasses Module B's planner; it calls `apply_voice` directly until
Meson→B unification ships.

## API

| Export | Role |
|--------|------|
| `GRAVITREE_VOICE_RULES` | Canonical trait list |
| `voice_system_prompt_section()` | The one `## Voice` block |
| `apply_voice(system_prompt)` | Idempotent inject / strip legacy `VOICE:` |
| `format_operator_message(kind, **ctx)` | Approvals, tool errors, notifications, turn cancel |
| `chev_term(status)` | Connected / Healthy / Executable / Verified labels |
| `domain_focus_section(modifier)` | Persona overlays under `## Domain focus` |

## Call sites (v1)

1. `_build_system_prompt` — chat / agent surfaces
2. `react_engine` — `apply_voice` before `harden_system_prompt`
3. `conversation_turn_controller` — `voice_section` + pending-plan cancel copy
4. `tool_error_messages.format_tool_error_for_user`
5. `connector_action_workflows.format_write_approval_message`
6. `execution_outcome` notification title/body defaults
7. Chat write approval requester notification
8. `meson_service` interpret prompt

## Department personas

Selector UI kept. `COMMUNICATION_PERSONAS` modifiers are domain-focus only
(what to emphasize). Base Voice always wins.

## Verification

```bash
pytest backend/tests/services/test_gravitree_voice.py \
  backend/tests/test_conversational_intelligence.py \
  backend/tests/services/test_tool_error_messages.py -q
```

**Done bar (user-facing):** merge → Railway redeploy → live chat tip with
evidence pointer. Local pytest green alone is not production-fixed.

## Sequencing

| Dependency | Status |
|------------|--------|
| Module B chat/ReAct entry | Met — wired |
| Module B Meson unification | Not required for voice SoT |
| Module A / C | Not required |
