# What real value does the turn-shape gate provide? (site 8, fix-vs-retire input)

Requested before deciding whether to fix the routing gap or retire the gate.
This is an evidence-based read of what actually consumes the gate's verdict, not
a judgement on whether the idea is good.

## What the gate produces

`classify_turn_shape` returns `conversational | task_shaped | mixed` plus a
social/task split. The heuristic decides ~28% of real messages; the model tier —
the part that was dormant — decides the rest.

## Who actually consumes it

`classify_turn_shape` has exactly **two** callers.

### 1. `should_offer_conversational_path` — `agent_intelligence.py:2190`

```python
if (
    not live_enabled
    and should_offer_conversational_path(turn_shape, has_pending=pending_family_active)
):
```

This is the gate's original purpose: route a whole turn to
`generate_conversational_reply` instead of the task pipeline. It is **explicitly
disabled whenever unified-turn LIVE is enabled**, and the comment above it says
why:

> R1 (STA-334): when LIVE is enabled, skip phrase-bank-as-primary early-exit —
> LIVE already owns meta/pending/pure chat. Keep turn_shape + mixed social ack
> for classical tool fallthrough. **Rollback: UNIFIED_TURN_LIVE_ENABLED=false.**

LIVE is on in production (`unified_turn.live.completed` fires continuously), so
this consumer is standby code for a feature-flag rollback.

### 2. `_maybe_prepend_mixed_social_ack` — `unified_turn_reasoning_service.py`

Fires only on `shape == "mixed"`, and prepends a one-line warm ack to a
LIVE-served reply. Reached on 3 of the 9 `live_served` paths.

## What LIVE does instead, and why the gate isn't buying conversational quality

The LIVE path never calls `classify_turn_shape`. It calls the **heuristic
directly**, in a deliberately narrow role — `unified_turn_tool_retrieval.py:377`:

```python
def is_task_shaped_for_retrieval(message: str) -> tuple[bool, str, str]:
    """Lightweight shape hint for retrieval/model tier only — never skips the reasoning call.
    ...
    Ambiguous (None) → treat as task-shaped (fail closed to semantic retrieval).
    """
```

So on LIVE the shape hint selects a *retrieval strategy* (embedding vs keyword)
and the retrieval query. It never decides whether a reply is conversational, and
by design it never short-circuits the reasoning call.

Conversational quality on LIVE comes from the unified-turn reasoning model
itself, and the site 8 probe runs demonstrate it plainly. These are real
production replies to deliberately ambiguous, non-task messages, produced with
the gate never running:

- `"Good. Glad it clicked."`
- `"That's a reasonable place to pause."`
- `"That may be right. If it's not moving a decision or a customer outcome, don't spend more time on it."`

That is the capability the gate was built to guarantee, being delivered without
it.

## Honest value summary

| Consumer | Live today? | Value if the gate's model tier ran |
|---|---|---|
| `should_offer_conversational_path` | No — off while LIVE is on | Whole-turn conversational routing; this is the documented `UNIFIED_TURN_LIVE_ENABLED=false` rollback path |
| `_maybe_prepend_mixed_social_ack` | Yes, 3 of 9 paths | A one-line warm ack prepended to mixed social+task messages |
| LIVE retrieval shape hint | Yes | **None** — it calls the heuristic directly and would not benefit from the fix |

So as currently wired, the gate's live value is **one cosmetic social-ack
prefix**, and its substantial value is **rollback insurance**.

## What this does not tell us

How often the model would return `mixed` is unmeasured. The heuristic reaches
`mixed` once per 1000 real messages, but it can only do so when a comma or
`also/but/anyway/btw` joins the two halves — a syntactic accident, not a
semantic judgement. The model could plausibly find it far more often, which
would raise the social-ack value above "cosmetic". Measuring that requires the
gate to actually run on LIVE traffic, which is the fix side of the decision.

## The two options, restated with this evidence

**Fix the routing** — call `classify_turn_shape` from the LIVE path so the
social ack works as designed and the shape verdict is available to LIVE. Cost:
one FAST classification call on ~72% of turns, for a feature whose upside is
currently unquantified.

**Retire it** — delete the gate and the `mixed` ack branch. Cost: this also
deletes the documented rollback path for `UNIFIED_TURN_LIVE_ENABLED=false`. That
flag would need retiring first, or the rollback accepted as gone. Not dead code
in the usual sense: standby code plus one small live feature.

A third option worth naming: **keep the heuristic, retire only the model tier.**
The heuristic is what LIVE actually uses, it is free, and it is deliberately
scoped to "never skips the reasoning call". This would preserve every consumer
that currently works, drop the per-turn model cost, and be honest that the
conversational judgement now lives in the unified-turn model rather than in a
separate gate.

## Decision (2026-09-02) — keep the heuristic, retire the model tier

Cesar chose the third option after reading the value report above.

**Shipped**

- `_model_turn_shape` deleted, along with `TurnShapeResult` and the module's last
  `get_model_router` reference. The gate now calls no model at all.
- `heuristic_turn_shape` is unchanged. It is what LIVE actually consumes via
  `is_task_shaped_for_retrieval`, and what `maybe_social_ack_with_pending_note`
  consumes for the mixed social ack. Both still work.
- When the heuristic declines (~72% of gate calls), the gate fails closed to
  `task_shaped` with reason `heuristic_declined_model_tier_retired`. This is the
  same verdict the dormant call produced for months — now intentional and named,
  rather than the silent result of a swallowed TypeError.
- The `turn.shape.classified` instrument is kept as the only visibility into a
  component whose reach was measured at near zero, and now carries
  `modelTierRetired: true`. Volume caveat recorded in the code: if routing ever
  sends real traffic through this gate, sample rather than write a row per turn.

**Why this is not simply reverting the site 8 fix**

The dormant call and the retirement produce the same runtime behaviour, so it is
fair to ask what the fix bought. It bought the measurement. While the call was
dormant, nobody could tell the difference between "this gate is load-bearing and
broken" and "this gate is not load-bearing". Fixing it, instrumenting it, and
running live traffic against it is what produced the near-zero reach figure and
the three findings above — and therefore what made an evidence-based retire
decision possible instead of a guess.

**Tests**

`backend/tests/services/test_turn_gate_reaches_model.py` was inverted. It now
asserts that no model is reachable, pins the heuristic behaviour every remaining
consumer depends on, and adds a structural check that `get_model_router` cannot
reappear in the module. 16 tests, all passing.

Mutation-proven: restoring the model tier in its original swallowing
`except Exception: pass` shape fails 6 of the 16. The call-counting assertion
sits outside the mocked router, so the broad handler cannot hide it — this is
the specific blind-test trap the clarification-engine tests fell into earlier in
this program.
