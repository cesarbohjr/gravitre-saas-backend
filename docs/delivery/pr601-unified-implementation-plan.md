# PR #601 — Unified Intelligence, Conversation and Autonomous Execution: Implementation Plan

Status: DRAFT; integration and remediation plan, not proof of completed repairs. Benchmark: ChatGPT-caliber task completion and conversational experience, measured with comparable permissions and tools.

## Objective and engineering principles
Make Gravitre's existing capabilities work as **one coherent system**. Preserve PR #581 agent routing and capability catalog, PR #587 shared intelligence/voice, PR #597 autonomous orchestration, and prior cumulative work. PR #600 remains separately in progress; reconcile its fixes without duplicate or premature merges. Repair broken wiring first; redesign a component only when reproducible evidence proves its design is defective. Do not equate deployed code, active invocation, or successful execution.

## End-to-end contract
User voice/text → transcript and history → referent resolution and durable task state → light/medium/deep routing → seven intelligence capabilities, memory/ML/DSPy, persona selection → plan and canonical connector discovery → policy/permission/approval checks → tool dispatch → durable result and idempotent continuation → verified outcome → expressive text/TTS → heard-history and next-turn state.

For each boundary record source file, producer, consumer, payload schema, activation flag, selected model/provider, deployment SHA, trace ID, latency, fallback and error propagation, authorization, outcome evidence, and test. Verify no dropped history, task, persona, tool result, or approval across routing and interruption.

## Workstreams
1. **Runtime and deployment reconciliation:** map merged/deployed/invoked/bypassed components across backend and frontend; exact SHA and effective nonsecret config; identify disconnected/duplicated/misordered paths.
2. **Seven intelligence layers and learning:** contextual, sentiment, causal, temporal, relational, adaptive, predictive; inspect actual evidence consumption, ML/DSPy, memory, feedback, preferences, persistence, consent, tenant boundaries and observable answer effect. Avoid claiming every layer must execute on every turn; verify relevance-aware activation/defer.
3. **LLM routing and failover:** investigate observed OpenAI 401, effective provider and overrides, live/shadow separation, tier choice, capability support, bounded auth backoff, healthy authorized failover and full task/history preservation. No silent permission or model-policy bypass.
4. **Conversation and personas:** agency-agent role manifests, injection precedence, response composition, personality consistency across providers, natural and varied replies, follow-up reference resolution, clarification loop repair, safe expressive TTS.
5. **Autonomous execution:** canonical connected/available/unauthorized tool discovery, planning, actual reads, approval-gated writes, durable task ownership, retry/idempotency, cancellation, reconnect, verified readback and honest outcome statements. A fluent answer without a tool outcome is not task success.
6. **Voice pipeline:** Pipecat, Deepgram, ElevenLabs, client playback, PCM buffers, gain/ducking, barge-in, latency, reconnection and long-session listening. Separate first model text latency from TTS TTFA and audible continuity.
7. **Observability, security and independent defects:** sanitized correlated traces; investigate Slack invalid_auth and workflow prediction DB error independently; maintain least privilege, tenant isolation, consent, approval and rollback.

## Evidence-backed initial repair backlog
- F01 OpenAI 401 (confirmed) and F02 unified-turn error fallthrough (confirmed; successful fallback unverified).
- F03 generic repetitive clarification (observed; exact causal link unproven) and F04 sampled ~8-second first substantive text latency.
- F05 recurring Slack invalid_auth and F06 workflow-prediction database operation failure.
- F07 user-reported choppy/fading audio, F08 idle cancellation requiring session correlation.
- F09 seven-layer/persona integration unverified; F10 Outlook-after-Gmail autonomous completion unverified.
- F11 PR #600 not deployed; F12 inadequate turn-level observability; F13 rejected HubSpot webhook may be expected protection; F14 frontend/client deployment not reconciled.
Maintain the detailed register in docs/delivery/pr601-failure-register-and-repair-gates.md. Every finding requires owner, root cause or explicit unverified classification, test and disposition.

## Phased delivery and exit gates
**Phase 1 — Baseline and wiring:** freeze exact candidate/deployment SHAs, compile complete producer-consumer map, reconcile feature flags and source paths, link sanitized production turn evidence. Exit: no critical unknown handoff without explicit NOT_VERIFIED.
**Phase 2 — Provider recovery:** fix F01/F02 with deterministic 401/timeout tests, authorized healthy fallback and task continuity; ensure no duplicate effects. Exit: failures recover truthfully or provide precise blocker.
**Phase 3 — Context and dialogue:** resolve F03/F04 and Outlook antecedent; prevent repetitive generic clarifications; preserve persona and task across tiers/providers. Exit: scripted multi-turn continuity passes.
**Phase 4 — Real autonomous execution:** complete connected Outlook read and governed multi-step write scenarios, actual tool result provenance, cancellation and idempotent resume. Exit: outcome verified; permissions never bypassed.
**Phase 5 — Intelligence and expression:** prove relevant seven-layer outputs, ML/memory and agent-persona injections reach final text and speech; repair only verified missing links. Exit: positive/negative integration tests and observable effect.
**Phase 6 — Voice quality:** client/server version check, physical listening, interruptions, reconnect, 20-minute sessions, acoustic and tail latency measurements. Exit: agreed thresholds and no unexplained drops.
**Phase 7 — Reliability and ChatGPT benchmark:** repair independent F05/F06, complete correlated observability, run matched ChatGPT/Gravitre task sets with comparable access and independent text/audio raters. Set thresholds before evaluation; no cherry-picking.
**Phase 8 — Release:** exact combined-tree CI, independent write-fence/security audit, permitted live smoke tests, rollback plan, then separately authorized merge and production deployment; verify post-deploy SHA and user journeys.

## Mandatory acceptance journeys
- Gmail unavailable → “try another email provider” → discover authorized Outlook/Microsoft 365 → perform requested read or identify precise permission blocker, without losing referent.
- Research → source discovery → grounded deliverable, no redundant context requests.
- Multi-step reads → governed write preparation → approval → execute exactly once → verify result.
- Provider 401/timeout → safe fallback or actionable failure while retaining active task.
- 20-minute voice conversation with interruption, barge-in, reconnect, consistent persona and no duplicate execution.
- Seven-layer relevance/negative cases; agent role selection, personality injection, and final audible reply.
Record turn IDs, provider route, intelligence evidence, persona, tool invocation, policy decision, result, spoken/heard response, latency, PASS/FAIL/NOT_RUN.

## Definition of done
All confirmed failures repaired or evidence-backed dispositioned; critical handoffs verified; no false completion claims; no critical authorization/security violations; complete exact-head CI; matched full-journey tests; physical audio and live-provider checks only when authorized, otherwise NOT_RUN/NOT_CERTIFIED. No ChatGPT parity claim without measured results. PR #601 remains draft until gates pass. No production rollout, paid-provider testing, secret rotation or autonomous writes outside existing approval policy authorized by this plan.


## PR #600 voice-continuity instrumentation checkpoint — 2026-11-03

**Scope:** source-only playback-state correctness and content-free diagnostics, not a listening verdict. Change set on the reconciled PR #601 branch; do not promote or merge without exact-head checks.

- The worklet now tags `started` events with the same flush epoch as progress and active reports. The browser rejects a delayed pre-flush start, preserving reply-origin and heard-history attribution through interruptions. An automated regression exercises a stale start followed by a valid new-epoch start.
- The PCM queue counts **recovered starvation gaps** only when a starved queue later receives additional PCM; it records event count and elapsed output frames without changing fade, queue, barge-in, or cancel behavior. These observations cannot by themselves distinguish TTS/network delay from a pause or a new reply. The existing underrun heuristic is separate and may report different counts.
- Worklet progress/active messages carry `rebuffer_events` and `rebuffer_frames`, converted by the player into cumulative `rebuffer_ms`. The existing scoped output-diagnostics payload allowlists bounded `rebuffer_events` and `rebuffer_ms`; no audio, transcript, device identity or new grants are collected. Duck duration and flush count remain available for joint analysis.
- Processor and shared DSP changes bump the worklet cache version to 6. Unit contracts cover stale event epochs, cumulative/invalid diagnostic values, measured queue starvation, flush exclusion, and backend schema bounds.
- Baseline buffering and gain policy remain **unchanged**: 120 ms initial lead, max 320 ms, adaptive 60 ms increase, 12 ms flush fade, duck gain 0.15. No speculative reduction of attenuation or interruption detection was introduced.
- **Acceptance status:** code committed; exact-head CI pending. Real iOS Safari/desktop output capture, TTS arrival/playing timestamps, server-to-client clock correlation, blinded listening, provider acoustic cause and an authorized matched comparison remain **NOT_RUN / NOT_CERTIFIED**. Investigate any long duck interval alongside rebuffer gaps and audio-context state before selecting a playback or prosody remedy.

