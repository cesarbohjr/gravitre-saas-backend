# PR 601 — Conversational runtime reconciliation and autonomous-agent acceptance

Status: DRAFT. Engineering work authorized; no production deployment or paid-provider calls authorized.

## Objective
Reconcile Gravitre's existing light/medium/deep, One Brain, voice, connector, and governed-action architecture with observed production behavior. Fix proven integration defects, not redesign existing architecture.

## Existing work to preserve and trace
- PR #231: conversational text/voice acceptance gate.
- PR #227: natural response composition and lifecycle wording.
- PR #580: intelligence evidence and live-gate honesty; documented OpenAI 401.
- PR #587: shared intelligence, DSPy, Pipecat/LiveKit and voice reliability.
- PR #600: provider authentication backoff, contextual email discovery, clarification repair and PCM diagnostics.
- Issue #594: separate acoustic cancellation certification.

## Primary engineering directive: cohesion before redesign
The purpose of PR #601 is **integration correctness of the existing system**, not re-engineering its intelligence, learning, model, voice or persona components by default. Treat each existing component as an established subsystem until a reproducible defect establishes otherwise.

- Map the end-to-end **wiring contract** for each subsystem: producer, consumer, payload/schema, source-of-truth, ownership, trigger/activation, configuration, timing, fallback, error propagation and output evidence.
- Test every handoff, including light→medium→deep escalation, intelligence→planner, planner→tools, connector inventory→tool dispatch, tool results→reasoning, model switch→task/history continuity, agent personality→composer→TTS, interruption→cancellation authority, and output audio→heard-history.
- Identify disconnected, duplicate, misordered, silently skipped, incorrectly wired, stale, overridden or incompatible paths; inspect feature flags, environment variables, deployment SHAs and runtime precedence.
- Require full-turn traces and integration tests showing a capability **actually changes the intended outcome**; unit tests proving isolated components exist are insufficient.
- Repair broken contracts, configuration, handoffs and sequencing first. Re-engineer an individual component only after evidence proves its design itself is defective, with a documented reason and regression coverage.
- Preserve existing authorization, tenant isolation, idempotency, approval, cost limits and deliberate fast-path optimization.
- Completion criterion: one coherent agent experience across text and voice, with task continuity, natural expression, correct tools, honest recovery and verifiable results—not merely green component tests.

## Mandatory full-stack intelligence and personality scope
This PR is not audit-only: implement and regression-test **integration repairs** for proven gaps. Existing intelligence, learning, personality and voice components remain intact unless an evidenced component-level defect requires a narrowly scoped change.

### Intelligence and learning
- Inventory all **seven intelligence layers by their actual repository names**; record owner, inputs, outputs, feature flags, active runtime path, persistence, learning/update mechanism, telemetry and failure behavior. Do not assume the layer names or invent missing layers.
- Trace machine-learning components, DSPy/optimization, feedback loops, learned preferences, retrieval/memory and agent intelligence through actual decisions. Distinguish trained/adaptive behavior from static prompts and rules. Check tenant isolation, provenance, opt-in/retention, and feedback safety.
- Test light/medium/deep tier choice and escalation against full active-task state, not merely utterance length; check response quality and cost/latency tradeoffs.
- Trace model/provider selection, explicit overrides, defaults, fallback/circuit breakers, authentication health, capability and tool support. Validate fallback returns to the task without dropping context, and never silently crosses permissions or claims a tool action occurred.

### Agent personalities and expressive conversation
- Inventory every existing agency agent, its persona/system-prompt injections, shared personality layers, precedence, configuration, runtime injection points and overrides across text and voice.
- Verify persona survives tier transitions, model/provider switches, tool calls, interruptions, reconnects, and fallback routes without contaminating tool arguments or overriding safety/authorization.
- Test expressive, varied, context-appropriate dialogue: natural turn-taking, acknowledgement that advances the task, concise vs nuanced answers, prosody/TTS expressive controls, conversational warmth and calibrated humor. Avoid robotic repetition, canned generic clarifications, filler, exaggerated emotional claims, or personality that obscures facts.
- Distinguish linguistic expressiveness from audible expressiveness. Instrument TTS voice choice, synthesis, gain/ducking, queue underruns, interruptions and latency; listening trials are mandatory for audio quality claims.
- Preserve existing user/organization agent customization, stable identity, safety hierarchy, accessibility and multilingual behavior where supported.

### Traceability and implementation contract
For each layer and persona: source path + PR origin + configuration flag + deployment SHA + invocation evidence + output effect + regression test. Mark IMPLEMENTED, DEPLOYED, INVOKED, BYPASSED, FAILED or NOT_VERIFIED independently. Fix verified missing injection, misrouting, dropped state, poor fallback, or audio delivery in this PR; do not merely document them.

## Execution stages
1. Build a commit- and runtime-config-bound capability matrix: implemented, deployed, invoked, bypassed, failed, or unverified. Include light/medium/deep, primary and classical fallback, context compiler, response composer, tool inventory, authorization, voice and TTS.
2. Trace the November 2 Outlook failure by correlated conversation/turn IDs: ASR input, active task and heard history, tier choice, intent gateway, model/provider route, connector status and scope, fallback, final reply and played audio. Preserve tenant isolation; redact secrets and message content from retained evidence.
3. Reconcile recurring provider 401 with #580 and #600: effective selected model/provider, credential health and deployment SHA. Do not assume model routing is broken when credentials are invalid.
4. Inspect whether existing acceptance workflows ran on the exact deployed SHA and whether skipped/blocked checks were incorrectly represented as passes. Preserve all existing safety/write fences.
5. Repair verified intelligence-layer, learning, model-routing, agent-persona, expressive-dialogue, connector and audio root causes in small commits with regression tests for both primary and fallback paths. Do not replace tiered architecture or add vendor-specific special cases where canonical discovery works.
6. Run synthetic end-to-end journeys: Outlook alternative after Gmail unavailable; multi-turn task with interruptions; autonomous authorized research/preparation; approval-gated writes; provider outage recovery; 20-minute voice continuity; genuine stop versus stop-speaking. Include clean/impaired network and physical iOS/browser listening.
7. Compare contemporary ChatGPT on comparable tasks with independent raters, task success, meaningful latency, audio continuity and truthful capability claims. Report non-comparable gaps and costs.

## Required deliverables
- Seven-layer intelligence, ML/adaptation, model-routing and agency-agent personality matrices with source references and deployment provenance.\n- Exact runtime persona injection map and expressive text/voice acceptance scores.
- Turn-level causal timeline separating observed facts from hypotheses.
- Root-cause fixes with exact-head CI and existing combined acceptance suite.
- User-journey pass/fail report, audio measurements and independent safety audit.
- Explicit NOT_RUN/NOT_CERTIFIED labels for unavailable live or paid tests, plus rollback plan.

## Release policy
Remain draft until exact-head tests and permitted live acceptance certify the complete product experience. No new connector grants, autonomous writes outside existing approvals, training on production transcripts, paid inference, production rollout or ChatGPT-parity marketing claim.
