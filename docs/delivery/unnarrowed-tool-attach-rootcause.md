# `unnarrowed_tool_attach_blocked` — root cause, 2026-09-02

Closes the last standing WATCH item from the twelve-site dormant-call audit.
Carried as WATCH because 119 events had been observed and explained away by
*"stopped on its own, never touched a real org"* — with no root cause. This
document supplies the root cause, and reports what that turned up.

## What the guard is

`assert_tools_narrowed` in `backend/app/services/narrowed_tools.py`, enforcing
`G5-RISK-UNNARROWED-FALLTHROUGH` (added 2026-08-05, `16e5ed84`). Any path calling
a model with tools must pass them through `narrow_tools_for_turn` or
`embed_narrow_tools_for_turn`, which return a `NarrowedTools` list carrying
`gravitre_narrowed = True`. A non-empty tool list without that marker raises.

Narrowing decides which tools the model can see on a turn, so an unnarrowed
attach hands the model tools outside that turn's scope. The guard fails closed:
it aborts the LIVE reasoning call and the turn drops to the classical path, so
the user still gets an answer. That is why the whole burst surfaced only as
`outcome_error` telemetry and never as visible breakage.

**The guard was never wrong.** It fired correctly every time. The defect was
always in the plumbing that lost the evidence.

## Root cause

`NarrowedTools` is a `list` subclass and the proof is an *attribute*. Every
ordinary way of copying a list — `list(x)`, a comprehension, a slice — returns a
plain `list` and silently discards it. The marker survives being passed around;
it does not survive being rebuilt.

This produced **two independent instances of the same mistake**, which is why
one fix did not close it.

### Instance 1 — `unified_turn.round_0`, 111 events

```python
round_tools = [] if conversational_no_tools else list(attach_tools)
```

`list()` stripped the marker on **every** tool-carrying turn, so the round-level
assert raised every time. Fixed 2026-08-13 at `65161f90` ("fix NarrowedTools
round-trip in unified turn"), which introduced the marker-preserving branch.

That commit date is exactly the day the events stopped — 10 events on 08-12,
109 on 08-13, none after. So instance 1 was fixed three weeks before this
investigation; nobody had connected the fix to the burst.

### Instance 2 — `provider_tool_router.complete_with_tools`, 8 events

**Not fixed by `65161f90`, and still live until today.**

```python
kwargs["tools"] = [openai_tool_payload(t) for t in round_tools]
```

The 08-13 repair restored the `round_tools` round-trip but left this conversion
one line below still stripping the marker. That value is handed to
`complete_with_tools`, which asserts narrowing a second time.

It stopped producing events for a reason that has nothing to do with being
fixed: only **non-OpenAI** models reach it. `_complete_unified_turn` routes
OpenAI models to the streaming branch, which never calls `complete_with_tools`.
Because the deployment routes unified turns to OpenAI models (`gpt-4o-mini`,
`gpt-5.4-mini` in the traces), the path simply stopped being exercised. Any
Anthropic or Gemini turn carrying tools would still have tripped the guard and
silently dropped to the classical path.

**This is why the WATCH label was right and "closed on no recurrence" would have
been wrong.** Silence was absence of traffic, not absence of a defect.

### The underlying trap

`NarrowedTools.as_openai_tools()` — the *sanctioned* helper for producing
provider payloads — returned a plain list. The one method whose entire job is
this conversion discarded the proof, so every correct caller was set up to fail.
That is the real design fault behind both instances.

## Fix

| file | change |
|---|---|
| `narrowed_tools.py` | `as_openai_tools()` returns `NarrowedTools`, preserving `stats` and `source`. Still strips provider-illegal keys; serialises identically on the wire. |
| `unified_turn_reasoning_service.py` | Payload conversion preserves the marker (instance 2 fixed). |
| `unified_turn_reasoning_service.py` | Guard moved to run **before** the conversion. |
| `unified_turn_reasoning_service.py` | Unreachable `else` arm no longer strips (defensive; see caveats). |

### Ordering matters

The conversion now *carries proof forward*, so it may only run once the guard
has established that the proof is real. Reversed, it would launder an unnarrowed
list into a narrowed-looking one and make the invariant decorative. A structural
test pins the order, and mutation M3 confirms reversing it is caught.

## Why this went undetected for 109 events

The guard was tested. The helpers were tested. **The turn was not.** No test
asserted that `run_unified_turn_shadow` reaches the model with tools that still
pass the guard, so the one thing that broke was the one thing unobserved.

Mutation testing proved this was a live hole, not a hypothetical: with the
original round-trip defect reintroduced, the entire suite stayed green.

`backend/tests/services/test_unified_turn_attaches_narrowed_tools.py` now drives
the real function and inspects what reaches the provider dispatch.

## Verification

`python scripts/mutate_narrowed_tools_roundtrip.py` — **5 of 5 mutations caught**
(was 4 of 5 before the end-to-end harness existed):

| mutation | caught by |
|---|---|
| M1 `as_openai_tools` returns a plain list (the trap) | round-trip tests |
| M2 payload conversion strips the marker (instance 2) | round-trip + provider tests |
| M3 guard moved after the conversion (laundering) | structural order test |
| M4 preserving branch removed (**the actual 08-13 defect**) | end-to-end harness |
| M5 guard downgraded to a no-op (the invariant itself) | guard tests |

Suites: `2985 passed`, 4 pre-existing failures unrelated to this change
(`test_agent_memory_service`, `test_connector_output_contract` ×2,
`test_workspace_memory_and_metrics`) — confirmed pre-existing by re-running them
with these source changes stashed.

M4 was initially written unfaithfully: it mutated the `else` arm, which never
executes because `attach_tools` is always a `NarrowedTools`. Rewritten to remove
the preserving branch entirely, i.e. the true pre-`65161f90` shape.

## Evidence status — read this before quoting a PASS

Deliberately **not** labelled PASS.

- **Root cause: PROVEN.** Git archaeology (`65161f90`, 2026-08-13) matches the
  event dates exactly; both attach sites traced in code to their call chains.
- **Instance 1: fixed in production since 2026-08-13.** Supporting evidence is
  the absence of events since, which is weak on its own but corroborated by the
  commit that repaired the exact expression on the exact day.
- **Instance 2: fixed locally, mutation-proven, NOT production-verified.**
  Cannot be proven live from prod telemetry, because prod does not route unified
  turns to non-OpenAI providers, which is precisely why it stayed dormant. A
  genuine prod PASS requires a real Anthropic- or Gemini-backed tool-carrying
  turn. Until then this is **PARTIAL**.
- **Regression coverage: closed**, mutation-proven at 5/5.

## Caveats

- The `else` arm in the round-tools selection is **unreachable** in practice
  (`attach_tools` is always `NarrowedTools`). Hardening it is defensive only, and
  no test covers it — mutating it alone changes no behaviour.
- The end-to-end harness had to pin the model-router singleton. It first passed
  standalone and failed in the full suite, because the turn bails with
  `openai_client_unavailable` when the shared router has no client — dependent on
  what ran earlier in the session. Pinned explicitly; a version of this test that
  only passed in isolation would have been another broken instrument.
- The React path (`react_engine._chat_with_tools`) was checked and is safe: it
  passes the `NarrowedTools` from `narrow_tools_for_turn` straight through.

## Lesson: a third countermeasure for "Class B: broken instrument"

Recorded in `dormant-model-calls.md`. The pattern here is new enough to name:

> **Proof carried as an attribute on a mutable value will be lost by ordinary
> copying, and the loss is silent.** Guarding the invariant is not enough; the
> guard must be exercised end-to-end through the real call path, or the plumbing
> between guard and provider is unobserved.

And a governance lesson:

> **"Has not recurred" is not a root cause.** It is indistinguishable from "has
> not been exercised." Instance 2 had been silently broken for three weeks and
> would have stayed broken until the first non-OpenAI turn.
