# Phase 2 ordered completion ledger

The authoritative scope is `docs/roadmaps/voice-one-brain-phases-2-3.md`, which
contains ten workstreams. Earlier summaries grouping these into eight must not
omit clarification, expressive prosody or the engine benchmark.

Work advances in roadmap order. A code/test increment is not full certification.
No row below is a production completion claim.

| Order | Workstream | Current source evidence | Outstanding acceptance |
| --- | --- | --- | --- |
| 1 | Contextual intent, subtext, sarcasm, humor, indirect requests, ambiguity | `dialogue_interpreter.py`, kernel, shared compiler and prompt consumers; contextual policy now applies even without lexical cues | Generated-response scenarios, all role/channel paths, standing live batteries, CI and deployed evidence |
| 2 | Emotional/social awareness and boundaries | Advisory cues and Module D registers exist | Audit implementation gaps; proportionate boundaries, false-positive and live response evaluation |
| 3 | Natural turn-taking | Existing Pipecat turn controller, silence, overlap, cancellation and acknowledgement implementations | Audit both transports; run regressions and provider/device acceptance |
| 4 | Memory/session continuity | Session continuity and opt-in kernel recall/learn policy | Organization configuration, flag activation after deployment, live isolation/retention evidence; non-kernel paths retain separate contracts |
| 5 | Adaptive communication | Existing personas, spoken register and depth controls | Audit dynamic tone/depth/expertise/pacing and consented preference consumers |
| 6 | Clarification, repair, uncertainty, recovery | Clarification engine/policy, dialogue repair cues | Validate consequential ambiguity, nonredundant questions and error recovery across consumers |
| 7 | Prosody and multilingual switching | Existing TTS profiles and voice language configuration | Audit text/voice switching and content-aligned expression; actual audio for all three profiles |
| 8 | Human escalation | Existing dialogue escalation mode; agent handoff bus is not human delivery evidence | Verify governed human routing, summaries, recipient authorization and actual delivery |
| 9 | Outcome evaluation and private observability | Existing dialogue rubric, turn traces and outcome loop | Cross-role live quality matrix, adversarial/multilingual cases, privacy and performance evidence |
| 10 | Swappable Pipecat engine and benchmark | Existing engine interface and conservative benchmark comparator | Paired real-provider measurements, reliability/cost evidence and adoption decision |

## Workstream 1 source increment

The canonical kernel now supplies a fixed contextual interpretation policy on
all non-skipped turns, including neutral and implicit wording with no lexical
cue. The existing reasoning call interprets semantics using its authorized
message, session history and retrieved context. No second model, intent router,
inferred sarcasm label, conversation persistence or write authority is added.

The policy covers indirect requests; absent/multiple referents; latest correction
precedence; capability questions, hypotheticals, quotation and brainstorming;
implicit humor/sarcasm without guessed inversion; focused clarification where
consequences differ; and uncertainty without gratuitous questions. Existing
lexical cues remain tentative and optional. Fixed instructions and allowlisted
cue telemetry contain no transcript excerpts or inferred semantic labels.

`test_contextual_dialogue_contract.py` crosses twelve scenarios with text/voice
and every existing `AGENT_PERSONAS` entry. It exercises the real kernel/compiler
and the spoken-write classifier, verifies scoped continuity and unchanged state,
and checks that no ambiguous scenario authorizes a write. These are propagation
and denial contracts, not model-generated response evaluation or certification
of each complete agent ingress. `test_dialogue_cognitive_integration.py` now
requires neutral turns to retain contextual policy instead of an empty section;
its prior cue, privacy and governance assertions remain intact.

Local focused result: 299 tests passed, one existing Starlette deprecation warning.
Full Phase 2 status: INCOMPLETE. No merge, deploy, customer consent or live
certification has been performed by this increment.

## Workstream 2 source increment and Workstream 3 test isolation

Shared conversational behavior now distinguishes direct emotional disclosure
from quoted, hypothetical, negated and third-person language; prevents inferred
emotional profiling and social-pressure consent; and defines proportionate
boundaries without treating ordinary profanity or disagreement as harassment.
This system section is already consumed by unified text/voice, classical prompts
and the response composer. The cue extractor masks quoted spans and omits
reported/hypothetical emotional sentences while preserving later direct cues.

Local focused result: 356 contextual, social-policy and natural-dialogue tests
passed. This does not assess the actual generated response to harassment or
certify emotional intelligence.

The natural-turn subset initially exposed unit fixtures reaching real provider
moderation. Automatic approval review blocked an attempted OpenAI connection;
no live quality evidence is claimed. The silence and cancelled-output fixtures
now inject a local successful guard and local base prompt, retaining all timing,
output and cancellation assertions and additionally asserting the guard was
awaited. This changes test isolation, not runtime guard behavior. The dedicated
shared-guard refusal/concurrency tests run alongside them. Isolated result:
73 tests passed. Real microphone, speaker, acoustic overlap and provider quality
remain NOT RUN; these tests do not substitute for them.

Full CI is running through draft PR #587. Do not interpret a submitted or running
check as green, and do not advance the completion status without its result.

Combined isolated regression result after these changes: 1,179 tests passed
(with three existing dependency deprecation warnings). A subsequent quote-parser
edge case adds coverage for single-quoted contractions; rerun recorded in PR.
Railway OAuth inventory confirms ANTHROPIC_API_KEY, OPENAI_API_KEY,
DEEPGRAM_API_KEY and ELEVENLABS_API_KEY names are configured in production,
but values are redacted. Inventory is not authentication or provider acceptance.
DIALOGUE_MEMORY_GOVERNANCE_V1 was not listed. No variable was changed.

Final combined rerun after the single-quoted contraction regression: 1,180 tests
passed (three dependency deprecation warnings). PR #587's initial CI revision
has green web, shared runtime and dependency-audit jobs; backend remains running.
The live-provider job was SKIPPED because its workflow condition requires manual
workflow_dispatch/workflow_call or ACCEPTANCE_AUTOMATION_ENABLED=true for a PR.
This is not evidence of missing or invalid provider credentials. GitHub's
connected tool exposes no workflow-dispatch action; a run must be initiated from
Actions or an authenticated maintainer CLI. Acceptance secret availability is
still unverified. The physical-voice placeholder job is not physical evidence.
