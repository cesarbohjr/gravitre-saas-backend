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

### Instance 3 — `_stable_tool_list(list(visible or []))`, never fired

Found 2026-09-02 by `scripts/scan_narrowed_tools_strips.py`, written to answer
the question "is there a third one?"

`_stable_tool_list` has its own preserve-branch:

```python
if isinstance(tools, NarrowedTools) or getattr(tools, "gravitre_narrowed", False):
    return mark_narrowed(...)
```

but the caller wrapped the argument in `list()` first, so that branch could
never see a `NarrowedTools` and was **dead code**. `visible` came back
unnarrowed. It never reached the guard only because both downstream branches
(`apply_progressive_disclosure` and `mark_narrowed`) re-mark unconditionally —
i.e. it was harmless by luck, and a third branch would have broken it.

Feeding a stripped value to a function that exists to preserve the marker is
self-defeating in a way nothing would report, so the scanner gives it its own
verdict, `BLINDS_PRESERVER`.

### Instance 4 — `tools=list(kwargs.get("tools") or [])`, fixed 2026-08-11

Found while checking whether the 8 `complete_with_tools` events could have come
from the ReAct path instead. Commit `ae2ec35b` ("Fix NarrowedTools regression and
complete multi-provider live smoke", 2026-08-11) had already repaired exactly
this shape in the provider dispatch:

```diff
-            tools=list(kwargs.get("tools") or []),
+            tools=kwargs.get("tools") or [],
```

Predates the burst and is not a cause of it, but it is the same mistake and it
matters for the count: this is not a one-off, it is a repeated pattern.

### The underlying trap

`NarrowedTools.as_openai_tools()` — the *sanctioned* helper for producing
provider payloads — returned a plain list. The one method whose entire job is
this conversion discarded the proof, so every correct caller was set up to fail.
That is the real design fault behind all four instances.

## Fix — at the source, not per call site

The first pass patched the two known call sites individually. That was the wrong
level: it leaves the trap in place for the next caller. Corrected 2026-09-02 on
Cesar's instruction.

| file | change |
|---|---|
| `narrowed_tools.py` | `as_openai_tools()` returns `NarrowedTools`, preserving `stats` and `source`. Still strips provider-illegal keys; serialises identically on the wire. |
| `narrowed_tools.py` | **New `openai_tools_payload(tools, *, where)`** — the single sanctioned conversion. Asserts and converts in one call, so a caller cannot get one without the other. |
| `unified_turn_reasoning_service.py` | Attach site now calls `openai_tools_payload` instead of hand-rolling the comprehension (instance 2). |
| `unified_turn_reasoning_service.py` | `_stable_tool_list(visible or [])`, no `list()` wrapper (instance 3). |
| `unified_turn_reasoning_service.py` | Unreachable `else` arm no longer strips (defensive; see caveats). |

### Why a single entry point rather than three correct call sites

Ordering matters: the conversion carries proof forward, so it may only run once
the guard has established the proof is real. Reversed, it would launder an
unnarrowed list into a narrowed-looking one and make the invariant decorative.

Leaving that ordering to each call site means getting it right *everywhere*, and
it was got wrong twice one line apart. `openai_tools_payload` makes the ordering
a property of the helper, so it cannot be got wrong at a call site at all.

What remains possible is bypassing the helper entirely — which is what the CI
scan covers.

### What cannot be fixed in code

`list(x)` returning a plain list is Python semantics; a `list` subclass cannot
override it, and no amount of API design prevents a future caller writing a bare
comprehension. So the second half of the fix is detection, not prevention:
`scripts/scan_narrowed_tools_strips.py`, enforced in CI by
`backend/tests/test_no_narrowed_tools_strips.py`.

The scan is intraprocedural and name-based — that is its honest bound. It tracks
names assigned from a known narrowing producer within one function and reports
rebuilds, classified as `ATTACH` (reaches a model attach site),
`BLINDS_PRESERVER` (defeats a preserve-branch), `REMARKED` (safe) or `MEASURE`
(sizing only). It does not follow values across function boundaries or through
containers. Current state: 0 ATTACH, 0 BLINDS_PRESERVER across 966 files.

## Why this went undetected for 109 events

The guard was tested. The helpers were tested. **The turn was not.** No test
asserted that `run_unified_turn_shadow` reaches the model with tools that still
pass the guard, so the one thing that broke was the one thing unobserved.

Mutation testing proved this was a live hole, not a hypothetical: with the
original round-trip defect reintroduced, the entire suite stayed green.

`backend/tests/services/test_unified_turn_attaches_narrowed_tools.py` now drives
the real function and inspects what reaches the provider dispatch.

## Verification

`python scripts/mutate_narrowed_tools_roundtrip.py` — **6 of 6 mutations caught**
(was 4 of 5 before the end-to-end harness existed):

| mutation | caught by |
|---|---|
| M1 `as_openai_tools` returns a plain list (the trap) | round-trip tests |
| M2 attach site hand-rolls the conversion (instance 2) | round-trip + provider tests |
| M3 `openai_tools_payload` converts without checking (laundering) | guard tests |
| M4 preserving branch removed (**the actual 08-13 defect**) | end-to-end harness |
| M5 guard downgraded to a no-op (the invariant itself) | guard tests |
| M6 strip before a preserver (instance 3) | CI scan test |

Full backend suite: `5052 passed`, 17 failures. All 17 confirmed **not caused by
this change**: 16 still fail with these source changes stashed, and the 17th
(`test_schedule_write_success_verification_returns_immediately`) is a timing
assertion that flaked under an 11-minute full-suite run and passes 3/3 in
isolation with the changes applied.

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
- **Instance 2: fixed and deployed, mutation-proven, still PARTIAL on live
  evidence.** See the section below for exactly what blocks a PASS.
- **Instances 3 and 4: no production events, and none expected.** Instance 3
  never reached the guard (both downstream branches re-mark); instance 4 was
  fixed before the burst. Neither is claimed as a live finding.
- **Regression coverage: closed**, mutation-proven at 6/6, plus a standing CI
  scan over 966 files.

## Instance 2: what a real live PASS actually requires

Attempted 2026-09-02 per Cesar's instruction to stop leaving it PARTIAL. Two
facts changed the plan, both worth recording.

**1. Prod already runs the fix.** `GET https://api.gravitre.app/health` reports
`git_sha: 7a0ab8d4`, the fix commit — Railway auto-deploys from `main`. So the
"prove it fires today" half can no longer be done against prod as it stands.
Doing it would mean **deliberately deploying the known defect to production** to
re-open the window.

**2. No model-provider keys in this environment.** `provider_tools_configured`
reports `openai=False, anthropic=False, gemini=False` locally (booleans only; no
secret material was read). The route used by the earlier accepted multi-provider
evidence — a local process against prod Supabase and real provider APIs, as in
`scripts/smoke-multi-provider-tool-live.py` — therefore cannot run here. Supabase
service access *is* present, so the isolated-org scaffolding works; only the
model calls are blocked.

`scripts/probe-unnarrowed-nonopenai-live.py` is written and ready; it currently
returns `CANNOT_RUN / anthropic_not_configured` and that result is recorded in
`docs/delivery/unnarrowed-nonopenai-live.json`.

### Safety assessment, as requested

Running one real Anthropic tool-carrying unified turn is **safe and genuinely
bounded**, on four independent grounds:

1. `run_unified_turn_shadow` makes one model call and **does not execute tools**
   (its own docstring). No connector write can occur by construction.
2. It runs in the isolated conversation org, which `conversation_write_guard`
   structurally prevents from ever being a customer org or Cesar's workspace.
3. The model is passed per-call. Prod routing, prod config and every
   customer-reachable agent are untouched.
4. The probe asserts the OpenAI tool path is **not** taken, so a pass cannot be
   manufactured by silently falling back to OpenAI.

The risk is not in running the probe. It is in what the "before" half now costs.

### The remaining choice

| Route | Gets a real "fires today"? | Cost |
|---|---|---|
| Provider key available to run the probe out-of-band | Yes — pre-fix and post-fix, both real | None to prod; needs an Anthropic (or Gemini) key |
| Deploy pre-fix code to prod, probe, redeploy | Yes, end-to-end through Railway | **Deliberate production regression window**, even if on a path with no customer traffic |
| Post-fix only, through prod HTTP | No — only proves clean | None; leaves "fires today" resting on the 8 historical events |

Not decided unilaterally: option 2 means shipping a known defect to production,
which is a call for Cesar, not for the agent. Recorded here rather than quietly
downgraded.

Worth stating plainly: the 8 events of 2026-08-12/13 at
`provider_tool_router.complete_with_tools` **are** real production evidence that
this defect fired on this path. What is missing is a *fresh* reproduction, not
proof that it was ever real.

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
