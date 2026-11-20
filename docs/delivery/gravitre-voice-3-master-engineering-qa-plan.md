# Gravitre Voice 3.0 — Master Engineering, Reliability and QA Certification Plan

**Status:** PROPOSED / IMPLEMENTATION NOT STARTED / P0 CUSTOMER ACCEPTANCE FAILURE. **Date:** 2026-11-07.
**Owner:** Gravitre voice + canonical intelligence/runtime + QA workstreams. **Origin:** User's direct production voice test, PR #605 unified modernization audit (ECO-004, ECO-009, ECO-016–028 and later runtime/outbox/ownership gates), the prior ChatGPT review, Deepgram Flux and ElevenLabs engineering documentation.
**Integration:** Companion to the master QA automation initiative (`feat/gravitre-master-qa-automation`) and to PR #605; no destructive replacements, deployment, or modification of already-merged PR #608. Add these cases to master QA orchestration once its owning plan is identified/implemented.

## 0. Problem statement: do not conflate the three failures

The user's live test reports: (a) severely choppy/fading spoken output; (b) the assistant begins responding before a sentence/question finishes; (c) unsolicited “let me check”/tool narration, repetitive or contextually unrelated replies; (d) weak follow-through on useful tools and tasks. Treat as **release-blocking P0 product failures**, independent of whether backend tests, audio transport connections, or browser CI are green. Causes below are candidates, **not established**. Keep voice parity **NOT CERTIFIED** until measured technical and user acceptance.

### Primary diagnostic hypotheses (prove or disprove)
- **Turn gate / STT:** `backend/app/services/pipecat_voice/stt_factory.py` enables Flux eager mode when an eager threshold is configured. `EagerEndOfTurn` can start speculative LLM generation; inspect whether model/TTS/playback results leak before committed `EndOfTurn` or survive `TurnResumed`. Examine `transcript_relay.py`, interim/final boundaries, backchannels, duplicated finals and stale generations; confirm active production preset, not just source.
- **Dialogue/tool narration:** Inspect `unified_turn_reasoning_service.py`, `unified_turn_classical_fallback.py`, tool response composer, `chat_connector_execution_service.py`, narrator/prompts and `scripts/measure-voice-narration-dead-air.py`. Separate requested actions, helpful suggestions, automatic filler, real tool dispatch, and verified results. Presence of a measurement script does not establish the production culprit.
- **Audio:** Inspect server TTS chunk emission, Pipecat WS frames, sample-rate/PCM integrity, `apps/web/hooks/use-voice-duplex-session.ts`, `apps/web/lib/voice-pcm-player.ts` (AudioWorklet and BufferSource), `apps/web/lib/pipecat-voice-client.ts`, jitter/duck/reconnect/epoch cancellation. Distinguish network dropouts, provider stalls, browser underruns, wrong clocks and overly aggressive interrupt/ducking.
- **State:** Verify single author of turn status vs multiple intent/model/context/voice owners. Preserve tenant scoped `conversation_state_service`, `execution_plan_authority`, `execution_outcome`, approvals, cancellation, audit, durable outbox and write fences. Test multi-process concurrency before altering authority.

## 1. Target invariant: one intelligence, two duplex surfaces, authoritative turn ownership

```text
Browser mic (WebAudio) -> transport (current Pipecat WS; isolated WebRTC candidate)
 -> Deepgram Flux (or explicitly chosen supported STT fallback)
 -> Correlated Turn Arbiter (session_id, utterance_id, turn_revision, transcript digest, generation_epoch)
 -> canonical Gravitre context/intent/model policy and governed tool engine
 -> verified response envelope: answer | suggestion | progress | approval_request | verified_result
 -> ElevenLabs compatible streaming TTS adapter
 -> epoch-tagged PCM queue / adaptive jitter buffer / player with exact cancellation
 -> browser speaker + durable conversation view
```

**Principles:**
1. One authoritative **Turn Arbiter** is responsible for when a user turn is committed, when new response audio is authorized, and when interrupted speculative work becomes invalid. Client/server have explicit mirrored states; connection health is not turn authority.
2. Permit `EagerEndOfTurn` **computation only** behind a non-emitting speculative gate. Prohibit audible output, tool calls with external effects, durable user-history writes and progress narration until the authoritative committed turn and policy permit them. On `TurnResumed`, invalidate generation epoch and discard all queued text/TTS/PCM. Commit only when final transcript identity/revision is consistent; avoid arbitrary 400–600ms global VAD threshold.
3. Differentiate **user barge-in** (legitimate interruption of assistant speech) from **assistant premature reply** (defect). On genuine barge-in, stop audio promptly and interrupt generation; preserve any already executed provider write/outcome and idempotency.
4. Treat conversational answer, direct task and goal-driven plan as **modes of the same canonical kernel**. Text/voice differ in I/O and rendering, not in tenant auth, tool policy, model selection or execution truth.
5. Retain Deepgram and ElevenLabs as configurable speech providers. Do not put Gravitre connectors, credentials or approvals under a vendor-managed ElevenAgents brain; a future adapter can be compared only within the same governed contract and after privacy/cost review.
6. Keep existing Pipecat path until its behavior and the WebRTC alternative are compared on equivalent fixtures; LiveKit candidate currently is an isolated **transport** comparison, not proof that migrating to LiveKit Agents fixes dialogue.
7. Reuse current infrastructure. Introduce no new managed service merely for novelty; all framework/vendor changes require causal evidence, dependency/security/privacy analysis, total cost and rollback.

### Formal turn states
`DISCONNECTED` → `READY/LISTENING` → `USER_SPEAKING` → `ENDPOINT_CANDIDATE` → `USER_TURN_COMMITTED` → `REASONING` → `SPEAKING` → `READY/LISTENING`.
Orthogonal states: `TOOL_PENDING_APPROVAL`, `TOOL_EXECUTING`, `CANCEL_REQUESTED`, `RECONNECTING`, `FAILED`.
Events must be versioned and idempotent: `mic.voice_start`, `stt.interim`, `stt.eager_eot`, `stt.turn_resumed`, `stt.final_segment`, `stt.end_of_turn`, `turn.commit`, `response.speculative`, `response.authorize_output`, `tool.proposed`, `tool.dispatched`, `tool.observed`, `tts.chunk`, `pcm.enqueue`, `pcm.play`, `pcm.underrun`, `barge_in`, `generation.invalidate`, `turn.complete`. Correlate events by tenant-safe opaque trace IDs; do not log raw sensitive audio/transcripts by default.

## 2. Sequenced implementation: red tests first, bounded repairs

| Gate | Engineering deliverable | Source-of-truth / proof | Merge criteria |
| --- | --- | --- | --- |
| V0 — baseline and source wiring | Reconcile deployed UI/backend SHAs, voice flags/presets/renderer, model/provider, WS domain, route ownership, current code vs PR605 audit. Read-only production inventory; consented recording only after deployment approval. | Timestamped deployment/config attestation, exact source SHA, sample code-level call graph, named unresolved hypotheses. | No undocumented active voice entry points; unknowns labeled UNKNOWN. |
| V1 — trace and reproduce | Privacy-safe synthetic fixtures and synchronized mic→STT→turn→LLM/tool→TTS→PCM event recorder with monotonic timestamps, correlation and error classes. | Deterministic failing tests for pause, correction, double-final, unsolicited narration and synthetic audio starvation. | Defects reproduced, classified, invariant assertions added. |
| V2 — turn arbitration | Authoritative turn-state transitions and commit barrier; speculative response containment; `TurnResumed` epoch invalidation; transcript deduplication; client/server state parity; short backchannel filtering without deleting true final speech. | Long utterances with 0.4/0.8/1.2-second mid-sentence pauses; corrections; overlapping user/assistant speech; reconnect and STT fallback. | **Zero premature assistant playback** and exactly one committed user turn per fixture; valid intentional barge-in retained. |
| V3 — cognition and action honesty | Structured intent/answer/action envelope, stable context across follow-ups, tool availability + scope, no unsupported “checking” or fabricated results; preserve read/write authorization, explicit approvals and durable completion. | No-tool conversational probes, genuine tool request probes, no-connectors, approvals/revocation, multi-step and stale-tool callbacks; text/voice semantic parity. | Zero unauthorized writes, fake tool claims, filler-only turns and contradictory terminal outcomes. |
| V4 — audio continuity | Instrument ElevenLabs first byte and chunk cadence, PCM format/sample rate, queue depth, underruns, worklet/BufferSource selection, gain/duck transitions, replay suppression and stop/clear; tune queue adaptively, avoid blind buffer increases. | Synthetic impulse/silence/slow chunk/fast chunk/packet delay/cancel tests plus controlled browser playback captures. | No repeated/dropout syllables or cross-turn bleed in deterministic fixtures; measurable underrun budget and first-audio SLO agreed before certification. |
| V5 — transport and expressive quality | Compare baseline Pipecat WS vs Pipecat/WebRTC candidate with identical speech, LLM/TTS policies and device/network conditions; compare supported ElevenLabs Flash/Turbo/expressive models only with correct endpoints. | Paired latency (TTFA p50/p95), packet loss/jitter, intelligibility, MOS-style blinded rating, cost per minute, tool parity and reconnect results. | Adopt only demonstrably better, no tenant/governance regression; documented cost/privacy/rollout/rollback. |
| V6 — holistic master QA | Wire deterministic tests into exact-head CI, route inventory, provider-independent browser simulation, workflow orchestration and certification artifact; retain status v2/outbox/approval and multi-process write fences. | Machine-readable result matrix per test, device, SHA, environment, provider simulation, skipped/not-run counts, links to traces. | Required gates green, **skips are not passes**, no paid live tests before approved production stage. |
| V7 — deployment and human acceptance | Protected merge per current owner policy; controlled deployment, SHA + route + health verification; production Deepgram/ElevenLabs/selected LLM checks and real-device iOS Safari + desktop 20-minute conversation. | Consent-controlled audio, synchronized live traces, task completion, naturalness rubric, and the user's explicit sign-off. | No subjective ChatGPT-level parity claim without the user's final acceptance. |

**Sequencing constraint:** Instrument and prove V1 before changing models, voice sliders, silence thresholds, framework or transport; fix turn arbitration (V2) before evaluating expressive quality (V5). V3 and V4 can run in parallel after V1 if state/trace contracts remain stable. Preserve exact-head CI when adding changes. Do not change production traffic while diagnosing source-only hypotheses.

## 3. Innovative engineering refinements worth implementing only if tests support them

- **Two-phase voice commit:** speculative *computation* token is not output permission. Commit barrier mediates generation/streaming; epoch tagging prevents an old reply/TTS chunk from playing after the user continues. Useful for low latency without interrupting users. Do not persist an eager draft as the customer's statement.
- **Conversational floor manager:** distinguish user continuation, hesitation, assistant backchannel and true interruption using STT semantics plus local acoustic/VAD evidence; apply hysteresis and contextual pause profiles (including long enumerations and multi-part questions), not a universal fixed cutoff. A deliberate “stop” remains prompt.
- **Audible truth contract:** “Let me check” allowed only if a real relevant check is about to execute or already has been dispatched and the user turn is committed; never on a conversational response simply to fill silence. Voice cannot make an action-completion claim ahead of independently verified provider outcome.
- **Speech continuity controller:** adapt playback queue to observed producer/transport jitter with bounded latency budget; propagate source epochs and PCM sample counters across TTS chunks/player so underrun, overrun, replay, stale audio and sample-rate mismatch are separately detectable. Keep transparent failure paths rather than degrading into a different voice silently.
- **Prosody without fantasy:** avoid synthetic “umm” defaults and faux breaths. Sentence/phrase-level streaming should respect punctuation, semantic clauses and ElevenLabs model/endpoint compatibility. Benchmark available voices/blinded naturalness; do not assume voice cloning, lower stability or more fillers guarantees realism.
- **Dual-surface conversational state:** transcript view, speech generation and tool execution share one immutable committed-turn ID and durable execution result; interruptions affect narration, not already committed business actions. Recover from reconnect with replay-safe event cursors.
- **User intent integrity evaluation:** distinguish requested action, optional helpful suggestion, approval required, verified completion. Bench conversational quality against difficult ambiguous queries, evolving long-turn context, interruptions and single/multi-task outcomes rather than keyword or generic benchmark pass rate.

## 4. Master QA test matrix (minimum required)

**A. Turn-taking — P0:** user speaks a long multi-clause question with 400/800/1200ms pauses; pauses before “but”; correction (“Tuesday—actually Thursday”); slow speech; hesitations; trailing question; whispered/quiet speech; short backchannel from speaker; STT interim updates; duplicate `EndOfTurn`; `EagerEndOfTurn→TurnResumed`; provider reconnect. Assert no early audio/tool side effect, exact final transcript, no phantom turn. Also test rapid genuine barge-in stops existing speech without suppressing new user turn.

**B. Dialogue — P0:** ask a simple conversational question with no tools; contextual follow-up; switch from chat to voice and back; specify “do not check anything”; request real authorized connector read; request unapproved write; approve, deny, revoke and repeat; connector missing scope; model unavailable. Assert no unsolicited “let me check,” no repetitive templates, grounded answers, correct scope, transparent errors and verified outcomes.

**C. Acoustic — P0:** deterministic PCM frames at expected sample rate, variable TTS chunk timing, 0/100/300ms network jitter, artificial starvation, forced AudioWorklet unavailable, mobile Safari audio focus/suspend/resume, Bluetooth route changes, concurrent reconnect, cancellation mid-word and turn-id rollover. Assert bounded underrun, no dropped/replayed word tails, no cross-turn bleed, correct gain recovery and no indefinite ghost audio.

**D. Execution/governance — P0:** single read, approved write, explicitly denied write, interrupted approval, resumed multi-step plan, replayed provider callback, worker crash/restart, multi-process pending-action CAS and tenant isolation. Check idempotency, write fences, durable journal and terminal-outcome truth rather than only spoken transcript.

**E. Naturalness — acceptance:** open-ended 20-minute voice-only session with follow-ups, nuanced questions, hesitations and tool requests. User rates pacing, warmth, coherence, expression, pronunciation, silence, interruptions, context and proactive behavior. Record subjective scores and objective traces separately. No self-graded parity claim.

## 5. Observability, targets, hard gates

Minimum safe redacted event fields: `trace_id`, opaque `session_id`, `turn_id`, `utterance_id`, `revision`, `generation_epoch`, `event_type`, source and monotonically timed timestamp, state transition, provider/model ID, audio format and sample counter, queue depth, STT final/EOT class, tool action state, nonsecret org/tenant discriminator, error and abort reason. Maintain sampling controls, retention policy, access authorization and default-off sensitive content.

Report separately: mic-to-EOT, EOT-to-model first token, EOT-to-first **audible** sample (not only provider TTFB), p50/p95, TTS chunk gaps, PCM underruns/minute, incomplete-turn speaking rate, duplicate-final turns, ghost-audio incidents, interrupt cut-off, tool intent precision, tool verification rate, end-to-end completion, minutes and cost/turn. Establish baseline before choosing numeric optimization targets. **Correctness gates are zero tolerance** for unauthorized writes, false verified outcomes, cross-tenant data, premature speaking in deterministically reproduced test cases, stale audible generations and deliberate unsupported tool downgrade. Synthetic green is necessary but insufficient for human acoustic acceptance.

The master QA runner must output for every lane: `NOT_RUN | BLOCKED | FAIL | PASS`, exact commit and deployed SHA, scenario and fixture digest, permission boundary, run URL, provider simulation/live classification, assertions, failure artifact link and reason. No “not exercised” lane can be classified passed.

## 6. Provider and transport decision log

- **Deepgram:** Keep Flux as currently primary, Nova-3 explicitly as compatible fallback. Audit current `eager_eot_threshold`, `eot_threshold`, `eot_timeout_ms` and chosen voice profile; do not hardcode 400–600ms. Apply Deepgram's documented `TurnResumed` invalidation and commit barrier. Review STT fallback metadata and semantic parity.
- **ElevenLabs:** Keep TTS adapter. The existing `/v1/text-to-speech/{voice_id}/stream-input` WebSocket does not support v3/v4; compare models only using appropriate endpoint/protocol, voice/format support and real paid-account limits. Optimize end-to-end TTFA, not vendor-only latency. No PVC requirement.
- **Pipecat:** Keep cognitive bridge and auth boundary. Compare WebSocket vs WebRTC transport separately and hold all other variables fixed. Consider using LiveKit only if a measured transport win survives operational cost and tenant-security review; native ElevenAgents must not bypass Gravitre policy.
- **LLMs:** Continue unified organization model policy and capability-aware routing. No additional LangGraph/LiteLLM/OpenRouter migration unless a measured gap justifies it; model switching must preserve tool access, conversation state and authorization.

## 7. Release ownership and stop conditions

- **Voice runtime owner:** turn-state contracts, transcription finality, cancellation and provider session lifecycle.
- **Frontend audio owner:** browser mic, PCM worklet/player and iOS Safari audio/reconnect behavior.
- **Intelligence owner:** contextual reasoning, tool initiative, truthful action envelopes.
- **Governance owner:** approvals, provider writes, outcome verification, audit and durable recovery.
- **QA owner:** fixtures, tests, replay/trace integrity, independent certification and evidence artifact.

The owner of each failing invariant must publish root cause with direct traces, minimal repair, regression added, exact SHA, rollback and residual risks. No blind parameter tuning, unbounded retries, silent provider substitutions, or reduction of CI checks.

**Non-negotiable release sequence:** branch implementation → exact-head offline/synthetic tests → full CI + governed action and security gates → protected review/merge → explicitly authorized production deployment with verified SHA → live provider/acoustic acceptance on iOS Safari and desktop (20-minute dialogue and approved tasks) → user acceptance. Prior PR #605 CI green does NOT certify voice parity or production experience. Merge/deploy/secret/DB changes are **not requested or granted** by this document.

## 8. Reference evidence and vendor docs

- Prior PR #605 audited scope: `docs/delivery/gravitre-unified-ecosystem-modernization-plan.md`, `pr605-canonical-ownership-retirement-register.md`, `pr605-dependency-audit-tranche-3.md`, `pr605-dependency-audit-tranche-4.md`, later deployment/runtime inventory and merge-control packets.
- Deepgram: https://developers.deepgram.com/docs/flux/configuration and https://developers.deepgram.com/docs/flux/voice-agent-eager-eot
- ElevenLabs: https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tts ; https://elevenlabs.io/docs/eleven-api/concepts/latency-methodology ; https://elevenlabs.io/docs/eleven-api/guides/how-to/best-practices/latency-optimization

**This document is a proposed executable engineering and QA specification, not a code fix, measured baseline, successful CI run, deployment or final acceptance.**
