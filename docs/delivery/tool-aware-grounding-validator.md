# Tool-aware grounding validator

Closes the coverage gap where every connector-connected org received no
grounding validation at all. Cesar's decision (2026-09-02) was to build a
tool-aware validator rather than accept the exclusion.

## The gap

`resolve_effective_intelligence_mode` upgrades **both** `standard` and
`reasoning` to `agent` whenever a connector is connected, and leaves `fast` as
`fast`. A connector-connected org can therefore only ever reach `{fast, agent}`.
The default validation set was `{standard, reasoning}`. The intersection is
empty, so grounding validation was unreachable for every org with a connector —
zero `answer.grounding.validated` events across the whole measurement window.

Neither half of that is wrong on its own. The gap only exists in the
composition, which is why it survived so long and why the composition is now
pinned in `tests/services/test_grounding_validation_reaches_real_orgs.py`.

## Why the first attempt failed

Adding `agent` to the set was tried at `1e94e644` and reverted the same day:

| | 1e94e644 (RAG-only validator) |
|---|---|
| latency added | p50 9309ms, p95 10131ms (generation baseline 3123ms) |
| answers replaced | **3 of 3**, one landing on `SAFE_FALLBACK` |

Structural, not tuning. `agent` is the mode where answers come from **tools**
while RAG chunks are incidentally present, so the validator compared a
tool-derived conclusion against unrelated knowledge snippets and correctly found
it unsupported. A real HubSpot search result was declared ungrounded because
five unrelated documents did not mention it.

## The fix

`build_evidence` unifies retrieved chunks and executed tool results into one
evidence list. Tool results are marked authoritative in the prompt; failures are
included deliberately so a claim that an action succeeded can still be caught
against a `FAILED` result. `has_context` now means documents **or** tool results.

The regeneration path receives the same evidence. That half is easy to forget
and worse to get wrong: rewriting a tool-derived answer from unrelated documents
produces a fluent, confident, wrong answer, which is worse than the rejection it
replaces.

## Two instrument bugs found on the way

**`assessorRan` was always false.** It compared `confidence_source` against the
literal `"model"`, while `CONFIDENCE_SOURCE_MODEL` is `"loaded_model_artifact"`.
Every `answer.grounding.validated` event ever written said `assessorRan=false`,
including events where the assessor had genuinely judged. The first live run
read "0 of 3 fell open" off this field and the reading was pure artifact — it
would have led to abandoning a working validator. Same class as the
`actor_id=None` bug. Checked class-level: no other production comparison against
the literal.

**Fail-open was silent.** `validate_grounded_answer` swallows any failure into a
permissive `is_valid=True`. Failing open is right for a safety check on the
user-facing path — a model hiccup should not turn a correct answer into an
apology — but a fail-open that does not *say* it failed open is
indistinguishable from a validator that works. It now returns
`validator_fallthrough` naming the cause (`model_error:<type>`,
`no_json_in_response`, `empty_response`, `json_decode_error:<type>`) and the
audit records it.

## Truncation was manufacturing false rejections

At `742414b9` the validator worked (assessorRan 3/3, fallthrough None) and two of
three answers passed in ~1.4s. The one still replaced was the largest payload:
"list my hubspot contacts" returned ten records and the answer enumerated all
ten, but the 2000-char tool budget cut the tail, so the validator could not see
the records the answer named. Regeneration cost 11.9s to recover an answer that
was correct to begin with.

Per-tool budget raised to 6000 chars with a 14000-char total ceiling so a
multi-tool turn cannot balloon the prompt. Truncation is marked `[TRUNCATED ...]`
and the prompt instructs the model to treat truncated evidence as **incomplete,
not contradictory**. `evidence_truncated` is audited so this stays a measurement.

## Live result — PASS at `ab7ca5a7`

Two probe runs, `docs/delivery/tool-aware-grounding-live.json`:

| | 1e94e644 (before) | ab7ca5a7 (after) |
|---|---|---|
| validator runs on agent mode | 0 in 30 days | 5 across two runs |
| judged by the model | n/a | 5 of 5 |
| fail-open events | unmeasurable | 0 |
| answers replaced | 3 of 3 | **0 of 5** |
| latency added | p50 9309ms / p95 10131ms | **p50 1781ms, max 3713ms** |

Evidence kind was `tool+doc` on all five, `mode=agent` on all five — the mode
that previously had zero coverage.

### Honest caveats

- Five runs is a small sample, and all from one probe org against HubSpot. It
  demonstrates the failure mode is fixed; it is not a distribution.
- One probe turn produced no validation event because the model hit progressive
  disclosure (`full_schema_not_loaded`) and never called a tool. That is a
  separate issue and is not evidence about the validator.
- The probe's connector line prints `0 connected` because it filters on
  `status='connected'` while these rows evidently carry another status value.
  The authoritative confirmation is `mode=agent` on the audit rows, not that
  line.
- Total wall time per tool turn remains 33–46s. The validator is now a small
  fraction of that; the rest is tool execution and generation, and is untouched
  by this work.

## Tests

- `tests/services/test_tool_aware_grounding_validator.py` — 24 tests
- `tests/operators/test_finalize_passes_tool_evidence.py` — 13 tests, the
  call-site wiring
- `tests/services/test_grounding_validation_reaches_real_orgs.py` — the
  composition that hid the gap
- `tests/test_intelligence_engine_gaps.py` — 3 tests here had been failing on
  `main` since `user_id` became required on `_finalize_assistant_response`,
  leaving the regeneration and safe-fallback paths unguarded. Repaired.

Mutation-proven 12/12 via `scripts/mutate_tool_aware_validator.py`. One blind
spot was found and closed during that process: a structural source check for
`build_evidence` and `tool_calls` in the regeneration path passed even when the
body discarded the tool evidence, so it now asserts on the real prompt.
