# Gravitre Voice and One Brain Roadmap

Status: Planned. Phase 1 remains subject to PR #585 live provider acceptance; this document does not certify or merge it.

## Architecture principles
- Seven intelligence layers/capabilities feed a **single shared One Brain** for intelligence coordination, reasoning, decisions, and learning. Do not create independent brains for voice, agents, or workflows.
- Four agent roles use shared One Brain services with role-specific policies and dialogue behavior.
- Voice and chat are interaction channels, not competing decision engines.
- Plays, workflows, actions and connectors execute only through existing authorization, tenant isolation, governance and audit controls.
- Action results and feedback return to One Brain and the intelligence layers for measured improvement; machine-learning updates require explicit validation and deployment controls.
- Pipecat, if adopted, is a voice transport/orchestration component, never a replacement for One Brain.

## Phase 1 — Voice foundation (PR #585)
ElevenLabs TTS, Deepgram STT, duplex streaming, interruption/cancelled-write protection, light/medium/deep expression profiles, latency and audio-gap metrics. Gate: green synthetic and live provider roundtrip, credential verification, recording evidence for all three profiles, and review of CI and acceptance artifacts. Do not merge on synthetic-only success.

## Phase 2 — Advanced conversational intelligence
Deliver a shared, configurable dialogue layer across four agent roles:
1. Contextual intent, subtext, sarcasm, humour, indirect requests, and ambiguity detection.
2. Emotional/social awareness, proportionate boundaries for inappropriate language, graceful redirects, and avoidance of false positives.
3. Natural turn-taking, acknowledgments, interruption responsiveness, silence/hesitation handling, and conversational overlap.
4. Short-session context, permissioned long-term memory, commitments, and retention/tenant isolation.
5. Adaptive tone, pacing, explanation depth, vocabulary, role-specific conversation style and objection handling without manipulation.
6. Proactive clarification, conversation repair, uncertainty disclosure, and smooth recovery after errors.
7. Expressive prosody synchronized with content, multilingual conversation and language switching.
8. Human escalation/handoff with summaries and relevant context.
9. Outcome quality scoring and dialogue evaluation with privacy-safe observability.
10. Pipecat integration behind a swappable engine interface; benchmark against existing pipeline for first-audio latency, audio gaps, interruption, reliability and operational cost; adopt only where validated.

### Voice 3.0 — Expressive Dialogue and Conversational Adaptation (shared text/voice)

Enhance the existing One Brain dialogue path to deliver natural, expressive, context-aware conversations across chat and voice, benchmarked against matched ChatGPT and Claude reference conversations. Reuse existing contextual/sentiment intelligence, consent-governed memory, personas and LLM routing; evaluate lightweight adaptive conversational planning, dynamic tone/vocabulary/depth, dialogue repair, multi-turn continuity, curated diverse examples, and expressive speech delivery. Audit prompt assembly and repetitive instructions before adding frameworks; evaluate DSPy for offline prompt optimization, Pipecat for voice delivery, and DeepEval for repeatable diagnostics only where they demonstrably improve quality. Do not add a second brain, unconditional per-turn LLM calls, or a large canned-script prompt.

Measure blinded human-rated naturalness and register appropriateness, repeated openings/stock phrases, context and correction retention, emotional appropriateness, clarification quality, latency, interruptions, and governed tool-execution accuracy. Proposed initial targets (subject to baseline calibration): at least 80% preferred-or-tied against each reference in blinded comparisons; at most 5% unnecessary repeated openings; at least 95% correction retention and consequential clarification accuracy; at least 90% appropriate register; zero unauthorized writes; and no material regression to approved voice latency budgets. Reuse the existing paired synthetic evaluation foundation, extend to 10–30-turn scenarios, report per-category results and human-rater agreement, and separate offline from real-provider/physical-device evidence. Deliver as reviewable increments within the existing consolidated CI workflows and 43-finding remediation traceability. Production acceptance requires real voice, tool, privacy, consent, rollback and deployment evidence; adding this plan is not certification.

Deliver as small, reviewable PRs. Acceptance: role-by-role scenario matrix covering normal, ambiguous, adversarial, multilingual, interruption, memory, boundary, escalation and recovery paths. Include privacy/security and performance regression tests.

## Phase 3 — One Brain, seven layers, actions and workflows

Current source integration and scoped offline evidence: [Phase 3 implementation](../delivery/phase3-one-brain-integration.md). This does not replace the live certification requirements below.
Connect Phase 2 interaction channels and all four agent roles to the existing seven intelligence layers through **One Brain**. Preserve the actual canonical layer names and contracts from the repository; do not invent or rename layers.

End-to-end flow: spoken/text input -> dialogue interpretation -> role-specific agent -> One Brain -> seven-layer intelligence context/recommendation -> governed authorization and approval -> Play/workflow/action/connector execution -> audited result -> feedback to One Brain and seven-layer learning loop.

Integrate existing Plays including Customer Rescue and Process Drift, workflow lifecycle, connector permissions, recommendations, human approval gates, tenant isolation, MSP governance, audit evidence, idempotency, retry/compensation and error recovery. Do not allow voice instructions to bypass security policies. Machine learning is evidence-driven, with offline evaluation and controlled promotion rather than unreviewed self-modification.

Certification: cross all seven intelligence capabilities with four agent roles and supported interaction/action surfaces; test positive and denied permissions, cross-tenant isolation, approvals, cancellations, rollback/compensation, end-to-end Play outcomes and feedback integrity. Reuse existing certification requirements and evidence where applicable; do not claim unexecuted tests have passed.

## Delivery sequence
1. Finish Phase 1 acceptance and merge PR #585 only after green gates.
2. Build and certify Phase 2 dialogue capabilities incrementally.
3. Benchmark Pipecat and select voice orchestration based on evidence.
4. Connect Phase 3 to canonical One Brain and seven-layer interfaces.
5. Wire governed Plays/workflows/actions/connectors and feedback loops.
6. Run end-to-end cross-role, cross-capability and security certification before production rollout.

This roadmap records scope and acceptance intent; it does not imply implementation or production deployment.
