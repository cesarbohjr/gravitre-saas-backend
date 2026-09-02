# `outcome_error` fallthrough — real trace (142 of 502 turns / 30d)

Recorded as "~28% of fallthrough turns failing outright", flagged as a live
quality problem deserving its own trace. The trace substantially **downgrades**
the finding, and the reason is worth stating plainly: the metric was measuring
this audit's own probe traffic.

## What the reason actually means

`unified_turn_reasoning_service.py:1667`:

```python
if result.outcome_kind in {"skipped", "error"}:
    _mark_live_fallthrough(result, f"outcome_{result.outcome_kind}")
```

A fallthrough **continues** to the classical path. `outcome_error` means the
LIVE reasoning attempt errored and classical took over — a real defect in the
LIVE path, but only a user-visible failure if classical then also failed.

## Who generated these turns

`backend/scripts/probe_outcome_error_severity.py`:

| traffic source | events |
|---|---|
| this audit's own probe orgs (`f07e57c0`, `00000000`) | **140** |
| real customer orgs (`cbbf993b`) | **2** |

The 28% figure is almost entirely self-inflicted by the verification scripts
written during this program. Any future reading of this metric has to filter by
org first — the audit is polluting the telemetry it measures.

## What was erroring

| class | probe | real | active? |
|---|---|---|---|
| `unnarrowed_tool_attach_blocked` (internal invariant guard) | 119 | 0 | **No** — only 2026-08-12/13, none since |
| `400 invalid tool_choice` (API contract bug) | 14 | 1 | **Yes** — 08-12, 08-14, 08-31, 09-01 |
| `429 provider rate limit` (gpt-4.1 TPM) | 7 | 0 | environmental |
| `404 model \`default\` does not exist` | 0 | 1 | one-off, 08-12 |

Zero events had an empty error field, so nothing here is unattributable.

Latency burned on a failed LIVE attempt before restarting on classical:
**p50 831ms, p95 2030ms, max 6923ms**.

## Did users still get answers

Of 60 sampled conversations, 54 received an assistant reply afterwards (90%
recovery via the classical path). Of the 6 with no reply, **all 6 were probe
orgs and none were real customers**.

So: **0 real-customer turns were left unanswered.** The "failing outright"
framing does not hold.

## The one real, current defect — fixed

`400 invalid tool_choice` is genuine, was still firing on 2026-09-01, and hit a
real customer org once.

`_complete_openai_with_tools` unconditionally sent both `tools` and
`tool_choice`. OpenAI rejects `tool_choice` when no tools are attached, and both
callers can legitimately arrive with an empty list:

- `unified_turn_reasoning_service.py:875` sets `tool_choice="none"` for
  conversational turns while only attaching `tools` when it has some
- `react_engine.py:769` passes `tools if tools else []`

### First attempt was inert — fifth "one layer too low", and mine

Fixed first at `_complete_openai_with_tools` in `provider_tool_router`, on the
reasoning that the adapter is the single place the vendor contract is violated.
Deployed at `56b4f1a1`. The live re-run produced **4 more 400s**.

`unified_turn_reasoning_service.py:249` routes OpenAI models straight past that
adapter:

```python
provider = resolve_provider_for_model(model)
if provider == "openai":
    return await _complete_unified_turn_stream(openai_client, kwargs=kwargs, ...)
```

`_complete_unified_turn_stream` calls
`openai_client.chat.completions.create(**stream_kwargs)` directly and never
touches `provider_tool_router`. Every observed 400 was on `gpt-4o-mini` — an
OpenAI model — so the adapter fix could not have covered a single one of them.
It does still cover `react_engine` and the non-OpenAI providers, so it was kept
rather than reverted.

The unit tests for the first attempt were green. Only the production re-run
distinguished "the guard works" from "the defect is closed" — the same pattern
this program has now found six times, including twice in my own work today.

### The fix that worked

Two places, deliberately:

- `_complete_unified_turn_stream` drops both keys when there are no tools. This
  is the boundary that issues the request, so a future caller cannot
  reintroduce it.
- the kwargs construction at `:872` now sets `tool_choice` only alongside
  `tools`, which is the semantically correct form.

9 tests, and the streaming guard is mutation-proven: removing it fails 2 of
them. Negative controls confirm tool calling still works when tools *are*
present.

### Live PASS at `e370df75`

Same probe, same 6 conversational turns, against the deployed tip:

| | `56b4f1a1` (adapter fix only) | `e370df75` (streaming fix) |
|---|---|---|
| turns replied | 6/6 | 6/6 |
| fallthrough events | 4 | **0** |
| `tool_choice` 400s | 4 | **0** |

The reply quality changed visibly too, which is the user-facing part of this
defect. At `56b4f1a1` the first turn returned:

> `"Got it — updated to thanks, that actually helped a lot. Continuing with that."`

— the classical path mangling a conversational turn after the LIVE attempt
died. At `e370df75` the same input returns:

> `"Glad to hear that! If there's anything else on your mind, just let me know."`

So the 400 was not merely a logged error being recovered from. It was pushing
conversational turns onto a path that answered them badly.

## Left open, honestly

- **`unnarrowed_tool_attach_blocked` (119 events).** Gravitre's own invariant
  guard rejecting unnarrowed tools in the LIVE path. It is a real internal
  defect, but it fired on two days three weeks ago, has not recurred, and never
  touched a real org. Not chased further on that evidence; if it returns, the
  audit event now carries the exact `where=` and `count=` needed to locate it.
- **`404 model \`default\``.** One real-org event on 08-12, no recurrence. No
  code path was found that passes the literal string `"default"` as a model
  name — every `or "default"` in the codebase is an environment or segment
  default, not a model. Reported as an unexplained one-off rather than given an
  invented fix.
- **429 rate limits** on `gpt-4.1` TPM are environmental, not a code defect.

## Honest verdict

`outcome_error` is **not** the ~28% live quality incident it appeared to be.
Real-customer impact over 30 days is 2 turns, both answered. The dominant
contributor is a historical internal-guard burst confined to the audit's own
probe traffic.

But the trace was still worth doing, and not because of the headline number.
The `tool_choice` 400 inside it was real, still active on 2026-09-01, and was
degrading conversational replies rather than merely being logged — visible in
the before/after above. It is now fixed and live-proven at `e370df75`.

The finding that survives is smaller and more specific than "a quarter of turns
are failing": one vendor-contract bug on the conversational streaming path,
closed, plus a standing warning that this audit's own probe traffic dominates
this metric and must be filtered out of any future reading of it.
