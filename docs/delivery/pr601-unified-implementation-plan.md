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



## PR #600 acoustic-causality gate — further engineering checkpoint (2026-11-03)

**Implemented on reconciled PR #601 branch, not deployed:** source-backed fixes and deterministic regression comparisons. No provider invoice, mailbox action, production flag change or real-device recording was authorized by this checkpoint.

### Findings and repairs

1. Previously, a stream resuming after an extended interval was counted as recovered starvation even if the interval exceeded the existing 400 ms same-reply limit. `PcmPlayoutQueue.push` now increments `rebufferEvents`/`rebufferFrames` only for a continuation satisfying the existing same-reply classifier, keeping counting consistent with adaptive jitter. It still cannot identify true reply identity without an explicit source reply boundary; avoid treating the metric alone as an acoustic verdict.
2. The worklet's first `started` event after a flush now replaces the provisional `ctx.currentTime + 120ms` reply origin with its actual reported AudioContext frame timestamp. Rebuffer-induced later starts do not change the original start time. Flush resets confirmation; stale-epoch start reports remain rejected.
3. Added regression cases for terminal silence and cross-reply pauses, measured first-start correction, and a deterministic constant-PCM delayed-arrival comparison of the existing 120 ms lead versus a 260 ms alternative. The comparison tests the buffering/latency tradeoff, **not** an acoustically validated winner. Production lead remains 120 ms and the maximum remains 320 ms.
4. Explicit stop, genuine interruption, approval/cancellation, gain ducking, worklet flush fade and task authority are untouched.

### Required causal observation matrix (NOT RUN)

For a synchronized browser/TTS/audio trace, collect same-clock relative receive/enqueue/start/play/underrun/duck/unduck/flush/context-state events scoped by session, turn and reply ID, with content-free timing plus any separately consented test audio. Report possible categories separately:

| Signature | Hypothesis | Cross-check / disqualifier |
| --- | --- | --- |
| New same-reply rebuffer count with positive gap | PCM queue starvation | Compare PCM arrival gaps, queue depth and output recording; do not infer upstream provider identity |
| Ducked state and growing ducked_ms, but no starvation | Overlap attenuation | Compare actual mic overlap, classifier decision and gain restoration; deliberate interruption must still flush |
| AudioContext state is not running | Browser playback interruption | Inspect resume/user-gesture/OS interruption; do not call this TTS silence |
| No queued PCM with late upstream chunk arrivals | TTS or transport delivery delay | Correlate server TTS generation/send timestamps and client receive clock, distinguishing intentional punctuation |
| Silent recording with normal queue, no duck and running context | Unknown until investigated | Compare capture/output routing, device gain, synthesis amplitude and muted output |

**Physical and benchmark gate:** iOS Safari speaker/headphones, desktop Chrome/Safari, Wi-Fi and impaired-network runs, barge-in/reconnect, uninterrupted 20-minute conversational audio, actual consented recordings, and contemporaneous blinded independent ChatGPT/Gravitre matched-permission reference ratings are still **NOT_RUN / NOT_CERTIFIED**. Code-level synthetic timings cannot be substituted for them. Use recorded exact code/config SHA, audio checksums, real provider route, test conditions, privacy controls and rating provenance when those evaluations are authorized and available.

**Decision rule:** do not change lead/duck/gain/transport or claim a winner until synchronized real PCM/TTS/device data shows a reproducible mechanism, measured improvement in held-out sessions, nonregression of first meaningful audio and cancellation latency, and independent audible inspection. No merge/deploy solely on offline tests.

## Release-gate clarification — 2026-11-04 (supersedes Phase 8 sequencing only)

User-authorized release order is **offline exact-head certification → merge to main → production deployment verification → real live-provider, connector, audio and comparative acceptance**. This ordering supersedes older paragraphs requiring paid provider or physical listening before merge. It does **not** waive those acceptance journeys or classify NOT_RUN as PASS.

### Gate A — Pre-merge engineering certification
- All applicable GitHub Actions workflow jobs (not just green workflow wrappers) pass on the **same immutable head SHA**, including full backend pytest, integration smoke, web, Phase 3 seven-layer/offline contracts, autonomous-write independent process, connector governance, browser voice guard, and privacy/security tests.
- Fix runner/environment faults rather than silently dropping assertions. In particular, Phase 3 intelligence coverage's historical `Errno 28` install failure must be rerun with CPU-only PyTorch and adequate disposable-runner disk.
- Preserve the exact SHA and test/job/artifact links. A skipped paid test is deferred; a failed or cancelled non-paid job blocks this gate.

### Gate B — Merge decision
- Confirm PR600's 21 changes have been reconciled into PR601 and avoid an independent duplicate merge. Resolve current branch protection, review requirements, migration safety and rollback owner.
- Once Gate A passes, mark the PR ready for review and merge with exact-head SHA guard. CI passing is **not** evidence of production conversational parity.

### Gate C — Deployment verification
- Confirm backend Railway deployment and frontend Vercel deployment originate from the merged main commit; check health and migrations, make rollback available, and ensure permitted production settings are effective.
- No certification of text, audio, connector outcomes or user conversations from source existence alone.

### Gate D — Post-deployment real functional acceptance
- Prove effective authorized OpenAI/Anthropic inference/failover, conversational referent/history/agent-persona retention, contextual connector inventory and real authorized Outlook or equivalent mailbox read with result provenance.
- Prove research and multistep work actually performs permitted reads, prepares approval-gated writes, executes exactly once after approval and verifies results. Preserve cross-tenant, revocation, cancellation, restart/idempotency safeguards. If authorized test connectors/accounts are missing, mark scenario BLOCKED with exact dependency.
- Record relevance-aware seven-capability activation/defer, ML/memory consent, role/persona injection, downstream reasoning consumption, final answer impact and accurate user-facing task outcome.

### Gate E — Post-deployment acoustic and product acceptance
- Record synchronized TTS/network/client audio, speaker playback and utterance boundaries across Pipecat and LiveKit, iOS Safari and desktop, clean/impaired networks, barge-in, reconnect and 20-minute dialogue.
- Diagnose audible ducking/underruns from actual measurements before altering gain/buffering. Require independent matched-permission contemporary ChatGPT text/audio benchmark against frozen CQ-01–CQ-16 cases and existing 26-case/520-pair baseline.
- Any nonpassing mandatory scenario remains FAIL/NOT_RUN/BLOCKED, never reclassified as PASS because the release was deployed. Repair in reviewable follow-up and repeat affected gates; preserve rollback control.

### Evidence-state vocabulary
Use `PASS_OFFLINE_CONTRACT`, `PASS_LIVE_VERIFIED`, `BLOCKED`, `FAIL`, `NOT_RUN` and `DEFERRED_POST_DEPLOY` distinctly. Never infer `PASS_LIVE_VERIFIED` from `PASS_OFFLINE_CONTRACT`, parent workflow SUCCESS, source code presence, or provider key presence.

**Source, deployment, invocation, execution, observed user-visible output and actual heard audio are six separate assertions requiring separate evidence.**
