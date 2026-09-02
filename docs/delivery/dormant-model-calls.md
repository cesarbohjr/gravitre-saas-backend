# Dormant model calls ? silent no-ops in production

Standing record. Append-only; do not overwrite earlier sections.

A zero-argument factory called with an argument raises `TypeError` **before the
factory body runs**. Wrapped in `except Exception`, that becomes a silent no-op:
the capability is gone, nothing is logged above `debug`, and every test still
passes because the caller's fallback returns a valid-looking value.

Two confirmed instances were found by reading production traces, not by any
test:

- `verification_critic_service` ? the **mandatory** critic pass, degrading to
  `mandatory_critic_error` on every turn (fixed in `ccc98167`).
- `unified_turn_knowledge_context` ? customer RAG removed from the replan loop
  entirely. Live artifact at tip `ccc98167` shows
  `org_rag_error = "get_rag_service() takes 0 positional arguments but 1 was
  given"` on both evidence-bearing turns. The loop reported `org_rag` in
  `sources_tried` while that source had thrown instantly.

## Deferred, low priority ? `_classify_error` mislabels internal bugs as user error

Raised 2026-09-01 during the HubSpot search investigation. **Not urgent, real,
and deliberately not folded into the dormant-call work.** Recorded here so it
is not lost; it deserves its own audit once the twelve sites are closed.

`tool_service._classify_error` is the connector-wide fallthrough for tool
exceptions. Transport faults and timeouts were being labelled
`validation_error` and were fixed at that chokepoint; see
`docs/delivery/hubspot-search-validation-dead-end.md`. What remains is the
broader case: an arbitrary internal exception ? a `KeyError` in Gravitre's own
code, for instance ? still classifies as `validation_error`, so **our bug is
presented to the user as their input being wrong**, across all 727 actions.

Why it was not fixed in that pass: separating "our fault" from "your input" for
arbitrary exceptions requires auditing what every caller actually raises, per
connector. Changing the default without that audit would alter user-facing
messages catalog-wide with no way to verify the result, which is the kind of
unverified bulk change this program has repeatedly found to be wrong.

Scope when picked up: enumerate the real exception types reaching
`_classify_error` from each connector, decide the correct classification per
type, and keep `validation_error` for genuine user-input faults only.

## Phase 0 ? exhaustive inventory (2026-08-31)

Method: AST scan of all 318 zero-argument module-level factories in
`backend/app`, cross-checked against imported names so that same-named methods
(`self._load`, `trace.get_tracer`) are not miscounted.
Scanner: `backend/scripts/scan_arity_mismatch_and_silent_swallow.py`.

**Confirmed count: 12, not 10.** The two additions are both `get_rag_service`,
which the original count missed because it looked only for `get_model_router`.

Dormancy is certain by construction rather than inferred: a positional-argument
count mismatch is evaluated before the callee runs, so these calls can never
intermittently succeed. What varies is reachability, not outcome.

Runtime proof of the fallback each site has actually been returning:
`backend/scripts/probe_dormant_model_calls.py` ?
`docs/delivery/dormant-model-call-runtime-probe.json`.

### Severity ranking

Ordered by correctness ? safety/governance ? user-facing quality.

| # | Site | What has been silently absent | Observed fallback | Severity |
|---|---|---|---|---|
| 1 | `answer_validator.py:74` | Grounding/hallucination check against retrieved context | `{is_valid: True, issues: [], requires_human: False}` ? **fails OPEN** | ~~Critical ? correctness~~ ? **corrected to Low: dead code.** See Phase B ? measured as never executing on live traffic (0 audits against 464 fallthroughs / 1454 turns in 30d), so nothing was being falsely certified |
| 2 | `unified_turn_knowledge_context.py:201` | Customer RAG retrieval in the replan loop | `org_rag_error`, 0 chunks | **Critical ? correctness.** Org's own documents excluded from evidence |
| 3 | `agent_intelligence.py:931` | Regeneration of an ungrounded answer | Never reached ? gated behind site 1 failing open | **High ? correctness**, masked by site 1 |
| 4 | `schema_param_extractor.py:319` | Model extraction of connector action arguments | Heuristic-only args | **High ? touches write actions.** Missing args ? failed or under-specified writes |
| 5 | `pending_reply_classifier.py:500` | Comprehending approve/reject replies regex missed | `"ambiguous"` | **High ? governance-adjacent.** Approval replies collapse to a re-ask |
| 6 | `conversation_turn_controller.py:273` | Comprehending continue/modify/cancel on a pending plan | `"unclear"` | **High ? governance-adjacent** |
| 7 | `query_rewriter.py:52` | Resolving pronouns into standalone retrieval queries | Original query unchanged | **Medium ? retrieval quality.** Follow-ups retrieve on the raw pronoun |
| 8 | `conversational_turn_gate.py:240` | Distinguishing small talk from casually-phrased data asks | Heuristics decide every turn, `used_model=False` | **Medium ? quality/latency** |
| 9 | `domain_intelligence_service.py:208` | Model-based domain classification | `source: "rules"` | **Medium ? routing quality** |
| 10 | `contextual_understanding_service.py:225` | Goal + constraint extraction | `{}` ? always empty | **Medium ? quality** |
| 11 | `clarification_engine.py:769` | Polishing clarifying questions | Unpolished draft | **Low ? cosmetic** |
| 12 | `cache_warming_scheduler.py:48` | Warming embedding/retrieval caches | Throws per org; `queries_warmed=0` | **Low ? performance only.** Already visible at `warning` |

Honest correction recorded: an earlier reading of site 8 assumed the fallback
was uniformly `task_shaped`. The runtime probe shows a heuristic layer sits in
front, correctly classifying both an obvious greeting and an obvious data ask
without the model. The dormant call is the *ambiguous middle*, which is a
narrower impact than first stated.

## Phase 1 ? root cause and structural guard

### Root cause: NOT DETERMINABLE from available history

This repository's history is squashed ? all 573 commits trace to `9b1d748c`,
and `model_router.py`, `answer_validator.py` and the rest each show exactly one
commit. `git log -S` finds no prior settings-accepting form of
`get_model_router` because no prior form exists in this history at all.

**The drift predates the available record.** No story about when or why the
signatures diverged is offered here, because none can be evidenced.

What *is* structurally established: `ModelRouter.__init__(settings=None)` does
accept settings, while the singleton accessor `get_model_router()` does not and
**cannot honor them** ? the instance is built once and reused, so a
per-call `settings` argument would be silently discarded even if the signature
accepted it. Widening the factory would therefore encode a lie. The correct fix
is to keep it zero-argument and remove the argument at each call site.

### Structural guard ? `backend/tests/test_no_dormant_model_calls.py`

Two rules, enforced in CI:

1. **No zero-arg factory may be called with arguments.** Held against a
   `KNOWN_DORMANT` baseline that may only shrink: a new offender fails
   immediately, and a fixed site left in the list also fails, so the baseline
   cannot rot.
2. **A handler wrapping a model call may not swallow while logging below
   WARNING.** Handlers that re-raise are exempt, since translating an error into
   a typed exception surfaces it by definition.

Mutation-proven: injecting `get_model_router(1)` into an unrelated service makes
rule 1 fail with that exact path; removing the injection restores green.

Rule 2 found a **wider class than the 12 arity sites ? 17 handlers** hiding
model failures below WARNING, including three logging nothing at all. All 17
raised to `warning` in this pass. Two required new log statements
(`consensus_engine`, `generative_agent_coordinator`); the latter turned out to
call `ModelRouter(self.settings)` correctly and had only the silent-`pass`
problem, not an arity bug.

This change is observability-only: no control flow, fallback values, or model
behavior altered.

## Phase 2 ? site 1 + 3 (grounding validator and regeneration)

Fixed together, not as a batch of convenience: the validator failing open is
precisely what made the regeneration `TypeError` unreachable. Fixing the
validator alone would have converted a silent no-op into a **hard turn failure**,
because `agent_intelligence.py:972` calls `_regenerate_grounded_answer` outside
any `try`. Repairing one without the other leaves production strictly worse.

Changes:

- `answer_validator.py:74` ? `get_model_router()`.
- `agent_intelligence.py:931` ? `get_model_router()`, plus a handler so a
  regeneration failure returns `""` and lands on the caller's existing
  `SAFE_FALLBACK` branch rather than raising. This path has never executed in
  production, so it is newly exposed and should degrade, not 500.

### Severity correction (honest)

The Phase 0 table called this "every answer declared grounded". That overstates
it. `validation_enabled_for_mode` gates the check: it requires
`validation_enabled`, and by default covers only `standard` and `reasoning`
modes (`speed_priority` narrows it further to `reasoning`/`agent`). The accurate
claim is **every _validated_ answer was declared grounded without a check** ? a
smaller blast radius than first written, still a failed correctness gate.

### Before baseline ? `docs/delivery/validation-stage-latency.json`

`ai_pipeline_latency` where `stage_name='validation'`, 30-day window, captured
before deploy: **1 sample, 0 ms**. A swallowed `TypeError` returns in about a
millisecond; a real model call does not, so 0 ms is consistent with the no-op.

Two honest limits on that figure. n=1 is thin. And the latency row is only
written when `message_id` is present, so 1 is a **lower bound on invocations,
not a count of them** ? it does not establish how often the validator was
reached, only that where it was recorded, it took no measurable time.

### After ? live run at deployed tip `9ca96dc2`: PARTIAL, execution NOT CONFIRMED

Artifact: `docs/delivery/grounding-validator-live.json`.

Two standard-mode turns ran against the isolated conversation org at the
deployed tip. Both returned 200 with no stream errors. **Zero validation-stage
rows were written**, so the intended discriminator produced nothing to read.

This is reported as NOT CONFIRMED rather than as a failure, because the evidence
does not distinguish the two possibilities:

- The validator is on this path. `/api/assistant/chat` calls
  `intelligence.execute_task_streaming`, which reaches
  `_finalize_assistant_response` at `agent_intelligence.py:3463`. Defaults are
  `validation_enabled=True` and `performance_mode="balanced"`, which covers
  `standard`. The org has no `org_intelligence_engine_settings` row, so defaults
  apply. On that reading the validator ran and simply was not recorded.
- The latency row is gated on `message_id` being truthy. This org's history
  contains **only** `generation` rows and has never contained a `validation`
  row, which is consistent with `message_id` being absent on this path ? in
  which case no validation row could ever appear, before or after the fix.

So the chosen signal cannot prove execution here, and no claim of live execution
is made. What is established: the fix is deployed at `9ca96dc2`, and locally the
call now reaches the router (`MODEL_CALL_START` emitted, failing only for want
of provider keys) where previously it raised `TypeError` before getting there.

Next probe options, none yet run: read Railway logs for `MODEL_CALL_START`
with `task_type=classification` or the newly-raised
`answer validation skipped` warning during a live turn; or add a temporary
audit event recording the validation verdict, which would also give the
before/after quality comparison Phase 2 asks for.

**Status: site 1+3 SHIPPED and DEPLOYED, live execution NOT CONFIRMED.**

### Second live run at `9080bc87` ? root of the non-confirmation found

An `answer.grounding.validated` audit event was added so execution could be
observed without depending on `message_id`. Its decisive field is
`confidenceSource`: `"model"` means the assessor genuinely judged, `"heuristic"`
means the call fell through to the permissive default.

The re-run produced **zero such events**, and the reason is structural, not a
missing signal. Both turns were handled by `unified_turn.live.completed`:

```
grounding_pressure  d5a32ae1?  unified_turn.live.completed  2026-09-01T00:07:38Z
grounded_control    c3199c6d?  unified_turn.live.completed  2026-09-01T00:07:53Z
```

The grounding validator is called from
`agent_intelligence._finalize_assistant_response`, which sits on the ReAct
finalize path. Production chat traffic takes the **unified turn** path and only
reaches ReAct on `unified_turn.live.fallthrough` ? an event that does appear in
this org's history, but did not fire on either of these turns.

### Consequence for the Phase 0 severity ranking (second correction)

Site 1 was ranked **Critical ? every validated answer declared grounded without
a check**. That ranking assumed the validator sits on the main answer path. It
does not. Its real reachability is narrower still: validated modes
(`standard`/`reasoning`) **and** a unified-turn fallthrough.

This does not make the fix wrong ? a grounding gate that fails open is a real
defect and is now repaired. But the honest reading is that the capability was
absent from a **narrower slice of traffic** than the original ranking implied,
and that a separate, larger question is now open: whether the grounding check
should be on the unified turn path at all, given that is where real traffic
goes. That is a design question, not a signature bug, and is not decided here.

Live execution of site 1+3 therefore remains **NOT CONFIRMED**, with the reason
now known: the proof requires a turn that reaches ReAct finalize, which these
did not.

### Third attempt ? fallthrough forced, blocked by a stale approval hold

A connector-read query did force the intended route:

```
forced_react_fallthrough  actions=[pending_reply.classified,
                                   unified_turn.live.fallthrough]
                          reached_react=True  reason=read_tool_classical
```

Still zero grounding audits, because that turn was intercepted by a pending
approval ? `"I still have **Create list** waiting for approval."` ? which
short-circuits before answer generation.

I read that as a stale, org-scoped hold surviving `cancel`, and recorded it as a
separate blocking defect. **That diagnosis was wrong.** See the retraction below;
it is left in place rather than edited out because the way it went wrong is the
useful part.

**Site 1+3 status at this point: SHIPPED and DEPLOYED at `9ca96dc2`
(observability at `9080bc87`), live execution NOT CONFIRMED**, one real blocker:
the validator is not on the unified-turn path real traffic uses.

### Retraction ? there is no stale approval hold

Investigated as its own task and **NOT REPRODUCIBLE**. Evidence, at tip
`db928881`:

- `task_state` is a column on the `conversations` row, so a hold is
  conversation-scoped by construction. The claim that it is org-scoped was an
  assumption, never checked.
- Reading the four conversations from the failing run directly: only the
  `forced_react_fallthrough` one carried a `pending_task`, and that conversation
  was **created 11 seconds earlier, by that same run**. The other three were
  `None`.
- `scripts/verify-pending-cancel-clears-hold.py` runs the sequence the report
  actually describes ? one conversation, hold created, `cancel` in the **same**
  conversation, then a genuinely new conversation. **PASS on all four checks:**
  the hold was created (`Create list status=awaiting_confirm`), `cancel` cleared
  it in the database, the follow-up turn showed no hold prompt, and the fresh
  conversation started clean.

Two compounding mistakes produced the false report. The probe opened a new
conversation per turn, so `cancel` landed on a conversation that never had a hold
while a later turn created one of its own ? and `format_pending_meta_answer`
phrases a hold as `"I **still** have X waiting for approval"` even on first
mention, so a brand-new hold reads like a surviving one. Neither the code nor the
data ever said the hold survived; the prose did, and I believed it.

Guarded by `backend/tests/services/test_pending_hold_does_not_survive_cancel.py`
(10 tests). The terminal-clearing half is mutation-proven: disabling the
`pending_status in {"completed","failed","cancelled"}` branch in
`conversation_turn_controller` fails 3 of them.

### Phase B ? the validator is not on the live answer path, and site 1's severity was overstated

With the phantom blocker gone, the reachability question was asked directly
instead. `scripts/probe-grounding-validator-reachable-shape.py` swept four turn
shapes chosen to avoid the early returns that pass `validation=None` ? a factual
knowledge question, `reasoning` mode, a deliberate grounding-pressure question,
and a multi-hop business question.

**All four were served by "Unified turn live". `validation` was `null` in every
SSE stream, and zero `answer.grounding.validated` events were written.** The
audit code was confirmed live for these runs (`9080bc87` is an ancestor of the
deployed `db928881`), so the zero is a real measurement, not missing
instrumentation.

Traffic split from `audit_events`, via
`backend/scripts/probe_validator_reachability.py`:

| Window | Unified completed | Fallthrough | Fallthrough rate | Grounding audits |
|---|---|---|---|---|
| 6h | 35 | 11 | 23.9% | 0 |
| 24h | 38 | 13 | 25.5% | 0 |
| 7d | 130 | 53 | 29.0% | 0 |
| 30d | 990 | 464 | 31.9% | 0 |

This corrects an earlier claim of mine in two directions at once. I called this
"a fallthrough path most production chat traffic never takes" ? wrong, about a
third of turns fall through. But fallthrough does **not** mean reaching ReAct
finalize: the 30-day reasons are `pending_family_classical_resume` (144),
`outcome_error` (142), `defer_classical_tool_sse` (141), and
`read_tool_classical` (37), and the branches that serve them return before the
finalize call, several passing `validation=None` explicitly. 464 fallthroughs
produced 0 grounding audits.

**Site 1's severity was overstated and is corrected here.** The Phase 0 table
calls it "Critical ? correctness. Every answer declared grounded with no check."
That framing assumed the validator ran and rubber-stamped answers. It did not run
at all on any observed live path, so nothing was being falsely certified. The
honest finding is *dead code*, not a defeated safety check.

Nor is the live path ungrounded. Both pressure questions were refused honestly by
the unified turn on its own: *"I don't have enough information to substantiate an
exact guaranteed number from the internal documents you provided."* Grounding
discipline exists where traffic actually flows ? it simply is not this validator.

**Site 1+3 status: signature fix correct, SHIPPED, DEPLOYED, and NOT EXECUTING,
because the path it lives on is not reached by live traffic.** The remaining
question is a design one ? whether the unified turn should call this validator,
or whether it should be retired in favor of the grounding behavior the unified
turn already has. That is a product decision, not a signature bug, and is not
decided here.

## Phase 2 ? site 4, `schema_param_extractor.py:319` (PARTIAL)

Taken next as the highest-severity remaining site, and because it turned out to
be directly relevant to the fabricated-write finding: this extractor's own prompt
says *"Return ONLY keys that have a confident value. Do not invent ids."* While
it was dormant, the only things filling connector arguments were regex heuristics
and pack defaults ? precisely the path that invents
`{"name": "MSPs", ...}` in
[`readonly-destructive-proposal.md`](./readonly-destructive-proposal.md).

Fix: `get_model_router(settings or get_settings())` ? `get_model_router()`.

**Proven** (`backend/scripts/probe_site4_schema_param_extractor.py`), with the
pre-fix call shape re-created deliberately so the result cannot be mistaken for
something that always worked:

```
get_model_router(settings) -> TypeError: takes 0 positional arguments but 1 was given
get_model_router()         -> OK ? ModelRouter
```

**Not proven: that the model call adds arguments heuristics miss.** Two messages
hiding the list name in prose ("we've been calling the segment Northeast
Renewals") returned `{}` from both the heuristic and the model-backed path. That
is a limitation of the probe, not evidence about the fix: with no connector schema
registered in a bare local context, `_schema_field_keys` returns no fields, so
`required_missing` is empty and the function returns before reaching the model at
all.

### Resolved 2026-09-01 ? INCONCLUSIVE superseded by PASS

The INCONCLUSIVE above came from a probe limitation, not from the fix. Correcting
the probe resolved it. `backend/scripts/probe_schema_param_extractor_live.py`
first enumerates the real catalog for actions that genuinely have a workflow
schema with required fields, then constructs a message that leaves a required
field empty, which is what the earlier probe never achieved.

The dormancy claim is about control flow ? was the router entered ? so it is
decidable without AI credentials. `probe_schema_param_extractor_before_after.py`
runs the real extractor twice on the same input, restoring the original buggy
call for the first pass (`docs/delivery/schema-param-extractor-before-after.json`):

| | Router entered (`MODEL_CALL_START`) | Handler logged |
|---|---|---|
| before | **no** | `get_model_router() takes 0 positional arguments but 1 was given` |
| after | **yes** | `All AI providers failed (?not-configured)` ? local env only |

Status: **PASS on the dormancy defect.** The call reached the router on a real
invocation; before the fix it could not, and the failure was invisible.

Still open, and deliberately not rounded up: whether the model then contributes
arguments the heuristics miss. That is a capability question, not a dormancy
one, and it is unmeasurable in this environment ? no AI provider is configured
locally (openai, anthropic and gemini all report unavailable), so the call
reaches the router and can never receive a completion. Production only.

Recorded while probing, not fixed: for a vague message the heuristic pass fills
`hubspot.contacts.create`'s `firstname` *and* `lastname` with the entire user
message. Same argument-invention pathology as
[`readonly-destructive-proposal.md`](./readonly-destructive-proposal.md).

## Phase 2 ? site 5, `pending_reply_classifier.py:500` (PASS on dormancy)

Fix: `get_model_router(settings or get_settings())` ? `get_model_router()`.

What was silently absent: `classify_pending_reply` runs a regex fast path first
and only calls the model when that returns `None`. With the call dormant, every
reply the regex could not classify returned `"ambiguous"`, so the assistant
re-asked instead of reading the conversation. It **failed safe** ? asking rather
than guessing an approve or reject ? which is exactly why it was never noticed
on a governance-adjacent path.

Before/after on the same input, buggy call restored for the first pass
(`backend/scripts/probe_pending_reply_classifier_before_after.py`,
`docs/delivery/pending-reply-classifier-before-after.json`). The reply used is
*"hold off on that for now, I want to check the numbers with finance first"* ?
against a real `awaiting_confirm` hold, with the regex fast path confirmed
returning `None`, so comprehension is the only route to a correct label:

| | Regex fast path | Router entered | TypeError | Intent returned |
|---|---|---|---|---|
| before | `None` | **no** | yes, swallowed at WARNING | `ambiguous` |
| after | `None` | **yes** | no | `ambiguous` (no AI provider configured locally) |

Status: **PASS on the dormancy defect** ? the classifier now reaches the model
router on a reply the regex cannot handle.

### Live production proof ? PASS

`scripts/verify-pending-reply-classifier-live.py` against deployed tip
**dd218e899e08f34544fc70faba5cafc129f08c15**, org
`f07e57c0-1501-4000-8000-c04e57a00001`
(`docs/delivery/pending-reply-classifier-live.json`).

Each scenario stages a real `hubspot.lists.create` approval hold, then replies
with a phrasing verified to return `None` from `classify_pending_reply_fast`
(`backend/scripts/scratch_pick_regex_bypassing_replies.py`), so the model is the
only thing that can label it:

| Reply | Outcome | Hold |
|---|---|---|
| "hold off on that for now, I want to check the numbers with finance first" | "Cancelled the pending plan. What should we do instead?" | released |
| "let me run that past finance before we commit to it" | asked for a specific target | retained |
| "not yet, the board meeting is Thursday and I want their read first" | "Cancelled the pending plan. What should we do instead?" | released |

- **0 `lists.create` invocations** ? no soft deferral was read as approval. This
  was the check that mattered most; comprehending a deferral as a yes would be
  far worse than re-asking.
- **0 generic "waiting for your approval" re-asks** ? the signature of the
  dormant `"ambiguous"` path did not appear once.
- 2 of 3 released the hold correctly.

Honest on the third: "let me run that past finance before we commit to it" was
not treated as a deferral but as an incomplete instruction, and the reply asked
for a target. Safe, and not the dormant re-ask, but not right either. That is a
classification-quality wobble on a reply whose only signal is *"before we
commit"*, not a return of the dormancy bug. Recorded, not rounded up to a clean
3/3.

Also noticed while selecting phrasings, not fixed: the regex fast path labels
*"what exactly is that going to do to our existing lists?"* as `unrelated` when
it is plainly `meta_clarify`. Because the fast path returns a confident answer,
the model never gets to correct it ? a wrong regex verdict is more harmful than
no verdict, and this one predates the dormancy fix.

Baseline: `pending_reply_classifier.py:500` removed from `KNOWN_DORMANT`, guard
test green (2 passed). Five of twelve sites now closed.

### Superseded ? the "unreproduced" observation below is now REPRODUCED

Investigated properly in
[`readonly-destructive-proposal.md`](./readonly-destructive-proposal.md).
**4/4 on the exact phrasing**, deterministic, safety-relevant, unfixed. It is not
contamination: "MSPs" is `DEFAULT_HUBSPOT_LIST_NAME`, a deliberate pack default,
and the real defect is that ReAct selects a destructive create tool for a
read-only request. `APPROVAL_ACTION_MISMATCH` was tested against the claim and
**would not catch it** ? proposed and executed actions are identical.

This also explains the false stale-hold report above: same bug, seen through a
probe that opened a new conversation per turn.

The original, now-superseded note is kept below unedited.

### Unreproduced observation, kept honest

In the failing run, a **read-only** request ("show me the most recent deals")
produced a pending **destructive** write: `hubspot_lists_create`, name `"MSPs"`,
`destructive: true`, `risk_level: high`. `"MSPs"` matches earlier MSP
marketplace testing, so this looks like context contamination rather than
anything the user asked for. On re-run the same query answered normally with a
real deals table and created no pending at all.

Labeled **NOT REPRODUCED**, not fixed and not dismissed. It is an
action-resolution concern adjacent to the `APPROVAL_ACTION_MISMATCH` safety net,
not a dormant-call issue, and it should not be folded into this task. Worth
noting that the mismatch net is what would have to catch it if it recurs on a
real user's org.

## Phase 2 ? site 6, `conversation_turn_controller.py:273` (PASS on dormancy)

Fix: `get_model_router(settings or get_settings())` ? `get_model_router()`.

`_model_pending_intent` has two callers inside `classify_pending_plan_intent`,
with different fallbacks:

| Caller | Condition | Fallback when the model contributes nothing |
|---|---|---|
| modify-hint branch | `re_modify_hint(text)` matches | **`"modify"`** |
| general branch | a plan or pending task exists | `"unclear"` |

`re_modify_hint` fires on `don't`, `dont`, `without`, `instead`, `just`, `only`,
`skip`, `change`, `rather`. So a reply that plainly means *cancel* but contains
one of those words was classified as a request to **modify** the plan.

### Correction ? the severity claim I first wrote here was wrong

My first draft of this section said the dormancy "left a destructive plan
pending after the user tried to call it off." That is **not** what happens, and
I recorded it before tracing the caller. Correcting it rather than quietly
editing it out, since mis-stated severity is the exact thing this program keeps
catching.

`classify_pending_plan_intent` has exactly one production caller,
`agent_intelligence.py:1631`, and it is gated on:

```python
isinstance(early_plan, dict)
and early_plan.get("goal")
and not (isinstance(early_pending, dict) and early_pending)   # NO pending task
```

So this path only runs for an **orphan strategic plan** ? a `current_plan` left
over with *no* approval hold attached. A destructive plan awaiting approval is
excluded by the gate, and is handled by site 5's classifier instead. Further,
`cancel` and `modify` both clear `current_plan`. Nothing was left pending.

What the dormancy actually did, per branch:

| Intent | Effect at the caller | While dormant |
|---|---|---|
| `cancel` | clears `current_plan` | unreachable |
| `modify` | clears `current_plan`, **appends `" (regarding plan: {goal})"` to the user's message** | every modify-hint reply |
| `continue` | resumes the old goal as the message | unreachable |
| `unclear` | sets `pending_hold_prompt`, asks "abandon or hold" | every other reply |

So the two real consequences are:

1. **Stale-goal injection.** A reply meaning *stop* that contains a hint word
   got its text rewritten to carry the abandoned goal. *"don't bother with that,
   we're going a completely different direction now"* became
   *"?different direction now (regarding plan: Create a HubSpot list of MSP
   prospects?)"* ? the abandoned goal pushed into the very turn that rejected it.
2. **Forced re-ask.** Everything else fell to `unclear` and got the
   "abandon or hold" prompt instead of being understood.

Neither is a stuck destructive plan. Consequence 1 is still a genuine defect,
and it fails toward *carrying unwanted intent forward*, not toward safety.

### Possible link to the "MSPs" contamination, explicitly not proven

Consequence 1 is a real mechanism that injects a stale goal string into a later
turn's prompt, and the contamination observed earlier in this task surfaced the
token `"MSPs"` from prior marketplace testing. The shapes match. That is a
**hypothesis, not a finding** ? no trace ties the observed contamination to this
code path, and it is recorded here only so the connection is not lost. It should
not be cited as the cause of that incident without its own evidence.

### Before/after, buggy call restored for the first pass

`backend/scripts/probe_conversation_turn_controller_before_after.py`,
artifact `docs/delivery/conversation-turn-controller-before-after.json`.
Against a real orphan strategic plan (`hubspot.lists.create` +
`lists.add_members`), matching the shape the production caller requires:

| Reply | | Router entered | TypeError | Intent |
|---|---|---|---|---|
| "don't bother with that?" (modify hint) | before | **no** | yes, swallowed at WARNING | **`modify`** ? stale goal injected |
| | after | **yes** | no | `modify` (no AI provider configured locally) |
| "hold off, I need to run this past our finance lead?" (no hint) | before | **no** | yes, swallowed at WARNING | `unclear` |
| | after | **yes** | no | `unclear` (same reason) |

The swallowed line, verbatim:

```
WARNING: pending plan intent model skipped:
  get_model_router() takes 0 positional arguments but 1 was given
```

After the fix the same handler logs *"All AI providers failed (openai:
unavailable/not-configured; ?)"* ? the router is genuinely entered and fails on
missing local credentials, which is the expected local outcome and is what
distinguishes "reached" from "never called".

Status: **PASS on the dormancy defect**, and the mislabel it caused is measured
rather than argued: `modify` returned for an unambiguous cancel, 100% of the
time, deterministically.

Honest note on reachability, learned from Phase B: this site's one caller needs
a `current_plan` with a goal and no `pending_task`. How often real traffic is in
that state is **not measured**, so the fix is proven correct without a claim
about how much production behaviour it changes.

### Standing regression test

`backend/tests/services/test_pending_plan_intent_honors_model.py` ? 11 tests.
The load-bearing one asserts that when the model says `cancel` for a
modify-hint-shaped reply, `classify_pending_plan_intent` returns `cancel`, not
the `modify` fallback. The fixture asserts the factory is called with **zero
arguments**, so reintroducing the defect fails loudly instead of degrading.

Also pinned: the regex fast path still short-circuits `yes`/`cancel` without a
model call (cost and latency), the classification stays on
`TaskType.CLASSIFICATION` at `temperature=0.0`, the plan goal is actually
included in the prompt (without it the model cannot resolve "that"), and a real
provider outage still degrades instead of raising.

Mutation-proven 7/7 (`backend/scripts/scratch_mutate_pending_plan_intent.py`),
including restoring the original dormant call, dropping `cancel` from the
accepted labels, and removing the goal from the prompt.

Regression check: 279 passed across the pending/turn-controller/connector-action
suites. Baseline: `conversation_turn_controller.py:273` removed from
`KNOWN_DORMANT`. **Six of twelve sites now closed.**

### Live production proof ? PASS

`scripts/verify-pending-plan-intent-live.py` against deployed tip
**d57b48c36853b8cb066f04a205c5df8acd66ad16**, org
`f07e57c0-1501-4000-8000-c04e57a00001`
(`docs/delivery/pending-plan-intent-live.json`).

The scenario seeds the exact state the one production caller requires ? a
`current_plan` with a goal and **no** `pending_task` ? directly in
`conversations.task_state`, then sends one reply. The seeded goal carries a
nonsense canary token, `Zenphara`, that occurs nowhere else, so any appearance
of it in the answer is injection rather than coincidence.

| Scenario | Branch | Reply | "abandon or hold" prompt | Canary leaked | Plan cleared |
|---|---|---|---|---|---|
| "hold off, I need to run this past our finance lead before anything happens" | general (fallback `unclear`) | "Understood. I'll wait for finance lead approval." | **no** | no | yes |
| "don't bother with that, we're going a completely different direction now" | modify-hint (fallback `modify`) | "Understood. I'll drop the previous thread and work from the new direction." | no | **no** | yes |

**Why this is conclusive, and not just an absence of a bad string.** The general
branch has no non-model route to `cancel`/`modify`/`continue`: its fallback is
`unclear`, and `unclear` makes the caller emit that verbatim prompt and return.
Two independent observations rule that out ? the prompt never appeared, and
`current_plan` was cleared, which happens *only* inside the three model-decided
branches. So the model returned a valid label.

The remaining way this could be vacuous is if the regex fast path had answered
before the model was consulted. Checked, not assumed
(`backend/scripts/scratch_check_site6_phrasings.py`): neither phrasing matches
the clear-cancel regex or the confirm regex, so both genuinely reach the model.

The canary also stayed out of both answers, so the stale-goal injection
described above is not occurring at this tip.

Honest limits on this PASS:

- The state was **seeded directly**, not produced by a natural conversation.
  That is deliberate ? it is the only way to hit a caller gated on
  plan-without-pending-task ? but it means this proves the mechanism works, not
  that real traffic reaches it. The reachability rate is still unmeasured.
- The two answers read as correct comprehension, but the final answer is
  model-generated regardless, so the reply *text* is not itself evidence about
  the classifier. The load-bearing evidence is the branch discrimination above,
  not how sensible the wording sounds.

## Phase 2 ? site 7, `query_rewriter.py:52` (PASS on dormancy)

Fix: `get_model_router(settings)` ? `get_model_router()`.

What was silently absent: `rewrite_for_retrieval` turns a context-dependent
follow-up into a standalone search query. Its one production caller,
`agent_intelligence.py:2610`, feeds the result straight into
`prepare_assistant_turn(query=refined_query)` ? so its output **is** the query
the whole turn retrieves against, for RAG, Knowledge Fabric and hybrid search
alike.

While dormant it returned `refined_query == original_query` every time. So for
every context-dependent follow-up in every non-`fast` mode, retrieval searched
on the raw text. *"and what about their renewal?"* went to the index exactly
like that, with `their` unresolved and `Acme Corp` ? the only useful search term
in the exchange ? never reaching it.

This one fails toward **quietly worse retrieval**, which produces no error and
no user-visible symptom. The answer still arrives, because the final generation
model sees the conversation history directly; only the evidence behind it is
thinner. That makes it the least visible site so far and the hardest to have
caught by observation.

### Before/after, buggy call restored for the first pass

`backend/scripts/probe_query_rewriter_before_after.py`,
artifact `docs/delivery/query-rewriter-before-after.json`.

| | Router entered | TypeError | `refined_query` |
|---|---|---|---|
| before | **no** | yes, swallowed at WARNING | `"and what about their renewal?"` (unchanged) |
| after | **yes** | no | unchanged ? no AI provider configured locally |

```
WARNING: query rewrite skipped org_id=probe-org
  error=get_model_router() takes 0 positional arguments but 1 was given
```

Note the trap in reading this table: `refined == original` is also the *correct*
fallback, so the returned string alone cannot distinguish "dormant" from
"working but declined". Router entry is the discriminator locally ? and in
production that ambiguity is now resolved by the audit field below.

### New finding ? the existing test could never have caught this

`test_intelligence_engine_gaps.py::test_query_rewriter_uses_conversation_context`
has covered this function all along. It patches the factory with
`patch(..., return_value=router)`, which installs a `MagicMock`. A `MagicMock`
accepts **any** signature, so `get_model_router(settings)` succeeds inside the
test while the real zero-arg factory raises `TypeError` in production.

Measured, not asserted
(`backend/scripts/scratch_prove_existing_rewriter_test_blind.py`):

```
  existing test WITH the fix : PASS
  existing test WITH the bug : PASS
```

The mock granted the production code a calling convention it does not have.
This is the seventh instance in this program of a green test being the reason a
bug survived, and it is a **distinct class from "one layer too low"**: not a fix
aimed below the real cause, but a test that could not fail. Worth separating,
because the countermeasures differ ? the first needs live re-verification after
deploy, this one needs fakes that enforce the real signature.

Every fake in the new suite therefore asserts the factory is called with zero
arguments.

### Production observability added

A dormant rewriter and a model that declines to rewrite return byte-identical
results, which is precisely why this sat unnoticed. Following the precedent set
for the grounding validator, the caller now writes a
`retrieval.query.rewritten` audit event carrying **`modelRan`** ? true only
after `router.complete` returns ? alongside `changed`, `modeKey`, and
`historyTurns`. `rewrite_for_retrieval` returns the new `model_ran` key to
support it.

Two mutations exist specifically to stop that field lying: one sets it to `True`
unconditionally, one sets it before the call completes. Both are caught.

### Standing regression test

`backend/tests/services/test_query_rewriter_reaches_model.py` ? 14 tests.
Load-bearing assertions: a follow-up is genuinely rewritten when the model
returns one; `settings` is never forwarded to the factory; conversation history
reaches the prompt; the cheap `INTENT_DETECTION` tier and `temperature=0.0` are
pinned; the model is not consulted when there is no history or no query; an
echoed or unparseable response falls back to the original; the 2000-character
cap holds; and `model_ran` is correct in all four branches, including `False`
for the exact `TypeError` that defined the dormancy.

Mutation-proven 11/11 (`backend/scripts/scratch_mutate_query_rewriter.py`).
Regression check: 40 passed across the rewriter, intelligence-engine, and
research-policy suites. Baseline: `query_rewriter.py:52` removed from
`KNOWN_DORMANT`. **Seven of twelve sites now closed.**

### Live production proof ? UNREACHED, not PASS

`scripts/verify-query-rewriter-live.py` then
`scripts/probe-query-rewriter-reachable-shape.py`, both against deployed tip
**f8fb93d68fec04780dec49f20dce459bfcf78176**
(`docs/delivery/query-rewriter-live.json`,
`docs/delivery/query-rewriter-reachable-shape.json`).

**Zero `retrieval.query.rewritten` events across six two-turn conversations.**
The caller at `agent_intelligence.py:2610` never ran, so nothing about the fix's
production behaviour was tested. This is explicitly **not** being recorded as a
pass.

| Shape | Mode | unified completed / fallthrough | Reached rewriter |
|---|---|---|---|
| pronoun follow-up ("and what about their renewal?") | standard | served live | no |
| elliptical follow-up ("how long does that usually take?") | standard | served live | no |
| connector read follow-up (HubSpot deals ? close dates) | standard | 1 / 1 `read_tool_classical` | **no** |
| reasoning-mode analysis follow-up | reasoning | 2 / 0 | no |
| research-scope follow-up | standard | 2 / 0 | no |
| CRM entity follow-up (Acme ? open deals) | standard | 1 / 1 `read_tool_classical` | **no** |

The two bolded rows are the informative ones. They **did** fall through
unified-turn-live, which was the hypothesised prerequisite, and still did not
reach the rewriter. So fallthrough is necessary but not sufficient: the
connector-turn block returns at line 2606, ahead of the rewriter at 2610. Eight
early returns sit between the unified-turn call and the rewriter.

Production fallthrough reasons over 30 days, n=512
(`docs/delivery/unified-turn-fallthrough-reasons.json`) ? two of the four were
exercised above; `defer_classical_tool_sse` and `outcome_error` were not:

| Reason | Count |
|---|---|
| `defer_classical_tool_sse` | 143 |
| `outcome_error` | 142 |
| `pending_family_classical_resume` | 136 |
| `read_tool_classical` | 91 |

### This is a "one layer too low" instance, and the third in three investigations

The pattern the last two investigations established repeats exactly. Fixing the
dormant call is one layer below the question that decides user impact: *does the
code containing it run at all?* The fix is correct, mutation-proven and
deployed, and on the evidence so far it changes nothing a user experiences,
because the line is not reached.

Worth stating plainly: had the audit event not been added in the same change,
this would have been written up as a clean PASS. The local before/after was
green, the deploy succeeded, and the answers looked fine. Only an instrumented
production trace distinguished "the call works now" from "the call still never
happens" ? which is the same lesson as the HubSpot transport fix and the
fabricated-write gate.

### The bigger finding ? the classical answer path may be largely dead

Two independent instrumented points now sit in the region of
`execute_task_streaming` after the unified-turn-live call, and **both record
zero production events**:

| Instrument | Location | Window | Events |
|---|---|---|---|
| `answer.grounding.validated` | `_finalize_assistant_response` | 30 days | **0** |
| `retrieval.query.rewritten` | `agent_intelligence.py:2610` | since deploy | **0** |

Against 1008 `unified_turn.live.completed` and 512 fallthroughs in the same
30 days. The grounding-validator zero is the stronger evidence, having had a
full 30-day window; the rewriter's window is hours old and its zero is
suggestive, not conclusive on its own.

Read together this raises a real possibility that the classical
retrieval-and-answer region is effectively dead code for current production
traffic, with unified-turn-live serving everything it does not hand to the
connector path. Stated as a **hypothesis needing its own investigation**, not a
finding: proving it requires a longer observation window and a deliberate
attempt at the two untried fallthrough reasons.

**Process consequence, recommended for the remaining five sites:** measure
reachability *before* spending a fix-and-prove cycle. Sites 1/3 and 7 have now
each consumed a full cycle to arrive at "correct fix, unproven impact". A cheap
reachability check first would have ordered this work better, and would have
caught that these two sites share a single root condition rather than being two
independent findings.

Status: **PASS on the dormancy defect** (local before/after is decisive),
**UNREACHED on production impact**. Not rounded up.

## Phase 2 ? customer RAG (`get_rag_service`, both sites)

Chosen next over the remaining severity order because this one sits on the
unified turn path that production traffic actually uses, and because it is the
only site with a pre-existing live trace of its own dormancy.

- `unified_turn_knowledge_context.py:201` ? `get_rag_service()`. Restores
  customer RAG to the replan loop. Previously `org_rag_error` on every turn.
- `cache_warming_scheduler.py:48` ? `get_rag_service()`. Cache warming threw per
  org before warming anything; already visible at `warning`, so this one was
  never silent, only broken.

Before evidence, already on record from the replan-loop artifact at tip
`ccc98167`: `org_rag_error = "get_rag_service() takes 0 positional arguments but
1 was given"` with `org_rag_chunk_count = 0` on both evidence-bearing turns.
The pass condition is the disappearance of that key on a live turn.

### PASS ? live at deployed tip `db928881`

Same script, same org, same queries as the before-run, so the comparison is
like-for-like rather than a differently-shaped test.

| | tip `ccc98167` (before) | tip `db928881` (after) |
|---|---|---|
| `org_rag_error` (hard turn) | `get_rag_service() takes 0 positional arguments but 1 was given` | **absent** |
| `org_rag_error` (rich turn) | same error | **absent** |
| `org_rag` in `sources_tried` | yes | yes |

Evidence pointer: `unified_turn.live.completed` @ `2026-09-01T00:33:08.727681Z`,
artifact `docs/delivery/evidence-sufficiency-loop-live.json`. The hard turn's
`sources_tried` begins `['org_rag', 'internet', 'business_graph']`, so the source
was genuinely reached on the same run where the error key is gone ? the absence
is the call succeeding, not the branch being skipped.

Honest limit on this PASS: `org_rag_chunk_count` is still `0`. The isolated
conversation org has no customer documents, so what is proven is that the call
**executes and returns cleanly** instead of throwing. It does not prove customer
RAG returns useful evidence, which would need an org with a real corpus. Stated
so this is not read as more than it is.

Cost: no measurable latency change. The rich turn ran 32.1s against 32.9s on the
before-run, which is well inside run-to-run variance for a 3-round loop, and the
call it replaces previously failed instantly ? so the true added cost is one RAG
query per loop round, unmeasurable here because the corpus is empty.

**Status: both `get_rag_service` sites FIXED and LIVE-CONFIRMED at `db928881`.**

## Dead-path hypothesis ? REFUTED (2026-09-01)

Sites 1/3 (grounding validator) and 7 (query rewriter) both recorded **zero**
production events after their fixes went live. Two instruments, two zeroes,
prompted the hypothesis that the classical retrieval-and-answer region after the
`unified-turn-live` call is dead code for current traffic ? and with it, the
question of whether the remaining four sites were worth fixing at all.

The hypothesis is **wrong**. The region is reached by real traffic every day.

### What the zeroes actually meant

Both instruments sit *inside* the region, so a zero from either cannot separate
"region never entered" from "entered, but this branch skipped". That distinction
was the whole question, and neither instrument could answer it.

The decisive signal was one already carrying 30 days of history:
`agent.react.iteration`. Its two emitters are cleanly separable by the
`audit_resource_type` each passes:

- `agent_intelligence.py:3221` ? the **only** caller of `run_streaming`, sitting
  at line 3221, well past the region entry at 2608, passing `"assistant"`.
- `agent_intelligence.py:1293` ? the separate non-streaming `execute_task`,
  passing `"workflow_run"` / `"agent_job"`.

Both lines are inside `execute_task_streaming` (1382-3844) with no function
boundary between them, and the region entry sits at function-body indentation,
so **reaching 3221 requires executing 2608**.

| resource_type | events (30d) | means |
|---|---|---|
| `assistant` | **606** | classical region entered |
| `agent_job` | 37 | other entry point |
| `workflow_run` | 3 | other entry point |

Spread across 28 of 30 days, including 120 on the current day. Artifact:
`docs/delivery/classical-region-reach.json`, probe
`backend/scripts/probe_classical_region_reach.py`.

### All four fallthrough reasons carry real volume

No branch is unused, so the premise that grounding and the rewriter "happened to
sit on the two unused branches" is also wrong:

| reason | events (30d) |
|---|---|
| `defer_classical_tool_sse` | 143 |
| `outcome_error` | 142 |
| `pending_family_classical_resume` | 136 |
| `read_tool_classical` | 93 |

`outcome_error` at 142 of 514 is the unified turn's own reasoning failing on
roughly 28% of fallthroughs. Noted as a separate finding, not part of this one.

### So why is the rewriter still at zero

Not deploy timing ? checked rather than assumed. Production `git_sha` is
`f8fb93d68fec04780dec49f20dce459bfcf78176`, the instrumented commit, and **36**
post-region ReAct iterations occurred after that commit's time, the latest at
`2026-09-01T21:44:33Z`. The region ran, repeatedly, with the instrument live,
and the rewriter branch never did.

That leaves the gate above it, `if mode_key != "fast"`. **This is not yet
proven**: no audit event anywhere records the effective mode
(`docs/delivery/effective-mode-distribution.json` ? all four candidate event
types checked, none carries a mode field). Labelled INCONCLUSIVE pending the
instrument below, not rounded up to a root cause.

### Instrument corrected

The first instrument was placed *inside* the mode gate, so it inherited the
exact ambiguity it was meant to resolve. Replaced by
`classical.answer_path.reached`, emitted unconditionally on region entry, with
`modeKey` and `rewriteAttempted`, which separates "region never runs" from "runs
but skips the rewriter". Committed at `c38d42cf`, awaiting deploy.

### Consequence for the remaining four sites

Reachability was checked per site before any further fix work. Only one of the
four is in the region at all ? the other three sit on hotter paths than any site
fixed so far:

| site | production call site | real reach |
|---|---|---|
| `contextual_understanding` (and `domain_intelligence`, nested at `contextual_understanding_service.py:89`) | `agent_intelligence.py:1753`, function-body level | **every** streaming turn past the cache and pending-clarify returns ? ~1,527 turns/30d |
| `conversational_turn_gate` | `unified_turn_reasoning_service.py:1278` (unified path) **and** `agent_intelligence.py:2150` (fallthrough) | both paths ? effectively all turns |
| `clarification_engine` | `agent_intelligence.py:2718` | inside the region; reached daily, further gated |

The three highest-reach sites are on the unified-turn path that serves the
majority of traffic, which is the opposite of the dead-region read. These are
ordinary fix-and-prove work, not a product decision.

### Live follow-up: the region is entered, but not via `read_tool_classical`

With `classical.answer_path.reached` deployed at `d154bb99`, four turn shapes
were run live (`docs/delivery/query-rewriter-reachable-shape.json`). Two produced
a genuine `read_tool_classical` fallthrough ? and **still** recorded zero
region-reach events.

So that reason falls through the unified turn and then exits *before* line 2608,
which matches the static read: `run_connector_turn` handles the read tool and
returns at the `stop_pipeline` branch on line 2606, one line above the region.

This does not revive the dead-path hypothesis ? 606 post-region ReAct iterations
over 30 days are not in dispute. It narrows it: the route into the region is one
of the three reasons not yet reproduced live (`defer_classical_tool_sse`,
`outcome_error`, `pending_family_classical_resume`), or a fallthrough where the
connector turn declines to stop the pipeline. **Which one is still unidentified**
and is not being guessed at here.

## Phase 2 ? sites 9 and 10, `contextual_understanding_service.py:225` and `domain_intelligence_service.py:208` (PASS on dormancy)

Fixed together: domain classify is nested inside `understand()` at
`contextual_understanding_service.py:89`, so neither is reachable in production
without the other, and proving them separately would have meant faking the
caller of one to test the other.

Both were `get_model_router(self.settings)` inside a broad `except Exception`.

**Reach, measured before fixing** (the discipline the dead-path detour bought):

- Site 9 is called at `agent_intelligence.py:1753`, at function-body level, so it
  runs on **every** streaming turn past the cache and pending-clarify returns ?
  roughly 1,527 turns/30d, unified-served and fallthrough alike. This is the
  highest-reach site in the whole audit.
- Site 10 is reached only when rule + org-profile confidence lands under
  `DOMAIN_CONFIDENCE_THRESHOLD` (0.55).

**What was silently absent.** Site 9's `_model_extract` only runs when rules
cannot infer a goal ? messages that do not end in `?` and run past 12 words. For
exactly those long, instruction-shaped messages, `goal` stayed `None` and
`constraints` stayed empty, and that empty understanding is what
`get_task_classifier(...).classify(understanding=...)` received.

Site 10 is worse in kind. It is the documented third tier ? "org profile hints
first, rule/keyword taxonomy second, **LLM fallback last**". That last tier has
never existed in production. Every message too ambiguous for keyword rules kept
its low-confidence guess, and `DOMAIN_CONFIDENCE_THRESHOLD` is read by
`domain_routing_policy`, `domain_retrieval_policy` and `learning_strategy_keys`
? so the absence changed routing and retrieval decisions, not just a label.

### Before/after against real code, fixes stashed

`backend/scripts/probe_understanding_domain_before_after.py`, artifacts
`docs/delivery/understanding-domain-{before,after}.json`. The before arm is the
actual pre-fix source via `git stash`, not a reconstruction.

| | before | after |
|---|---|---|
| site 9 factory call | with 1 arg ? TypeError | zero-arg |
| site 9 result | `{}` ? goal `None`, constraints `[]` | real goal + 2 constraints |
| site 10 factory call | with 1 arg ? TypeError | zero-arg |
| site 10 result | rule result verbatim, **confidence 0.1** | real classification, **confidence 0.82** |

Both WARNING lines name the cause exactly: `get_model_router() takes 0
positional arguments but 1 was given`.

The site 10 row is the finding in one line: dormant, the fallback tier returned
the caller's own low-confidence input unchanged, below the 0.55 threshold that
downstream policy reads.

### Tests

`backend/tests/services/test_understanding_and_domain_reach_model.py`, 10 tests.
The fake router raises `TypeError` on **any** argument, mirroring the real
factory. That is deliberate: a permissive `MagicMock` is precisely how this bug
survived at the query rewriter, where the existing test passed with the bug
present. Mutation-proven 6/6
(`backend/scripts/scratch_mutate_understanding_domain.py`), including restoring
the dormant arity at both sites and deleting the low-confidence tier.

`KNOWN_DORMANT` shrinks by two; two remain (`clarification_engine.py:769`,
`conversational_turn_gate.py:240`).

### Honest limit ? live proof NOT YET obtained

**Status: PASS on dormancy, live production impact NOT PROVEN.** Neither service
writes an audit event, so there is currently no production signal that would
distinguish a working call from a dormant one. Site 9 in particular runs on
essentially every turn, which makes it both the most valuable to confirm and the
most costly to leave unobserved. Not labelled PASS overall until that exists.

### Root cause of every zero-event reading in this audit: `actor_id=None`

Three instruments added during this audit read zero in production. Two of those
zeroes were interpreted as "this code path is never reached". Both readings were
wrong, and the cause was the instruments, not the code.

`write_audit_event` **skips the `audit_events` insert entirely** when `actor_id`
is not a UUID (`app/workflows/audit.py:118-148`). `audit_events.actor_id` is
`uuid NOT NULL` and FKs `auth.users`, so the helper logs a warning and returns
rather than raising. All three instruments passed `actor_id=None`:

| instrument | site |
|---|---|
| `answer.grounding.validated` | `_finalize_assistant_response` |
| `classical.answer_path.reached` | `execute_task_streaming` |
| `context.understanding.extracted` | `execute_task_streaming` |

None ever wrote a row, whether or not the code ran. Every "UNREACHED" verdict
built on them is void:

- Phase B's grounding-validator UNREACHED ? **invalid measurement**
- Site 7's query-rewriter UNREACHED ? **invalid measurement**
- "`read_tool_classical` exits before the region" ? **invalid measurement**

The dead-path refutation itself **stands**: it rests on `agent.react.iteration`,
which passes a real actor and is unaffected. That independent signal is the only
reason this was caught rather than acted on.

Fixed: all three now pass `user_id`; `_finalize_assistant_response` gained a
`user_id` parameter. Standing AST guard added at
`backend/tests/test_audit_instruments_have_real_actor.py`.

**The guard found two more on its first run**, in code nobody was auditing:
`connector.auth.failed` and `connector.connected`
(`app/connectors/health_monitor_service.py:110,125`) have also never reached
`audit_events`. Pinned as known rather than patched blind ? the right actor for
a background health sweep is a product decision. **Open for Cesar.**

### Sites 9 and 10 ? LIVE PASS at `5f2b0014`

`scripts/verify-understanding-domain-live.py`, artifact
`docs/delivery/understanding-domain-live.json`. Six turns, all six past the rule
gate (verified in-script against the real gate, not assumed).

| | site 9 | site 10 |
|---|---|---|
| turns attempting the model | 6/6 | 3 |
| `modelRan=true` | **6/6** | ? |
| goal extracted | **6/6** | ? |
| `domainSource="llm"` | ? | **3/3** |

Evidence pointer: `context.understanding.extracted` @
`2026-09-02T04:46:11.220679Z`, `domainSource=llm`, `confidence=0.74`,
`routingActive=true`.

The site 10 rows are the finding closed. Those three messages score **0.000**
against the real rule classifier ? measured in
`backend/scripts/scratch_pick_low_domain_confidence.py`, after the first live
attempt used business-flavoured text that scored 0.7-0.8 and never reached the
tier at all. Dormant, they would have stayed at 0.000 with `routing_active=false`.
Live, the tier returned 0.74, 0.84 and 0.63 ? all above the 0.55 threshold that
`domain_routing_policy` and `domain_retrieval_policy` read. The fallback tier is
doing exactly the job it was documented to do, for the first time in production.

## Re-measurement with working instruments (supersedes the void verdicts)

### Site 7 `query_rewriter` ? LIVE PASS at `5f2b0014`

Evidence pointer: `classical.answer_path.reached` @ `2026-09-02T06:54:59.995672Z`
? `modeKey=agent`, `rewriteAttempted=true`, **`modelRan=true`**, **`changed=true`**,
`historyTurns=2`, 40 ? 58 chars. The model ran *and* produced a different
retrieval query than the user's raw text. This supersedes the earlier UNREACHED
verdict, which was measured with an instrument that could not write.

Getting there took correcting two probe faults, both of which had been silently
producing "proof" of the wrong thing:

1. **History came from the client, not the database.** `assistant.py:1041` builds
   `conversation_history` from `body.messages[:-1]`. The probe posted one message
   per request, so the rewriter saw no history and correctly returned before the
   model. `historyTurns=0` in the metadata is what exposed it ? without that
   field the run reads as a genuine failure.
2. **The turn that fell through was the turn without history.** With a
   tool-shaped *setup*, the fallthrough happened on turn 1. Reaching the rewriter
   needs a turn that carries history **and** falls through, so the setup was made
   conversational (unified-turn-live serves it) and the *follow-up* tool-shaped.

Honest limit: 1 of 4 shapes reached it. `read_tool_classical` on a
history-bearing turn is the only route confirmed so far.

### Sites 1+3 grounding validator ? NOT dormant, disabled by configuration

Zero `answer.grounding.validated` events, now with a working instrument, across
five confirmed region entries including the full-path turn above. The cause is
not reachability and not a dormant call:

```
validation_enabled_for_mode(mode_key, settings)      # intelligence_engine_settings.py:38
    speed_priority     -> {"reasoning", "agent"}
    accuracy_priority  -> {"fast", "standard", "reasoning", "agent"}
    default            -> {"standard", "reasoning"}          # excludes "agent"
```

Every region entry above recorded `modeKey=agent`. And
`resolve_effective_intelligence_mode` upgrades `standard` ? `agent` whenever any
connector is connected. So under the **default** performance mode the grounding
validator is switched off for precisely the orgs that have connectors ? real
customers ? while remaining enabled for the modes they never run in.

**This is a product/configuration decision, not a bug fix, and is left for
Cesar.** The honest options are to include `agent` in the default validation set,
or to accept that grounding validation is an opt-in for `accuracy_priority` orgs
and stop describing it as a standing safety net. What is no longer true is that
the site is "unreached" ? it is reachable and deliberately gated off.

## Site 8 `conversational_turn_gate.py:240` ? highest-reach site of the twelve

`classify_turn_shape` called `get_model_router(settings or get_settings())`. Fixed
to the real zero-argument form.

### Why this one never looked broken

It failed **closed**: the handler returns `shape="task_shaped"`, which is also a
perfectly legitimate verdict. Nothing errored, no output looked wrong, and the
fallback was even the *safe* direction ("never drop real work into chitchat").
The before/after probe shows exactly this - both arms return a usable decision:

| arm | router entered | shape | used_model |
|---|---|---|---|
| before (dormant) | False | `task_shaped` | False |
| after (fixed) | True | `mixed` | True |

`docs/delivery/turn-gate-before-after.json`. The only honest discriminators are
`router_entered` and `used_model`; the returned shape proves nothing on its own.

### Measured reach - 71.9%, before changing any code

`backend/scripts/probe_turn_gate_reach.py` runs the real heuristic over real
production user messages (30-day window, 1000 rows returned):

```
user messages considered : 1000
deferred to model        : 719  (71.90%)
heuristic mixed          : 1
  719  DEFERRED_TO_MODEL
  203  data_or_connector_signal
   51  human_moment_venting_no_ask
   16  social_no_task_signal
    9  meta_capability
```

So 719 of 1000 real turns had their shape decided by the dormant call fail-closed
default rather than by the model that was supposed to decide. This is the
highest-reach site in the whole inventory - higher than sites 9/10, and unlike
site 7 it does not depend on falling through to the classical region.

Second-order consequence, and the concrete user-visible one: the heuristic can
only reach `mixed` when a comma or `also/but/anyway/btw` joins the social and
task halves, which happened **once in 1000 turns**. `mixed` is the sole trigger
for `_maybe_prepend_mixed_social_ack` (`unified_turn_reasoning_service.py:1283`),
so the mixed social-ack feature - real, built, and on the LIVE path that serves
most traffic - was waiting on a call that never ran.

Honest scope limit: 71.9% is the *deferral* rate, not the rate at which the
model verdict differs from `task_shaped`. Many deferred turns are genuinely
task-shaped and the default was accidentally right. What the default could never
produce is `conversational` or `mixed`.

### Evidence

- Dormancy: **PASS** - `docs/delivery/turn-gate-before-after.json`
- Tests: 11 in `backend/tests/services/test_turn_gate_reaches_model.py`, all 11
  mutations caught (`backend/scripts/scratch_mutate_turn_gate.py`), including
  "restore the dormant call", "used_model always True", and "fail-closed becomes
  fail-open". One test asserts the heuristic still declines the probe message, so
  a future heuristic change cannot quietly make the suite vacuous.
- Regression: 164 related tests pass (`-k "turn_shape or turn_gate or
  conversational or social_ack or pending_reply"`).
- Observability: `turn.shape.classified` at `agent_intelligence.py:2189`, on the
  unconditional caller that runs every streaming turn, carrying `usedModel`,
  `shape`, `category`, `liveEnabled`. Actor is `user_id` from the start - the
  `actor_id=None` class of bug is now blocked by
  `backend/tests/test_audit_instruments_have_real_actor.py`.
- Live proof: **PENDING** deploy.

### CORRECTION to the 71.9% reach figure above

The 71.9% was measured one layer too low and should not be read as production
reach. `probe_turn_gate_reach.py` ran the real heuristic over real user messages
and found 719/1000 defer past it ? but that measures what *would* happen if the
gate ran on every turn. It does not run on every turn.

`classify_turn_shape` has exactly two callers:

- `agent_intelligence.py:2181` ? `apply_unified_turn_live` returns before this
  line, and LIVE serves the majority of traffic.
- `_maybe_prepend_mixed_social_ack` ? reached on 3 of the 9 `live_served = True`
  paths inside `apply_unified_turn_live`.

Evidence: a 6-turn live probe at `f7b25d08` and again at `b3a429f8` produced
**zero** `turn.shape.classified` events while 7 `unified_turn.live.completed`
rows confirmed every turn was LIVE-served. The gate did not run on any of them.

What 71.9% does honestly describe: of real user messages, the share whose shape
the heuristic cannot decide alone. It is an upper bound on the model tier's share
of gate invocations, not a share of turns.

### Third "one layer too low" ? this one in the instrument, not the fix

Worth recording as its own instance, since the user asked these be flagged
explicitly. The first two were fixes aimed at a symptom layer. This one is
different and arguably more dangerous: the *fix* was correct and live the whole
time, while the *instrument* measuring it was unreachable.

The replies in the `f7b25d08` probe run showed the gate plainly working ?
`"Glad it clicked."`, `"That's a reasonable place to pause."`, and a prepended
`"Hey ? on it."` social ack ? at the same moment the instrument reported zero
events. Read without the replies, that run looks exactly like the earlier
zero-event reachability findings, and would have been recorded as one.

Resolution: the event now lives inside `classify_turn_shape` itself with
`call_site` passed by the caller, so it cannot be misplaced relative to the call
it measures. Real reach will be read from production traffic on this instrument
rather than inferred.

### Site 8 final measured state ? dormancy FIXED, production reach NEAR ZERO

Four deploys of live-proof attempts (`f7b25d08`, `b3a429f8`, `b03def5c`) settle
this, and the answer inverts the section above.

**Proven:**

- Dormancy fixed ? `docs/delivery/turn-gate-before-after.json`, router entry
  goes False ? True, verdict `task_shaped` ? `mixed`.
- 11 regression tests, **11/11 mutations caught after the refactor**.

**Measured, not proven:** production reach. With the instrument inside
`classify_turn_shape` itself ? where it cannot be misplaced relative to the call
? 12 live turns across two distinct shapes produced **zero** events:

| run | tip | turns | events |
|---|---|---|---|
| reflective + task set | `f7b25d08` | 6 | 0 |
| same, instrument on LIVE social-ack caller | `b3a429f8` | 6 | 0 |
| same, instrument inside the function | `b03def5c` | 6 | 0 |
| rewriter-reachable shapes (reached region :2608) | `b03def5c` | 6 | 0 |

The last row is the decisive one. Those turns provably entered the classical
region at `:2608`, which sits *after* the gate caller at `:2181`. And
`context.understanding.extracted` fires from the same function with the same
`user_id`, so a run of `:2181` would have written a row. It did not ? therefore
the fallthrough re-enters `execute_task_streaming` **after** `:2181`, and that
caller is not reached under current routing either.

That leaves `_maybe_prepend_mixed_social_ack` as the only live caller, reached on
3 of 9 `live_served` paths, and none of the 12 probe turns took one.

**Honest conclusion.** Site 8 was reported above as the highest-reach site of the
twelve, on a 71.9% heuristic-deferral figure. Measured reach is near zero under
current LIVE routing. This is the same shape as the grounding validator: correct
code that routing does not reach. Note the `"Hey ? on it."` prefix seen in the
probe replies comes from some other social-ack path, not this gate.

**Decision for Cesar, not resolved unilaterally** ? same two honest options as
the grounding validator:

1. Fix the routing gap so the turn-shape gate runs on LIVE-served turns (it is
   the component that decides conversational vs task-shaped, and LIVE currently
   decides that some other way), or
2. Retire the gate and its `mixed` social-ack branch rather than leave a
   correct-but-unreached component implying conversational routing that is
   actually happening elsewhere.

### Site 7 upgraded during this work

`docs/delivery/query-rewriter-reachable-shape.json` at `b03def5c`: **3 of 4**
shapes now reach the rewriter, 3/3 with `modelRan=true` and `changed=true`. The
earlier "1 of 4" note is superseded.

## Site 11 `clarification_engine.py:769` ? LIVE PASS at `301a64e1` (last of the twelve)

`_polish_question` called `get_model_router(self.settings)`, raised `TypeError`
on every invocation, and the handler swallowed it. So it always returned `None`,
`generate_clarification_question` fell back to `polished or question`, and every
clarifying question the platform asked shipped as its **raw template**.

Why nobody noticed: the templates are legitimate, readable questions. `"I can
help with {action}. {specific_question}"` renders as a perfectly serviceable
clarification. The degradation was tone, not correctness ? which is exactly the
class of silent failure this audit was opened to find.

### Proof without an instrument

This is the one site of the twelve that needed no audit event, which matters
after three separate instrument-placement misses. The polished question **is**
the user-visible reply, so the reply text is the evidence, and the template
strings are the discriminator:

| state | user receives |
|---|---|
| dormant | the template **verbatim** |
| fixed | one natural question, rewritten |

`scripts/verify-clarification-polish-live.py` scores three outcomes rather than
two, so a turn that never triggered clarification cannot be mistaken for a pass.
`dialogue_mode=clarify` in the SSE metadata (`agent_intelligence.py:2896`)
separates "did not trigger" from "triggered and unpolished".

**Evidence pointers** ? tip `301a64e1`, org `f07e57c0-1501-4000-8000-c04e57a00001`:

- conversation `3ffeda10-0e66-44d8-88db-8add63598634`, `dialogue_mode=clarify`,
  reply `"I need the target first. Which Gmail messages or thread should I archive?"`
- conversation `3a222797-170f-4d39-a6a2-053055bf683a`, `dialogue_mode=clarify`,
  reply `"I need the actual task. What should I do for the client?"`

Neither contains any of the four verbatim template markers. The template for
that trigger would have read `"I can help with archive. Could you share the
target and any constraints?"`.

2 of 4 scenarios triggered clarification; both were rewritten, 0 verbatim. The
two that did not trigger are reported INCONCLUSIVE, not rounded up.

`connector_unavailable` is deliberately excluded from the probe:
`agent_intelligence.py:2866` overrides the question with `shaped["error"]` on
that branch, so the polish is discarded there and the branch would report a
false FAIL.

### Local proof

- 8 regression tests (`tests/services/test_clarification_polish_reaches_model.py`)
- **9/9 mutations caught** (`backend/scripts/scratch_mutate_clarification_polish.py`)

One mutation initially survived, and it was a blind test of my own: the
high-risk-confirmation guard test asserted from *inside* the fake router, but
`_polish_question` catches bare `Exception` and `AssertionError` is an
`Exception`, so the raise was swallowed and the template returned anyway ? the
test passed with the guard removed. It now counts calls and asserts outside the
handler. Same failure class this program has found repeatedly, in the test
written to catch it.

### All twelve closed ? `KNOWN_DORMANT` is empty

`tests/test_no_dormant_model_calls.py` now passes with an **empty** baseline: no
zero-argument factory is called with arguments anywhere in `app/`. Any future
entry means a fresh dormant call shipped.

## Grounding validator in agent mode ? enabled, measured, reverted (`1e94e644` ? `301a64e1`)

Cesar's decision was to include agent mode, defaulting toward inclusion on
safety grounds, with real latency measured before making it final. It was
enabled, measured on the deployed tip, and reverted the same day, because the
measurement was decisive against it.

### The gap is worse than "off for agent mode"

`resolve_effective_intelligence_mode` upgrades **both** `standard` and
`reasoning` to `agent` whenever a connector is connected, and leaves `fast` as
`fast`. So a connector-connected org can only ever reach `{fast, agent}`, and
the default validation set is `{standard, reasoning}`. The intersection is
**empty**: grounding validation is structurally unreachable for every org with a
connector, not merely disabled for one mode.

Neither function is wrong alone, which is why this survived. A test asserting
the default set would have looked correct; only composing the two exposes it.
`tests/services/test_grounding_validation_reaches_real_orgs.py` pins the
composition for that reason.

### What the measurement showed

`docs/delivery/grounding-validator-latency.json`, 3 agent-mode turns on the
classical answer path at `1e94e644`. `ai_pipeline_latency` held exactly one
`validation` row in 30 days, at 0ms, so there was no history to read ? the gate
had made the validator unreachable.

| metric | measured |
|---|---|
| added latency | **p50 9309ms, p95 10131ms** (generation stage p50 is 3123ms) |
| answers replaced | **3 of 3** |
| fell through to `SAFE_FALLBACK` | 1 of 3 ? a dead end |

All three failed initial validation and were regenerated; two passed on the
second pass, one did not. The ~9?10s is two validation calls plus a
regeneration.

Evidence pointer: `answer.grounding.validated` @ `2026-09-02T09:24:23Z`,
`modeKey=agent`, `durationMs=8075`, `sources=5`, `answerReplaced=true`,
`isValid=false`, issues including `regeneration_failed`.

### Why it fails, and why it is not a tuning problem

The rejected claim was `"No HubSpot contact record found for Dana Whitfield"` ?
legitimately derived from a live HubSpot search, judged against five knowledge
snippets that merely *mention* HubSpot and Dana. The validator was reasoning
correctly and reaching the wrong conclusion, because it was given the wrong
context to judge against.

Agent mode is precisely the mode where answers come from **tools** while RAG
chunks are incidentally present. This validator only knows how to compare an
answer against retrieved context; it has no notion of tool-derived grounding.
No threshold or prompt change fixes that.

### Fourth "one layer too low" ? and mine

The `has_context` guard I added covers `rag_sources == []`. The real failure
mode is `rag_sources` **present and irrelevant** to a tool-derived answer. I
guarded the empty case, shipped, and the measurement found the populated case
one layer up. Same pattern as the previous three: the guard was correct and left
the defect live.

### What was kept

The revert is only the mode flag. Retained because they are improvements
regardless:

- the `has_context` guard ? a no-context turn can no longer reach `SAFE_FALLBACK`
- `skipReason=no_retrieved_context` instrumentation, so the skip rate is
  measurable rather than assumed
- tests pinning both the exclusion and the coverage gap, so re-enabling sends
  the next reader to the measurement rather than to a merge conflict

### Still open for Cesar

The coverage gap is real, documented, and **not closed**: connector-connected
orgs get no grounding validation by default. Closing it needs a tool-aware
validator that can judge a tool-derived answer against its tool results, not a
config flag. `accuracy_priority` remains a genuine opt-in today, at the measured
~9s cost.

## Connector health audit gap ? closed at `1e94e644`

`connector.auth.failed` and `connector.connected` passed `actor_id=None`, which
`write_audit_event` silently drops (`NOT NULL` with an FK to users). A connector
dropping into auth failure therefore left **no audit trail at all**, while the
code read as though it recorded one. Found by the AST guard written after the
`actor_id=None` discovery, in code nobody was auditing.

`resolve_connector_audit_actor` assigns a real, named actor:

1. `connectors.created_by` ? the person who connected it, and the person whose
   reconnect is needed. Populated for 6 of 19 status-changeable production
   connectors.
2. the org's `owner`, then `admin`, from `organization_members` ? covers the
   remaining 13, and is the right escalation target for a connector with no
   recorded creator. Every org that actually holds connectors resolves to a real
   owner (`backend/scripts/scratch_connector_actor_coverage.py`,
   `scratch_org_owner_lookup.py`).

When neither resolves it logs `connector_health_audit_no_actor` and skips,
rather than writing a row that would be discarded silently.

`KNOWN_NONE_ACTOR` in `tests/test_audit_instruments_have_real_actor.py` is now
**empty**. 14 tests cover the chain, including the cache (a sweep touches many
connectors per org) and the no-actor skip. One pre-existing health-monitor test
was upgraded rather than merely unbroken: its fixture had no `created_by`, so it
now pins the real actor.

---

# FINAL LEDGER - the twelve-site audit, closed 2026-09-02

This section is the authoritative closing record. Everything above it is the
working history, including corrections and retractions that are deliberately
preserved. Where an earlier section conflicts with this ledger, this ledger is
the current state.

Note on encoding: this section is deliberately plain ASCII. The body of this
document above has mixed-encoding damage from earlier appends, and adding more
non-ASCII punctuation would compound it.

## Ledger

Dormancy is certain by construction for all twelve: a positional-argument count
mismatch is evaluated before the callee runs, so none of these could ever have
intermittently succeeded. Reach is the variable, and reach is what determines
user impact - which is the single most important lesson of this program.

| # | Site | Dormancy | Production reach | Final state |
|---|---|---|---|---|
| 1 | `answer_validator.py:74` | Fixed 2026-08-31 | Config-gated OFF for agent mode; 0 events in 30d | Tool-aware validator built; agent mode enabled; LIVE PASS `ab7ca5a7`. DELIVERED - see "Coverage gap: closed" below |
| 2 | `unified_turn_knowledge_context.py:201` (`get_rag_service`) | Fixed 2026-08-31 | Reached; `org_rag_error` observed live while dormant | LIVE PASS `db928881` |
| 3 | `agent_intelligence.py:931` (regeneration) | Fixed 2026-08-31 | Unreachable while site 1 failed open | Reachable and tool-aware; exercised live at `742414b9` (11.9s regeneration, since removed as a false trigger) |
| 4 | `schema_param_extractor.py:319` | Fixed 2026-08-31 | Reached | PASS via before/after router-entry probe. INCONCLUSIVE status closed out |
| 5 | `pending_reply_classifier.py:500` | Fixed 2026-09-01 | Reached | LIVE PASS |
| 6 | `conversation_turn_controller.py:273` | Fixed 2026-09-01 | Reached | LIVE PASS `d57b48c3` |
| 7 | `query_rewriter.py:52` | Fixed 2026-09-01 | Reached | LIVE PASS `5f2b0014` (modelRan + query changed). The earlier UNREACHED reading was an instrument artifact - see Class B below |
| 8 | `conversational_turn_gate.py:240` | Fixed 2026-09-01 | Measured NEAR ZERO | Model tier RETIRED `02ef5a6a` by product decision after its value was measured. Live post-fix proof `519fcdf7`: mixed social ack fires 3/3, all consumers intact |
| 9 | `domain_intelligence_service.py:208` | Fixed 2026-09-01 | Reached | LIVE PASS `5f2b0014` (3/3 `domainSource=llm`) |
| 10 | `contextual_understanding_service.py:225` | Fixed 2026-09-01 | Reached | LIVE PASS `5f2b0014` (6/6 `modelRan`) |
| 11 | `clarification_engine.py:769` | Fixed 2026-09-02 | Reached | LIVE PASS `301a64e1` (2/2 questions polished) |
| 12 | `cache_warming_scheduler.py:48` (`get_rag_service`) | Fixed 2026-08-31 | Scheduler-driven | Fixed; performance-only, was already visible at `warning` |

`KNOWN_DORMANT` in `backend/tests/test_no_dormant_model_calls.py` is empty, and
the guard only permits that set to SHRINK. A new entry means a fresh dormant
call shipped.

### Severity corrections made during the audit, preserved

Two of the Phase 0 severity rankings were wrong and were corrected on evidence,
not opinion:

- Site 1 was ranked **Critical (correctness)** on the assumption that a
  fail-open validator was falsely certifying answers. Measurement showed it
  never executed on live traffic, so nothing was being certified at all. It was
  downgraded, then turned out to be a **coverage** problem rather than a
  correctness one - the validator was unreachable for exactly the orgs that most
  needed it.
- Site 8 was ranked on a 71.9% reach figure that was measured one layer too low:
  it was a share of gate invocations, not of turns. True reach is near zero.

## The permanent lesson: "one layer too low"

Named class for this program. **Five confirmed instances.** The pattern:

> The fix is correct, mutation-proven, and deployed. It sits one layer below the
> layer that decides whether a user is affected. Local tests pass, the deploy
> succeeds, the output looks right, and the defect is still live.

| # | Instance | The fix | The layer that actually decided user impact |
|---|---|---|---|
| 1 | HubSpot transport fix | Corrected the call | A different transport path served real traffic |
| 2 | Fabricated destructive write gate | Gated the fabricating path | The fabrication entered from a path upstream of the gate |
| 3 | Site 7 `query_rewriter` | Dormant call fixed and proven | The enclosing classical region was not reached on the measured turns |
| 4 | Grounding validator `has_context` guard | Guarded `rag_sources == []` | The real failure was `rag_sources` **present and irrelevant** to a tool-derived answer, one layer up |
| 5 | `tool_choice` 400 | Patched `_complete_openai_with_tools` | OpenAI models route through the streaming path, which bypassed that adapter entirely. Four more 400s after deploy |

Numbering note, recorded honestly: the working history above labels two
different findings as "third", because the site 8 instrument finding was written
up under that number in a separate session. The table here is the definitive
enumeration; the site 8 instrument finding belongs to Class B below, not to this
class.

Instances 4 and 5 were both mine, in the same session, after the class had
already been named twice. That is the strongest evidence that naming a failure
class does not by itself prevent it.

### What actually catches it

Ranked by what demonstrably worked in this audit, not by what sounds rigorous:

1. **An instrumented production trace of the specific line.** This is the only
   thing that reliably distinguished "the call works now" from "the call still
   never happens". Every clean local before/after in this audit was compatible
   with the defect remaining live.
2. **Mutation testing the guard**, not just running it. It found a blind spot in
   the regeneration evidence check where a structural source assertion passed
   while the body discarded the tool evidence.
3. **Asking "which layer serves real traffic?" before writing the fix.** For
   site 8 this question, asked late, changed the outcome from "fix and ship" to
   "measure, then retire".

## Class B: broken instrument

A distinct and arguably more dangerous class, surfaced three times. Here the
**fix was correct and live the whole time** while the instrument measuring it
was wrong, producing a confident false negative. Left unchecked, each of these
would have led to abandoning working code.

| # | Instrument | The defect | What it falsely reported |
|---|---|---|---|
| 1 | Site 8 `turn.shape.classified` | Event emitted at a caller the measured turns never took | Zero events, read as "unreached", while the probe replies showed the gate plainly working |
| 2 | Three audit instruments | `actor_id=None` caused `write_audit_event` to skip silently | Zero events across sites 7, 9, 10 - voiding three verdicts at once |
| 3 | `assessorRan` | Compared `confidence_source` against the literal `"model"`; the constant is `"loaded_model_artifact"` | False on **every** grounding event ever written, including ones where the assessor genuinely judged. Read as "validator fails open on 3 of 3 turns" |

The countermeasure that worked in all three cases was the same: **cross-check
the instrument against an independent signal** before believing a zero. Twice
that signal was the user-visible reply text, which showed the feature working
while the instrument reported nothing.

A vacuous check is a fourth variant of this class and was caught in the site 8
live proof: "no event claims the model ran" passed with **zero events of any
kind**, so it proved nothing. It is recorded as PASS-but-weightless in
`docs/delivery/turn-gate-retirement-live.json` rather than counted as evidence.

## Class C: silence mistaken for health

**Third named failure class of this program, permanent status, same standing as
"one layer too low" (Class A) and "broken instrument" (Class B).** Added
2026-09-02 on Cesar's instruction after closing the
`unnarrowed_tool_attach_blocked` watch item. Full trace in
`docs/delivery/unnarrowed-tool-attach-rootcause.md`.

Where Class A is a fix in the wrong place and Class B is an instrument that
lies, Class C is **an absence of signal read as evidence of health**. It is the
most seductive of the three: doing nothing is always the cheapest option, and a
quiet dashboard always looks like success.

### The instance that named it

| Aspect | Detail |
|---|---|
| The signal | 119 events over two days, then nothing for three weeks |
| The reasoning | Stopped on its own, never touched a real org, so not worth chasing |
| Why it failed | The burst had **two** causes. One was genuinely fixed on the day the events stopped (`65161f90`). The other had merely stopped being **exercised**: it only fires for non-OpenAI providers, and prod routes unified turns to OpenAI |
| Cost had it stood | A live defect sitting dormant until the first Anthropic or Gemini tool-carrying turn, then silently dropping those turns to the classical path |

### The rule

> **"Has not recurred" is not a root cause.** It cannot be distinguished from
> "has not been exercised" without identifying the mechanism. A defect on a
> conditionally-reached path goes quiet when the condition stops holding, and
> looks exactly like a fix.

Diagnostic question, cheap to ask every time: *what would have to be true for
this to fire, and is that still true?* If nobody can answer, the silence is
uninterpreted, not clean.

### Why this class earns permanent status: the mistake recurred four times

The underlying defect is one line of Python repeated across the codebase. The
narrowing proof is an attribute on a `list` subclass, so `list(x)`, a
comprehension, a slice and `sorted(x)` all discard it silently.

| # | Site | Resolved | How it was found |
|---|---|---|---|
| 1 | `round_tools = list(attach_tools)` | 2026-08-13 `65161f90` | 109 production events |
| 2 | `kwargs["tools"] = [openai_tool_payload(t) ...]` | 2026-09-02 `7a0ab8d4` | root-cause investigation; had gone quiet **without being fixed** |
| 3 | `_stable_tool_list(list(visible or []))` | 2026-09-02 | AST scan; had silently killed that function's own preserve-branch |
| 4 | `tools=list(kwargs.get("tools") or [])` | 2026-08-11 `ae2ec35b` | multi-provider live smoke |

Four occurrences of one mistake is not carelessness, it is a design that invites
it. Hence a structural response rather than a fourth point-fix:

> **Proof carried as an attribute on a mutable value is lost by ordinary
> copying, and the loss is silent.** Python cannot prevent this: `list(x)`
> returning a plain list is language behaviour, not something a subclass can
> override. The countermeasures are therefore (a) one sanctioned conversion that
> checks and converts in the same call
> (`narrowed_tools.openai_tools_payload`), so a caller cannot get one without
> the other, and (b) a CI scan (`scripts/scan_narrowed_tools_strips.py`,
> enforced by `backend/tests/test_no_narrowed_tools_strips.py`) that fails on any
> rebuild reaching an attach site or blinding a preserver.

### Interaction with Class A

Instances 1 and 2 also sharpen "one layer too low": `65161f90` was a correct fix
applied one line too high, repairing the round-trip and leaving the conversion
immediately below it still stripping the marker. **Class A and Class C
compound** - a partial fix silences the remaining half, and that silence then
reads as success.

### Countermeasure that generalises

Guarding an invariant is not enough. The guard must be **exercised end-to-end
through the real call path**, or the plumbing between guard and provider is
unobserved. Mutation testing proved the point: before
`test_unified_turn_attaches_narrowed_tools.py` existed, the exact defect that
fired 109 times could be reintroduced with the entire suite green.

## Standing risk register

| Risk | Status | Owner |
|---|---|---|
| Grounding validation for connector-connected orgs | CLOSED at `ab7ca5a7`. Residual risk below, accepted | Cesar |
| Tool-aware validator proven on a thin sample only | ACCEPTED - n=5, one probe org, HubSpot only | Cesar |
| `_classify_error` labels internal bugs as user `validation_error` | OPEN, low priority, deferred by decision | unassigned |
| `unnarrowed_tool_attach_blocked` | **CLOSED 2026-09-02.** Four instances of one mistake, not one defect. Instance 1 fixed in prod since 08-13 (`65161f90`); instance 2 **LIVE PASS** - `BUG_REPRODUCED` pre-fix / `CLEAN` post-fix on a real `claude-sonnet-4-6` tool-carrying turn, guard at `provider_tool_router.complete_with_tools`, model chose `apollo_lists_list` post-fix; instances 3-4 fixed, no prod events. Mutations 6/6 + standing CI scan. See `unnarrowed-tool-attach-rootcause.md` | Cesar |
| Audit probe traffic pollutes production telemetry | KNOWN - 140 of 142 `outcome_error` events were this audit's own probes | unassigned |

## Coverage gap: closed, with the residual risk stated

Decision 2026-09-02 (Cesar): keep the tool-aware validator live and record it as
delivered, with the sample limitations carried as accepted residual risk.

Process note, recorded because it matters more than the outcome. The
instruction that arrived for this closing pass was to **defer** the tool-aware
validator as its own future project and to document the coverage gap as an
accepted temporary risk. By the time it arrived the validator had already been
built, deployed and live-proven. Rather than quietly keep the shipped work or
quietly revert it, the conflict was surfaced with the evidence on both sides and
the choice was made explicitly. Nothing here was decided by an agent's
preference.

**What is closed.** Every connector-connected org can now reach grounding
validation. `resolve_effective_intelligence_mode` sends them to `agent`, and
`agent` is in the default validation set, so the empty intersection that made
validation unreachable for those orgs no longer exists. Measured at `ab7ca5a7`:
5 tool-grounded runs where the previous 30-day window had zero, 5 of 5 judged by
the model, 0 fail-open events, 0 answers replaced, p50 1781ms.

**Residual risk, accepted rather than closed.** This is the part that must not
be read as stronger than it is:

- **Thin sample.** Five validator runs, from one probe org, against HubSpot
  only. That is enough to demonstrate the specific failure mode is fixed
  (RAG-only evidence rejecting correct tool answers). It is not a distribution,
  and it is a small basis for a check that gates user-facing answers.
- **Single connector shape.** Other connectors return differently shaped
  payloads. The 6000-char per-tool budget was sized against a ten-record HubSpot
  contact listing; a connector returning larger records could re-introduce the
  truncation-driven false rejection that cost 11.9s at `742414b9`.
  `evidence_truncated` is audited precisely so this is detectable rather than
  inferred.
- **Latency at scale unmeasured.** p50 1781ms was measured on a quiet probe org.
  Behaviour under real concurrent load is unknown.
- **Fail-open by design.** A model failure still waves the answer through. That
  is deliberate for a user-facing path, and `validator_fallthrough` now names
  the cause on every occurrence, but it means the validator is a best-effort
  safety net and not a guarantee.

**How this gets watched rather than forgotten.** The audit fields
`evidenceKind`, `toolResultCount`, `evidenceTruncated`, `assessorRan` and
`validatorFallthrough` on `answer.grounding.validated` are sufficient to answer,
from production data alone: is it running, is it judging, is it replacing
answers, and is truncation biting. Any future hardening project should start by
reading those rather than by re-deriving the problem.
