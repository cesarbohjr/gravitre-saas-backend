# Orch unrelated hold/abandon regression — root cause (2026-07-21)

## Answers (required order)

### 1. How did a presentation pass surface this?

**Phrase-variety / bank-first did not modify orch routing.** Commits `8aca00b4`…`e8dd0a1a` do not patch `_should_supersede_pending_orchestration` or the pre-classifier clear block.

The three failing battery cases are all **orch-seeded** (`awaiting_plan_confirm`). They hit this path in `chat_orchestration_service.process_turn` **before** the pending-reply classifier:

```python
if awaiting_plan/step and _should_supersede_pending_orchestration(...):
    await _clear_orchestration(...)
    return None  # pipeline then answers the new ask with no abandon/hold
```

For the failing prompts, supersede is `True` (run-history / how-many / disjoint Apollo vs HubSpot plan). Gmail/Slack seeded unrelated cases never enter this block — they still returned hold/abandon (21/24).

### 2. Did conversational bank-first compete with the classifier?

**No.** Bank-first only changes wording inside `compose_pending_social_aside` / `generate_conversational_reply` after intent is already `unrelated`. The failing turns never reached that handler because silent supersede cleared pending and returned `None` first.

The conversational gate also does not short-circuit when `has_pending_family` is true.

### 3. Fix

- Remove silent supersede-before-classifier for live awaiting orch.
- Add orch **hold-prompt resolution** before confirm→execute so bare `yes` parks/clears instead of starting the old plan.
- Unit test updated: unrelated Slack while Apollo orch awaits → abandon/hold prompt, not `None`.

## Verification

Full live `scripts/verify-pending-reply-classifier-live.py` must be **24/24**, not 21/24 broad pass.
