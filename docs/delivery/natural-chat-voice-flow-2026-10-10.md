# Natural chat and voice: dialogue repair and task status

## Problem and resulting behavior

The live Gmail conversation exposed two issues in addition to voice quality:
runtime acknowledgments repeatedly sounded like a lookup, and a retry saying
"the email" was intercepted by a prior-write status matcher. Open-ended social
remarks could also receive a generic greeting instead of a contextual reply.

This change extends the existing Intent Gateway, conversational tier, shared
behavior instructions, action lifecycle, and Pipecat speech bridge. It adds no
controller, business-reasoning path, schema, dependency, provider, or model.

Implemented behavior:

- A full-message apology such as "Sorry" receives "No problem" without consuming
  approval, cancelling the draft, or invoking a provider. It cannot become public
  research because internal retrieval was thin. A prefix such as "Sorry, send
  it now" does not use this shortcut; the actual request retains existing gates.
- "The email" is no longer evidence of a post-action status/identity question.
  The reproduced retry falls through to the existing task handler. An identity
  question without a prior observation also stays with that handler. Ordinary
  questions such as "Did you understand me?" or "Did that make sense?" are no
  longer interpreted as action status merely because they start with "did you".
- Status responses use ordinary language and preserve the difference between
  missing details, approval, execution, uncertainty, acceptance, and verification.
  An email is no longer described as a created contact. Unknown outcomes do not
  become claims of success or failure.
- Thanks and banter no longer automatically redirect the user into a new job.
  Open-ended small talk and an immediately repeated stock greeting fall through
  to the existing contextual reasoning path. Standalone greetings stay quick.
- The voice acknowledgment pool no longer says "Sure, let me look" or "Yeah,
  one sec." A pure apology gets no extra timed acknowledgment. Existing delay,
  guardrail settlement, cancellation, answer-first handling, and filler labels
  remain in force.
- Generic knowledge-base lookup narration/counts are silent; genuine business
  tool progress and execution feedback remain available. This changes speech
  presentation, not retrieval, tool permissions, or execution.
- Shared instructions ask for the next missing detail, retention of established
  task facts, context-sensitive repairs, and natural small talk. These are model
  instructions, not proof that every draft/revision transition is implemented.

## Evidence and validation

Base: c869f04a420a855807bfd65b0198e372b461e6e6 (PR #353).

New regression coverage includes the exact live retry, social repairs in typed
and spoken modes with pending details/approval, mixed apologies and real jobs,
thin-context public-research exclusion, contextual small talk, unknown status,
and speech-bridge delivery with internal retrieval followed by the useful answer.

Initial combined validation: 381 tests passed across dialogue, lifecycle,
research/tier routing, interrupt intents, segment labeling, silence guard, and
tool narration. After the final identity-query change, 102 targeted tests passed,
including natural-dialogue regressions and the Phase A, traffic, and action
execution business benchmarks. The new natural-dialogue module contains 46 tests.

Broader validation: 1,518 voice/shared tests passed with one replay-deadline
test explicitly deselected after it also failed on unchanged main. That test
was then isolated from irrelevant remote budget/moderation I/O; its unchanged
ordering/deadline assertions passed, as did all 64 tests in its replay module.
Final action-status/dialogue/tier/gateway validation: 227 tests passed.

Cognitive regression suite (including pending-reply, council, kernel, and
evidence pytest): passed. Confidence-honesty and smoke-isolation lints: passed.
Changed-source fatal Python lint and patch whitespace checks: passed.

GitHub CI is pending for the final revision; this is a draft PR.
No live email was sent; no microphone/browser/mobile audio benchmark was run.
No end-to-end latency or acoustic-naturalness improvement is claimed.

## Rollout and remaining work

Keep the existing stack, reasoning budgets, tool/approval authority, commit
gates, cancellation contracts, and execution records. No model call is added to
acoustic events or to the pure-apology shortcut. Contextual small talk uses the
existing kernel instead of a fixed answer, so its latency must be measured;
this is not a promise that every previously canned social reply remains instant.

This PR does not close the complete earlier audit: email requests can still need
better intent-aware retrieval routing; duplicate upstream final answers need
ownership tracing; state-read fallback and late memory cancellation require their
own correctness fixes. Physical playback history, effective rollout flags,
task persistence across reconnect, action outcomes, and voice selection still
need validation. Existing pending-task handling owns provider/recipient/body
collection; these changes do not create a separate draft coordinator.

Before deployment, replay the supplied conversation on the same baseline and
candidate. Include provider and recipient corrections, "no", "yes… wait", a
successful approved test send, an uncertain provider outcome, apology during a
pending task, repeated interruptions, and a complex business request. Compare
first useful played audio, completion time, interruption-to-silence, retained
constraints, correct effects, and voice quality. Count filler separately.

Deployment requires owner approval after reviewable work and validation. Rollback
is reverting this commit; there is no migration or new setting.
