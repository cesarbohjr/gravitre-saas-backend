# Module D — Gravitree Voice Layer

One persona SoT: [`backend/app/services/gravitree_voice.py`](../../backend/app/services/gravitree_voice.py).

## Exports

| Export | Role |
|--------|------|
| `GRAVITREE_VOICE_RULES` | Canonical trait list |
| `HOUSE_PHRASING` | Curated Gravitree lines |
| `voice_system_prompt_section()` | The one `## Voice` block (confidence register + humor budget) |
| `apply_voice(system_prompt)` | Idempotent inject / strip legacy `VOICE:` |
| `format_operator_message(...)` | Approvals, errors, notifications, canvas, skip reasons |
| `humor_permitted(kind, allow_humor)` | Humor budget gate |
| `chev_term(status)` | Connected / Healthy / Executable / Verified |
| `domain_focus_section(modifier)` | Persona overlays under `## Domain focus` |
| `format_outcome_digest(items, …)` | **Executive Digest** over Module A outcome batches |
| `coerce_outcome_digest_item(...)` | Normalize stream/DB rows into `OutcomeDigestItem` |
| `OutcomeDigestItem` | Stable digest item shape |

### Confidence register

`certain` · `estimate` · `blocked` — wired into chat prompts, Meson interpret/alerts, and canvas write-blocked / approval copy.

### Humor budget

`allow_humor=True` only for low-stakes kinds (e.g. `success_win`). Forced off for write approval, tool errors, canvas write blocked, connector-connect skips, Meson failure alerts.

## Call sites

1. `_build_system_prompt` — chat / agent surfaces
2. `react_engine` — `apply_voice` before harden
3. `conversation_turn_controller` — voice section + cancel copy
4. `tool_error_messages` / write approvals / run notifications
5. `meson_service` — `apply_voice` + blocked register on failure alerts + light success idle
6. `canvas_write_gate` — write blocked copy; execute paths preserve voice via `user_facing_message_from_write_authority_error`
7. Skip reasons / execution envelope
8. `GET /api/workflows/execution-outcomes/executive-digest` — live digest from `intelligence_outcome_events`

## Sanitize-away fix (Round 3 close)

Gate emitted voice `PermissionError`; linear/graph/dry-run/digital-twin catch blocks had replaced it with `"Step execution failed"`. Helper `user_facing_message_from_write_authority_error` preserves the voice suffix on all four paths.

## Executive Digest

Depends on Module A `finalize_execution_outcome` → `intelligence_outcome_events` + `outcome_event_bus`. `format_outcome_digest` is implemented; ops consumer at `/execution-outcomes/executive-digest`.

## Verification

```bash
pytest backend/tests/services/test_gravitree_voice.py \
  backend/tests/services/test_canvas_write_gate.py -q
```

**Done bar:** merge → Railway redeploy → canvas write-blocked tip run shows voice string; digest endpoint returns real last-24h copy.

## Expression range (2026-07-21)

Phrase variety for recurring categories — see
[`module-d-expression-range.md`](module-d-expression-range.md).
Selection: `task_state.voice_expression_last` + deterministic rotation.
Does not change Module B classification.

## Unified-turn imperfect input (2026-07-22)

On the single-reasoning-call path, Module D’s system instruction
(`module_d_unified_voice_spec.py`) includes a HARD rule: silently understand
typos, missing words, disordered phrasing, and voice-garble; **never** correct
spelling/grammar or narrate recovery (“I think you meant…”). Verified in the
Phase 2 imperfect-input battery (`verify-unified-turn-phase2-live.py`).
