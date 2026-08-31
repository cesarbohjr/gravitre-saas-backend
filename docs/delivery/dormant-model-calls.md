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
| 1 | `answer_validator.py:74` | Grounding/hallucination check against retrieved context | `{is_valid: True, issues: [], requires_human: False}` — **fails OPEN** | **Critical — correctness.** Every answer declared grounded with no check |
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
