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

## Autonomous execution and contextual continuity — mandatory integration gate
Conversational naturalness is insufficient. Gravitre must **carry out authorized user objectives** using its connected capabilities, while retaining the referent and task state across turns.

### Execution wiring to trace
- Follow a user request through ASR/transcript → dialogue history and referent resolution → goal/intent extraction → light/medium/deep reasoning → task planning → capability/connector discovery → permission/readiness checks → tool invocation → result interpretation → multi-step continuation → outcome verification → final user response.
- Identify the **execution owner** and persisted task state for each turn. Verify ownership survives tier/model/provider changes, classical fallback, retries, interruptions, reconnects and tool failures; prevent lost work, duplicate side effects and unbounded loops.
- Separate informational replies, read-only tool work, prepared governed actions, approval-pending writes and completed writes. An agent must not substitute a generic answer for a feasible authorized task, nor claim success from intent, a tool request or an unverified response.
- Check contextual follow-ups: "another email provider" after Gmail means find connected/available email alternatives, including Microsoft 365/Outlook when authorized; preserve antecedents, current task, previous tool outcomes and constraints. Topic changes must not inherit unrelated task state.
- Check connector discovery from canonical capability registry, live installed/authorized connectors, permission scopes and catalog alternatives. Distinguish connected/usable, installed-but-unauthorized, available-to-connect and unsupported. Never hallucinate tools or permission.
- On missing authorization, invalid credentials, unavailable provider, failed tool or unsupported task, pursue permitted alternatives and explain the precise blocker or request the required approval; do not repeat "more context" when enough context exists.
- Governed side effects must retain user approval, least privilege, tenant isolation, idempotency and verifiable readback; autonomy applies within granted authority.

### Required executable acceptance journeys
1. **Email continuation:** user asks about Gmail, then "what other email provider can you use?", then asks to find a message via authorized Outlook/Microsoft 365. Verify referent, discovery, actual read or precise permission blocker, and task-completion reply.
2. **Research and act:** discover available sources, search, cross-check and produce a grounded deliverable without requesting redundant directions.
3. **Multi-step connector task:** plan, execute dependent reads, transform results, prepare a governed write, pause for approval and resume exactly once after approval; cancellation prevents writes.
4. **Failure recovery:** selected LLM returns 401, connector times out, or one capability is unavailable; preserve goal/history, use authorized alternatives when configured, and return a useful truthful outcome.
5. **Voice task continuity:** interruption, barge-in, reconnect and 20-minute conversation preserve active goal, action state, personality and audible output; no repeated generic clarification or double execution.

For each journey, record turn-level task state, selected route/model, connector/action invoked, policy decision, result provenance, user-visible and heard reply, latency, and PASS/FAIL/NOT_RUN. A fluent answer without execution evidence **fails** task-completion acceptance.

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
- User-journey pass/fail report, autonomous execution trace and verified task outcomes, audio measurements and independent safety audit.
- Explicit NOT_RUN/NOT_CERTIFIED labels for unavailable live or paid tests, plus rollback plan.

## Release policy
Remain draft until exact-head tests and permitted live acceptance certify the complete product experience. No new connector grants, autonomous writes outside existing approvals, training on production transcripts, paid inference, production rollout or ChatGPT-parity marketing claim.
