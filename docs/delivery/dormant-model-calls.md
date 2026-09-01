# Dormant model calls — silent no-ops in production

Standing record. Append-only; do not overwrite earlier sections.

A zero-argument factory called with an argument raises `TypeError` **before the
factory body runs**. Wrapped in `except Exception`, that becomes a silent no-op:
the capability is gone, nothing is logged above `debug`, and every test still
passes because the caller's fallback returns a valid-looking value.

Two confirmed instances were found by reading production traces, not by any
test:

- `verification_critic_service` — the **mandatory** critic pass, degrading to
  `mandatory_critic_error` on every turn (fixed in `ccc98167`).
- `unified_turn_knowledge_context` — customer RAG removed from the replan loop
  entirely. Live artifact at tip `ccc98167` shows
  `org_rag_error = "get_rag_service() takes 0 positional arguments but 1 was
  given"` on both evidence-bearing turns. The loop reported `org_rag` in
  `sources_tried` while that source had thrown instantly.

## Deferred, low priority — `_classify_error` mislabels internal bugs as user error

Raised 2026-09-01 during the HubSpot search investigation. **Not urgent, real,
and deliberately not folded into the dormant-call work.** Recorded here so it
is not lost; it deserves its own audit once the twelve sites are closed.

`tool_service._classify_error` is the connector-wide fallthrough for tool
exceptions. Transport faults and timeouts were being labelled
`validation_error` and were fixed at that chokepoint; see
`docs/delivery/hubspot-search-validation-dead-end.md`. What remains is the
broader case: an arbitrary internal exception — a `KeyError` in Gravitre's own
code, for instance — still classifies as `validation_error`, so **our bug is
presented to the user as their input being wrong**, across all 727 actions.

Why it was not fixed in that pass: separating "our fault" from "your input" for
arbitrary exceptions requires auditing what every caller actually raises, per
connector. Changing the default without that audit would alter user-facing
messages catalog-wide with no way to verify the result, which is the kind of
unverified bulk change this program has repeatedly found to be wrong.

Scope when picked up: enumerate the real exception types reaching
`_classify_error` from each connector, decide the correct classification per
type, and keep `validation_error` for genuine user-input faults only.

## Phase 0 — exhaustive inventory (2026-08-31)

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
`backend/scripts/probe_dormant_model_calls.py` →
`docs/delivery/dormant-model-call-runtime-probe.json`.

### Severity ranking

Ordered by correctness → safety/governance → user-facing quality.

| # | Site | What has been silently absent | Observed fallback | Severity |
|---|---|---|---|---|
| 1 | `answer_validator.py:74` | Grounding/hallucination check against retrieved context | `{is_valid: True, issues: [], requires_human: False}` — **fails OPEN** | ~~Critical — correctness~~ → **corrected to Low: dead code.** See Phase B — measured as never executing on live traffic (0 audits against 464 fallthroughs / 1454 turns in 30d), so nothing was being falsely certified |
| 2 | `unified_turn_knowledge_context.py:201` | Customer RAG retrieval in the replan loop | `org_rag_error`, 0 chunks | **Critical — correctness.** Org's own documents excluded from evidence |
| 3 | `agent_intelligence.py:931` | Regeneration of an ungrounded answer | Never reached — gated behind site 1 failing open | **High — correctness**, masked by site 1 |
| 4 | `schema_param_extractor.py:319` | Model extraction of connector action arguments | Heuristic-only args | **High — touches write actions.** Missing args → failed or under-specified writes |
| 5 | `pending_reply_classifier.py:500` | Comprehending approve/reject replies regex missed | `"ambiguous"` | **High — governance-adjacent.** Approval replies collapse to a re-ask |
| 6 | `conversation_turn_controller.py:273` | Comprehending continue/modify/cancel on a pending plan | `"unclear"` | **High — governance-adjacent** |
| 7 | `query_rewriter.py:52` | Resolving pronouns into standalone retrieval queries | Original query unchanged | **Medium — retrieval quality.** Follow-ups retrieve on the raw pronoun |
| 8 | `conversational_turn_gate.py:240` | Distinguishing small talk from casually-phrased data asks | Heuristics decide every turn, `used_model=False` | **Medium — quality/latency** |
| 9 | `domain_intelligence_service.py:208` | Model-based domain classification | `source: "rules"` | **Medium — routing quality** |
| 10 | `contextual_understanding_service.py:225` | Goal + constraint extraction | `{}` — always empty | **Medium — quality** |
| 11 | `clarification_engine.py:769` | Polishing clarifying questions | Unpolished draft | **Low — cosmetic** |
| 12 | `cache_warming_scheduler.py:48` | Warming embedding/retrieval caches | Throws per org; `queries_warmed=0` | **Low — performance only.** Already visible at `warning` |

Honest correction recorded: an earlier reading of site 8 assumed the fallback
was uniformly `task_shaped`. The runtime probe shows a heuristic layer sits in
front, correctly classifying both an obvious greeting and an obvious data ask
without the model. The dormant call is the *ambiguous middle*, which is a
narrower impact than first stated.

## Phase 1 — root cause and structural guard

### Root cause: NOT DETERMINABLE from available history

This repository's history is squashed — all 573 commits trace to `9b1d748c`,
and `model_router.py`, `answer_validator.py` and the rest each show exactly one
commit. `git log -S` finds no prior settings-accepting form of
`get_model_router` because no prior form exists in this history at all.

**The drift predates the available record.** No story about when or why the
signatures diverged is offered here, because none can be evidenced.

What *is* structurally established: `ModelRouter.__init__(settings=None)` does
accept settings, while the singleton accessor `get_model_router()` does not and
**cannot honor them** — the instance is built once and reused, so a
per-call `settings` argument would be silently discarded even if the signature
accepted it. Widening the factory would therefore encode a lie. The correct fix
is to keep it zero-argument and remove the argument at each call site.

### Structural guard — `backend/tests/test_no_dormant_model_calls.py`

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

Rule 2 found a **wider class than the 12 arity sites — 17 handlers** hiding
model failures below WARNING, including three logging nothing at all. All 17
raised to `warning` in this pass. Two required new log statements
(`consensus_engine`, `generative_agent_coordinator`); the latter turned out to
call `ModelRouter(self.settings)` correctly and had only the silent-`pass`
problem, not an arity bug.

This change is observability-only: no control flow, fallback values, or model
behavior altered.

## Phase 2 — site 1 + 3 (grounding validator and regeneration)

Fixed together, not as a batch of convenience: the validator failing open is
precisely what made the regeneration `TypeError` unreachable. Fixing the
validator alone would have converted a silent no-op into a **hard turn failure**,
because `agent_intelligence.py:972` calls `_regenerate_grounded_answer` outside
any `try`. Repairing one without the other leaves production strictly worse.

Changes:

- `answer_validator.py:74` — `get_model_router()`.
- `agent_intelligence.py:931` — `get_model_router()`, plus a handler so a
  regeneration failure returns `""` and lands on the caller's existing
  `SAFE_FALLBACK` branch rather than raising. This path has never executed in
  production, so it is newly exposed and should degrade, not 500.

### Severity correction (honest)

The Phase 0 table called this "every answer declared grounded". That overstates
it. `validation_enabled_for_mode` gates the check: it requires
`validation_enabled`, and by default covers only `standard` and `reasoning`
modes (`speed_priority` narrows it further to `reasoning`/`agent`). The accurate
claim is **every _validated_ answer was declared grounded without a check** — a
smaller blast radius than first written, still a failed correctness gate.

### Before baseline — `docs/delivery/validation-stage-latency.json`

`ai_pipeline_latency` where `stage_name='validation'`, 30-day window, captured
before deploy: **1 sample, 0 ms**. A swallowed `TypeError` returns in about a
millisecond; a real model call does not, so 0 ms is consistent with the no-op.

Two honest limits on that figure. n=1 is thin. And the latency row is only
written when `message_id` is present, so 1 is a **lower bound on invocations,
not a count of them** — it does not establish how often the validator was
reached, only that where it was recorded, it took no measurable time.

### After — live run at deployed tip `9ca96dc2`: PARTIAL, execution NOT CONFIRMED

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
  row, which is consistent with `message_id` being absent on this path — in
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

### Second live run at `9080bc87` — root of the non-confirmation found

An `answer.grounding.validated` audit event was added so execution could be
observed without depending on `message_id`. Its decisive field is
`confidenceSource`: `"model"` means the assessor genuinely judged, `"heuristic"`
means the call fell through to the permissive default.

The re-run produced **zero such events**, and the reason is structural, not a
missing signal. Both turns were handled by `unified_turn.live.completed`:

```
grounding_pressure  d5a32ae1…  unified_turn.live.completed  2026-09-01T00:07:38Z
grounded_control    c3199c6d…  unified_turn.live.completed  2026-09-01T00:07:53Z
```

The grounding validator is called from
`agent_intelligence._finalize_assistant_response`, which sits on the ReAct
finalize path. Production chat traffic takes the **unified turn** path and only
reaches ReAct on `unified_turn.live.fallthrough` — an event that does appear in
this org's history, but did not fire on either of these turns.

### Consequence for the Phase 0 severity ranking (second correction)

Site 1 was ranked **Critical — every validated answer declared grounded without
a check**. That ranking assumed the validator sits on the main answer path. It
does not. Its real reachability is narrower still: validated modes
(`standard`/`reasoning`) **and** a unified-turn fallthrough.

This does not make the fix wrong — a grounding gate that fails open is a real
defect and is now repaired. But the honest reading is that the capability was
absent from a **narrower slice of traffic** than the original ranking implied,
and that a separate, larger question is now open: whether the grounding check
should be on the unified turn path at all, given that is where real traffic
goes. That is a design question, not a signature bug, and is not decided here.

Live execution of site 1+3 therefore remains **NOT CONFIRMED**, with the reason
now known: the proof requires a turn that reaches ReAct finalize, which these
did not.

### Third attempt — fallthrough forced, blocked by a stale approval hold

A connector-read query did force the intended route:

```
forced_react_fallthrough  actions=[pending_reply.classified,
                                   unified_turn.live.fallthrough]
                          reached_react=True  reason=read_tool_classical
```

Still zero grounding audits, because that turn was intercepted by a pending
approval — `"I still have **Create list** waiting for approval."` — which
short-circuits before answer generation.

I read that as a stale, org-scoped hold surviving `cancel`, and recorded it as a
separate blocking defect. **That diagnosis was wrong.** See the retraction below;
it is left in place rather than edited out because the way it went wrong is the
useful part.

**Site 1+3 status at this point: SHIPPED and DEPLOYED at `9ca96dc2`
(observability at `9080bc87`), live execution NOT CONFIRMED**, one real blocker:
the validator is not on the unified-turn path real traffic uses.

### Retraction — there is no stale approval hold

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
  actually describes — one conversation, hold created, `cancel` in the **same**
  conversation, then a genuinely new conversation. **PASS on all four checks:**
  the hold was created (`Create list status=awaiting_confirm`), `cancel` cleared
  it in the database, the follow-up turn showed no hold prompt, and the fresh
  conversation started clean.

Two compounding mistakes produced the false report. The probe opened a new
conversation per turn, so `cancel` landed on a conversation that never had a hold
while a later turn created one of its own — and `format_pending_meta_answer`
phrases a hold as `"I **still** have X waiting for approval"` even on first
mention, so a brand-new hold reads like a surviving one. Neither the code nor the
data ever said the hold survived; the prose did, and I believed it.

Guarded by `backend/tests/services/test_pending_hold_does_not_survive_cancel.py`
(10 tests). The terminal-clearing half is mutation-proven: disabling the
`pending_status in {"completed","failed","cancelled"}` branch in
`conversation_turn_controller` fails 3 of them.

### Phase B — the validator is not on the live answer path, and site 1's severity was overstated

With the phantom blocker gone, the reachability question was asked directly
instead. `scripts/probe-grounding-validator-reachable-shape.py` swept four turn
shapes chosen to avoid the early returns that pass `validation=None` — a factual
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
"a fallthrough path most production chat traffic never takes" — wrong, about a
third of turns fall through. But fallthrough does **not** mean reaching ReAct
finalize: the 30-day reasons are `pending_family_classical_resume` (144),
`outcome_error` (142), `defer_classical_tool_sse` (141), and
`read_tool_classical` (37), and the branches that serve them return before the
finalize call, several passing `validation=None` explicitly. 464 fallthroughs
produced 0 grounding audits.

**Site 1's severity was overstated and is corrected here.** The Phase 0 table
calls it "Critical — correctness. Every answer declared grounded with no check."
That framing assumed the validator ran and rubber-stamped answers. It did not run
at all on any observed live path, so nothing was being falsely certified. The
honest finding is *dead code*, not a defeated safety check.

Nor is the live path ungrounded. Both pressure questions were refused honestly by
the unified turn on its own: *"I don't have enough information to substantiate an
exact guaranteed number from the internal documents you provided."* Grounding
discipline exists where traffic actually flows — it simply is not this validator.

**Site 1+3 status: signature fix correct, SHIPPED, DEPLOYED, and NOT EXECUTING,
because the path it lives on is not reached by live traffic.** The remaining
question is a design one — whether the unified turn should call this validator,
or whether it should be retired in favor of the grounding behavior the unified
turn already has. That is a product decision, not a signature bug, and is not
decided here.

## Phase 2 — site 4, `schema_param_extractor.py:319` (PARTIAL)

Taken next as the highest-severity remaining site, and because it turned out to
be directly relevant to the fabricated-write finding: this extractor's own prompt
says *"Return ONLY keys that have a confident value. Do not invent ids."* While
it was dormant, the only things filling connector arguments were regex heuristics
and pack defaults — precisely the path that invents
`{"name": "MSPs", ...}` in
[`readonly-destructive-proposal.md`](./readonly-destructive-proposal.md).

Fix: `get_model_router(settings or get_settings())` → `get_model_router()`.

**Proven** (`backend/scripts/probe_site4_schema_param_extractor.py`), with the
pre-fix call shape re-created deliberately so the result cannot be mistaken for
something that always worked:

```
get_model_router(settings) -> TypeError: takes 0 positional arguments but 1 was given
get_model_router()         -> OK — ModelRouter
```

**Not proven: that the model call adds arguments heuristics miss.** Two messages
hiding the list name in prose ("we've been calling the segment Northeast
Renewals") returned `{}` from both the heuristic and the model-backed path. That
is a limitation of the probe, not evidence about the fix: with no connector schema
registered in a bare local context, `_schema_field_keys` returns no fields, so
`required_missing` is empty and the function returns before reaching the model at
all.

### Resolved 2026-09-01 — INCONCLUSIVE superseded by PASS

The INCONCLUSIVE above came from a probe limitation, not from the fix. Correcting
the probe resolved it. `backend/scripts/probe_schema_param_extractor_live.py`
first enumerates the real catalog for actions that genuinely have a workflow
schema with required fields, then constructs a message that leaves a required
field empty, which is what the earlier probe never achieved.

The dormancy claim is about control flow — was the router entered — so it is
decidable without AI credentials. `probe_schema_param_extractor_before_after.py`
runs the real extractor twice on the same input, restoring the original buggy
call for the first pass (`docs/delivery/schema-param-extractor-before-after.json`):

| | Router entered (`MODEL_CALL_START`) | Handler logged |
|---|---|---|
| before | **no** | `get_model_router() takes 0 positional arguments but 1 was given` |
| after | **yes** | `All AI providers failed (…not-configured)` — local env only |

Status: **PASS on the dormancy defect.** The call reached the router on a real
invocation; before the fix it could not, and the failure was invisible.

Still open, and deliberately not rounded up: whether the model then contributes
arguments the heuristics miss. That is a capability question, not a dormancy
one, and it is unmeasurable in this environment — no AI provider is configured
locally (openai, anthropic and gemini all report unavailable), so the call
reaches the router and can never receive a completion. Production only.

Recorded while probing, not fixed: for a vague message the heuristic pass fills
`hubspot.contacts.create`'s `firstname` *and* `lastname` with the entire user
message. Same argument-invention pathology as
[`readonly-destructive-proposal.md`](./readonly-destructive-proposal.md).

## Phase 2 — site 5, `pending_reply_classifier.py:500` (PASS on dormancy)

Fix: `get_model_router(settings or get_settings())` → `get_model_router()`.

What was silently absent: `classify_pending_reply` runs a regex fast path first
and only calls the model when that returns `None`. With the call dormant, every
reply the regex could not classify returned `"ambiguous"`, so the assistant
re-asked instead of reading the conversation. It **failed safe** — asking rather
than guessing an approve or reject — which is exactly why it was never noticed
on a governance-adjacent path.

Before/after on the same input, buggy call restored for the first pass
(`backend/scripts/probe_pending_reply_classifier_before_after.py`,
`docs/delivery/pending-reply-classifier-before-after.json`). The reply used is
*"hold off on that for now, I want to check the numbers with finance first"* —
against a real `awaiting_confirm` hold, with the regex fast path confirmed
returning `None`, so comprehension is the only route to a correct label:

| | Regex fast path | Router entered | TypeError | Intent returned |
|---|---|---|---|---|
| before | `None` | **no** | yes, swallowed at WARNING | `ambiguous` |
| after | `None` | **yes** | no | `ambiguous` (no AI provider configured locally) |

Status: **PASS on the dormancy defect** — the classifier now reaches the model
router on a reply the regex cannot handle.

### Live production proof — PASS

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

- **0 `lists.create` invocations** — no soft deferral was read as approval. This
  was the check that mattered most; comprehending a deferral as a yes would be
  far worse than re-asking.
- **0 generic "waiting for your approval" re-asks** — the signature of the
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
the model never gets to correct it — a wrong regex verdict is more harmful than
no verdict, and this one predates the dormancy fix.

Baseline: `pending_reply_classifier.py:500` removed from `KNOWN_DORMANT`, guard
test green (2 passed). Five of twelve sites now closed.

### Superseded — the "unreproduced" observation below is now REPRODUCED

Investigated properly in
[`readonly-destructive-proposal.md`](./readonly-destructive-proposal.md).
**4/4 on the exact phrasing**, deterministic, safety-relevant, unfixed. It is not
contamination: "MSPs" is `DEFAULT_HUBSPOT_LIST_NAME`, a deliberate pack default,
and the real defect is that ReAct selects a destructive create tool for a
read-only request. `APPROVAL_ACTION_MISMATCH` was tested against the claim and
**would not catch it** — proposed and executed actions are identical.

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

## Phase 2 — site 6, `conversation_turn_controller.py:273` (PASS on dormancy)

Fix: `get_model_router(settings or get_settings())` → `get_model_router()`.

`_model_pending_intent` has two callers inside `classify_pending_plan_intent`,
with different fallbacks:

| Caller | Condition | Fallback when the model contributes nothing |
|---|---|---|
| modify-hint branch | `re_modify_hint(text)` matches | **`"modify"`** |
| general branch | a plan or pending task exists | `"unclear"` |

`re_modify_hint` fires on `don't`, `dont`, `without`, `instead`, `just`, `only`,
`skip`, `change`, `rather`. So a reply that plainly means *cancel* but contains
one of those words was classified as a request to **modify** the plan.

### Correction — the severity claim I first wrote here was wrong

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

So this path only runs for an **orphan strategic plan** — a `current_plan` left
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
   *"…different direction now (regarding plan: Create a HubSpot list of MSP
   prospects…)"* — the abandoned goal pushed into the very turn that rejected it.
2. **Forced re-ask.** Everything else fell to `unclear` and got the
   "abandon or hold" prompt instead of being understood.

Neither is a stuck destructive plan. Consequence 1 is still a genuine defect,
and it fails toward *carrying unwanted intent forward*, not toward safety.

### Possible link to the "MSPs" contamination, explicitly not proven

Consequence 1 is a real mechanism that injects a stale goal string into a later
turn's prompt, and the contamination observed earlier in this task surfaced the
token `"MSPs"` from prior marketplace testing. The shapes match. That is a
**hypothesis, not a finding** — no trace ties the observed contamination to this
code path, and it is recorded here only so the connection is not lost. It should
not be cited as the cause of that incident without its own evidence.

### Before/after, buggy call restored for the first pass

`backend/scripts/probe_conversation_turn_controller_before_after.py`,
artifact `docs/delivery/conversation-turn-controller-before-after.json`.
Against a real orphan strategic plan (`hubspot.lists.create` +
`lists.add_members`), matching the shape the production caller requires:

| Reply | | Router entered | TypeError | Intent |
|---|---|---|---|---|
| "don't bother with that…" (modify hint) | before | **no** | yes, swallowed at WARNING | **`modify`** — stale goal injected |
| | after | **yes** | no | `modify` (no AI provider configured locally) |
| "hold off, I need to run this past our finance lead…" (no hint) | before | **no** | yes, swallowed at WARNING | `unclear` |
| | after | **yes** | no | `unclear` (same reason) |

The swallowed line, verbatim:

```
WARNING: pending plan intent model skipped:
  get_model_router() takes 0 positional arguments but 1 was given
```

After the fix the same handler logs *"All AI providers failed (openai:
unavailable/not-configured; …)"* — the router is genuinely entered and fails on
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

`backend/tests/services/test_pending_plan_intent_honors_model.py` — 11 tests.
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

### Live production proof — PASS

`scripts/verify-pending-plan-intent-live.py` against deployed tip
**d57b48c36853b8cb066f04a205c5df8acd66ad16**, org
`f07e57c0-1501-4000-8000-c04e57a00001`
(`docs/delivery/pending-plan-intent-live.json`).

The scenario seeds the exact state the one production caller requires — a
`current_plan` with a goal and **no** `pending_task` — directly in
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
Two independent observations rule that out — the prompt never appeared, and
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
  That is deliberate — it is the only way to hit a caller gated on
  plan-without-pending-task — but it means this proves the mechanism works, not
  that real traffic reaches it. The reachability rate is still unmeasured.
- The two answers read as correct comprehension, but the final answer is
  model-generated regardless, so the reply *text* is not itself evidence about
  the classifier. The load-bearing evidence is the branch discrimination above,
  not how sensible the wording sounds.

## Phase 2 — site 7, `query_rewriter.py:52` (PASS on dormancy)

Fix: `get_model_router(settings)` → `get_model_router()`.

What was silently absent: `rewrite_for_retrieval` turns a context-dependent
follow-up into a standalone search query. Its one production caller,
`agent_intelligence.py:2610`, feeds the result straight into
`prepare_assistant_turn(query=refined_query)` — so its output **is** the query
the whole turn retrieves against, for RAG, Knowledge Fabric and hybrid search
alike.

While dormant it returned `refined_query == original_query` every time. So for
every context-dependent follow-up in every non-`fast` mode, retrieval searched
on the raw text. *"and what about their renewal?"* went to the index exactly
like that, with `their` unresolved and `Acme Corp` — the only useful search term
in the exchange — never reaching it.

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
| after | **yes** | no | unchanged — no AI provider configured locally |

```
WARNING: query rewrite skipped org_id=probe-org
  error=get_model_router() takes 0 positional arguments but 1 was given
```

Note the trap in reading this table: `refined == original` is also the *correct*
fallback, so the returned string alone cannot distinguish "dormant" from
"working but declined". Router entry is the discriminator locally — and in
production that ambiguity is now resolved by the audit field below.

### New finding — the existing test could never have caught this

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
because the countermeasures differ — the first needs live re-verification after
deploy, this one needs fakes that enforce the real signature.

Every fake in the new suite therefore asserts the factory is called with zero
arguments.

### Production observability added

A dormant rewriter and a model that declines to rewrite return byte-identical
results, which is precisely why this sat unnoticed. Following the precedent set
for the grounding validator, the caller now writes a
`retrieval.query.rewritten` audit event carrying **`modelRan`** — true only
after `router.complete` returns — alongside `changed`, `modeKey`, and
`historyTurns`. `rewrite_for_retrieval` returns the new `model_ran` key to
support it.

Two mutations exist specifically to stop that field lying: one sets it to `True`
unconditionally, one sets it before the call completes. Both are caught.

### Standing regression test

`backend/tests/services/test_query_rewriter_reaches_model.py` — 14 tests.
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

### Live production proof — UNREACHED, not PASS

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
| connector read follow-up (HubSpot deals → close dates) | standard | 1 / 1 `read_tool_classical` | **no** |
| reasoning-mode analysis follow-up | reasoning | 2 / 0 | no |
| research-scope follow-up | standard | 2 / 0 | no |
| CRM entity follow-up (Acme → open deals) | standard | 1 / 1 `read_tool_classical` | **no** |

The two bolded rows are the informative ones. They **did** fall through
unified-turn-live, which was the hypothesised prerequisite, and still did not
reach the rewriter. So fallthrough is necessary but not sufficient: the
connector-turn block returns at line 2606, ahead of the rewriter at 2610. Eight
early returns sit between the unified-turn call and the rewriter.

Production fallthrough reasons over 30 days, n=512
(`docs/delivery/unified-turn-fallthrough-reasons.json`) — two of the four were
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
happens" — which is the same lesson as the HubSpot transport fix and the
fabricated-write gate.

### The bigger finding — the classical answer path may be largely dead

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

## Phase 2 — customer RAG (`get_rag_service`, both sites)

Chosen next over the remaining severity order because this one sits on the
unified turn path that production traffic actually uses, and because it is the
only site with a pre-existing live trace of its own dormancy.

- `unified_turn_knowledge_context.py:201` — `get_rag_service()`. Restores
  customer RAG to the replan loop. Previously `org_rag_error` on every turn.
- `cache_warming_scheduler.py:48` — `get_rag_service()`. Cache warming threw per
  org before warming anything; already visible at `warning`, so this one was
  never silent, only broken.

Before evidence, already on record from the replan-loop artifact at tip
`ccc98167`: `org_rag_error = "get_rag_service() takes 0 positional arguments but
1 was given"` with `org_rag_chunk_count = 0` on both evidence-bearing turns.
The pass condition is the disappearance of that key on a live turn.

### PASS — live at deployed tip `db928881`

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
was genuinely reached on the same run where the error key is gone — the absence
is the call succeeding, not the branch being skipped.

Honest limit on this PASS: `org_rag_chunk_count` is still `0`. The isolated
conversation org has no customer documents, so what is proven is that the call
**executes and returns cleanly** instead of throwing. It does not prove customer
RAG returns useful evidence, which would need an org with a real corpus. Stated
so this is not read as more than it is.

Cost: no measurable latency change. The rich turn ran 32.1s against 32.9s on the
before-run, which is well inside run-to-run variance for a 3-round loop, and the
call it replaces previously failed instantly — so the true added cost is one RAG
query per loop round, unmeasurable here because the corpus is empty.

**Status: both `get_rag_service` sites FIXED and LIVE-CONFIRMED at `db928881`.**
