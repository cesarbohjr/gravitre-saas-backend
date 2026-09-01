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
