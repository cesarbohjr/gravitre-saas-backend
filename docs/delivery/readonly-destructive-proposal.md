# A read-only question stages a destructive write the user never asked for

**Status: PARTIALLY FIXED, live-confirmed at `51aa61e4`. Invented arguments are
gone; the fabricated action is still staged for approval. Safety-relevant, still
open.**
Deployed tip `db928881`. Evidence:
`docs/delivery/readonly-destructive-proposal-probe.json`.

First seen as a footnote during the dormant-`get_model_router` audit and initially
labeled "MSPs contamination, NOT REPRODUCED". Both halves of that label were
wrong. It is not contamination, and it reproduces every time.

## What happens

A user asks a read-only question in a **brand-new conversation**:

> Show me the most recent deals in our HubSpot pipeline with their amounts and
> close dates.

They get back:

> I still have **Create list** waiting for approval.
> Say **yes** to run it, **cancel** to drop it, or describe a change.

A destructive `hubspot.lists.create` is staged in `task_state.pending_task` with
`destructive: true`, `requires_approval: true`, and args
`{"name": "MSPs", "object_type_id": "0-1", "processing_type": "MANUAL"}`.

Three separate things are wrong:

1. A read request selects a **destructive create** action.
2. **Every argument is invented.** `inference_sources` marks all three
   `pack_common_default`; the user supplied none of them.
3. The user is told they *already have* this pending — wording that invites a
   `yes` for an action they never requested.

## Reproduction

`scripts/probe-readonly-destructive-proposal.py`, 10 live turns, each in a fresh
conversation, alternating a 6s cold gap with a 0.5s rapid follow-on:

| Case | Attempts | Destructive proposals |
|---|---|---|
| `original_deals_read` (exact phrasing) | 4 | **4** |
| `readonly_lists_mention` | 2 | 0 |
| `readonly_plural_contacts` | 2 | 0 |
| `readonly_pipeline_summary` | 2 | 0 |

**4/4 on the exact phrasing**, unaffected by timing. Narrow but deterministic.

A near-miss worth recording: `"…pipeline with amounts."` answers cleanly with a
real deals table and stages nothing, while `"…pipeline with their amounts and
close dates."` misfires every time. Whatever selects the action is sensitive to
wording in a way that has nothing to do with the user's intent.

## Root cause

Two candidate mechanisms were ruled out by direct test
(`backend/scripts/trace_readonly_to_list_create.py`):

- **`LIST_CREATE_INTENT` does not match** either phrasing. It requires a create
  verb plus `list|group|segment`; the query has neither. Not the regex path.
- **Pack defaults are not the selector.** `apply_pack_common_defaults` only fills
  args on a plan that has *already* chosen `hubspot.lists.create`. "MSPs" is
  `DEFAULT_HUBSPOT_LIST_NAME`, deliberate and unit-tested. It explains the
  *arguments*, not the *action*.
- The deterministic mapper produces **no plan at all** for this message.

What remains, and what the turn shape supports: the turn falls through to ReAct
(`read_tool_classical`), and **the ReAct model itself selects the
`hubspot_lists_create` tool**. `react_write_gate` then converts that tool call
into a plan, `apply_pack_common_defaults` fills every missing argument, and the
result is staged for approval as though the user had asked for it.

So the fabrication is model tool-selection, and the surrounding pipeline
faithfully dresses it up as a legitimate, fully-specified, approval-ready
destructive write.

## The mismatch net does not cover this

Tested against the claim directly rather than assumed.
`assert_plan_matches_binding` compares the **approved binding** with the
**about-to-execute plan**: `bound_tool_name`, `bound_invoke_action`,
`bound_integration`, `bound_args_digest`.

In this bug all four agree. The staged record already carries
`bound_args_digest: 3d1d1544d2a38847953d4b5d246ed255cc8758503465a90752a746bd3891f438`
matching its own args. A user typing `yes` approves `hubspot.lists.create` and
`hubspot.lists.create` is exactly what executes.

**`APPROVAL_ACTION_MISMATCH` would not fire, and the write would go through.**
That net defends a different failure — approve X, execute Y. This one is propose
something never requested, then execute precisely that. The binding is perfectly
self-consistent; it is the proposal that is fabricated. No guard currently sits
between "model picked a destructive tool" and "user is asked to approve it".

Not live-tested to completion by design: confirming execution end-to-end would
create a real list in a real HubSpot account. The static analysis above is
decisive on its own, and a destructive vendor write is not something to trigger
without authorization.

## Why it matters more than its 4/10 rate suggests

The only thing standing between a fabricated destructive action and a real
vendor write is the user reading carefully — and the wording actively works
against that by asserting the action was already pending. A user who trusts the
system and replies `yes` gets a HubSpot list they never asked for.

It also explains the false "stale approval hold" report earlier in this program.
That was this bug, seen through a probe that opened a new conversation per turn.

## Fix applied — withhold invented arguments (option 1, authorized)

Authorized choice: refuse to fabricate arguments for a destructive action the
user never requested. Implemented in `apply_pack_common_defaults`, the one
chokepoint all four staging paths already share (governed chat, ReAct write gate,
unified-turn reasoning, orchestration), so this is not a single-path patch.

The condition is deliberately two-part, because either half alone would be wrong:

```python
if plan.destructive and not LIST_CREATE_INTENT.search(message):
    return plan  # leave the slots empty
```

- **`destructive` only, never `requires_approval`.** Many benign actions require
  approval; gating on that would suppress defaults far beyond this defect and
  broke `apollo.lists.add` / `clay.crm.sync` in the existing suite.
- **The create-intent check is what preserves legitimate flows.** A real
  omit-name create ("Create a HubSpot static list") is *also* fully
  default-filled, so a pure "all args are pack defaults" rule would have blocked
  it. It says "create", `LIST_CREATE_INTENT` matches, and defaults still apply.

With the slots left empty the plan fails the required-parameter check instead of
arriving as a one-word-from-execution approval prompt. `is_unrequested_destructive_plan()`
is exposed alongside it for callers that need the predicate directly.

**Evidence:**

- `backend/tests/services/test_unrequested_destructive_plan_guard.py` — 5 tests,
  asserting both directions: the read-only message gets no invented args, and a
  genuine create request still gets all three.
- **Mutation-proven.** Replacing the guard condition with `if False:` restores
  the exact fabrication (`{'name': 'MSPs', 'object_type_id': '0-1',
  'processing_type': 'MANUAL'}`) and fails the test. The guard is load-bearing.
- **No regressions:** 75 passed across `test_pack_common_intent_defaults`,
  `test_connector_action_workflows`, `test_chat_connector_execution`,
  `test_approval_action_binding`, plus the new file.

### Live result: the argument half is fixed, the staging half is not

Re-run in production at tip `51aa61e4`. **Half of this worked and half of my
reasoning about it was wrong**, so both are recorded.

Fabricated arguments are gone, confirmed by reading the staged record directly:

| | before (`db928881`) | after (`51aa61e4`) |
|---|---|---|
| `args` | `{"name": "MSPs", "object_type_id": "0-1", "processing_type": "MANUAL"}` | `{}` |
| `inferred_fields` | `["name","processing_type","object_type_id"]` | `[]` |
| `inference_sources` | 3 × `pack_common_default` | `{}` |

**But the fabricated action is still staged, and the probe is still 4/4.** The
user still gets:

> I still have **Create list** waiting for approval. Say **yes** to run it…

My stated prediction above — that empty slots would make the plan "fail the
required-parameter check instead of arriving as a one-word-from-execution
approval prompt" — **was wrong.** It stages `awaiting_confirm` with `args: {}`
regardless. Something downstream of the defaults does not treat missing required
arguments as disqualifying.

Honest status:

- **Fixed, live-confirmed:** no invented values reach a destructive proposal. A
  `yes` can no longer create a wrongly-named `MSPs` list; it would attempt a
  nameless create that vendor validation should reject. Real risk reduction.
- **Not fixed:** a read-only question still fabricates a destructive *action* and
  still invites approval for it. The root cause — ReAct selecting
  `hubspot_lists_create` for a read request — is untouched, and the guard was
  never aimed at it.

The remaining work is the staging decision, not the arguments: either the
required-param check must refuse to stage a destructive plan with no arguments,
or the ReAct-selected destructive tool must be gated on read-classified turns
(the option deferred earlier). Worth noting the unit tests for the guard were
green *and* mutation-proven while the live defect persisted — they proved the
guard does what it says, not that it closes the defect.

## Options considered and not taken

## Options considered and not taken

Deliberately left unfixed pending a decision, because the plausible fixes differ
in blast radius:

- Refuse to stage a destructive write whose arguments are **entirely**
  pack-default inferred (no user-supplied value anywhere). Narrow, targeted at
  the fabrication signature, and `inference_sources` already carries the data.
- Gate ReAct-selected destructive tools on read-classified turns.
- Fix the wording so a first-mention hold never claims to be pre-existing. Does
  not address the fabrication, but removes the misleading `yes` invitation, and
  it is what made this so hard to see.
