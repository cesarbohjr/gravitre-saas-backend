# Conversational quality, ChatGPT parity and further fine tuning

Status: DRAFT — implementation and product certification pending.
Created: 2026-11-02 (America/Creston).
Baseline: main `35dbc5bb3fa63b791b457c9ddfc10ee361eff5ae`.
Scope: shared text/voice dialogue, capability discovery, provider reliability, natural delivery, and measured product comparisons.

## Problem and intended behavior

The November 2 production voice session repeatedly answered questions about available email connectors with a generic request for context, searched unrelated public material for contextual follow-ups, and failed to identify an existing Microsoft 365 connector. The user reported robotic delivery, limited suggestions, choppy audio and fading.

The intended behavior is a coherent, useful conversation: preserve the active subject across corrections and short follow-ups; inspect authorized workspace capabilities; offer grounded alternatives; ask a precise question only when necessary; recover from failures without looping; and speak smoothly with appropriate pacing and interruptions. ChatGPT parity is a measured engineering objective within declared comparable tasks, not an existing whole-product equivalence claim.

This initial PR adds an execution and acceptance plan. It changes no runtime behavior, provider configuration, credentials, customer surfaces, training jobs or transport defaults.

## Evidence and uncertainty

Read-only production inspection covered 2026-11-03 01:08–01:12 UTC (November 2, 18:08–18:12 America/Creston), against the baseline above.

| Observation | Evidence class | Implication |
| --- | --- | --- |
| Seven unified-turn attempts returned provider 401 / invalid API key and fell through; seven classical answer-path events were recorded | Production audit observation | Restore effective provider/model authentication before interpreting model quality |
| Five first-meaningful-answer metric A observations were 7519, 9528, 6220, 8730 and 6431 ms | Production audit observation | Report filler separately; do not characterize early acknowledgment as answer latency |
| Workspace Microsoft 365 connector status was healthy; Gmail was not among the active connector rows retrieved | Read-only database observation | Discover alternatives and validate action scopes; a stored healthy status alone does not prove executable email access |
| Follow-ups about other email connectors triggered unrelated knowledge/web retrieval and repeated generic clarification | Stored interaction/tool records | Test contextual intent and capability routing across multiple turns |
| Backend contains an appended generic clarification sentence driven by confidence | Source inspection: agent_intelligence.py | Eliminate repetitive fallback behavior without discarding factual checks |
| Overlap ducking enabled; client gain drops to 0.15 while possible interruption is classified | Source plus effective production flag log | Candidate fading mechanism; correlate with audible evidence before changing |
| Worklet queue fades and restarts on starvation; emitted underrun count is not consumed by the inspected player handler | Source inspection | Complete continuity telemetry before attributing or selecting an audio remedy |

Raw session audio was not located. No listening-based diagnosis, causal proof of fading, fresh credential validation, measured model comparison or current ChatGPT/Claude/ElevenLabs product comparison is claimed. Seven attempts are not seven distinct completed human turns; speculative and interrupted work must be correlated by turn identity.

The provider-aware resolver already exists in unified_turn_reasoning_service.py. Do not assume the earlier hardcoded-provider defect is the cause of this production credential failure.

## Existing contracts to retain

- Follow ../ENGINEERING_STANDARDS.md and llm-quality-test-suite.md.
- Extend pr587-chatgpt-product-benchmark.md and scripts/run-conversation-parity-benchmark.py; retain the original 26-case/520-pair and multi-turn/DSPy baselines.
- Keep one shared One Brain and canonical intelligence-layer interfaces. Voice transport must not become a competing action-authorizing brain.
- Independently verify unified and classical fallback entrypoints until their effective authorization and behavior are demonstrably shared.
- Retain tenant boundaries, permission checks, confirmation, revocation, cancellation, idempotency and independent write-audit requirements.
- Preserve #594's separate fast acoustic cancellation gate and disabled/unadvertised disposition until independently certified. This PR cannot close it by changing a latency threshold.
- Existing offline evidence, skipped paid jobs, successful deployment and PR #587's merge are not conversational-quality certification.

## Ordered engineering work

Each workstream needs source changes, regression evidence, production disposition and unresolved limitations before being marked complete. Keep changes in small reviewable commits or linked implementation PRs under this plan.

### 1. Provider reliability and truthful degradation

- [ ] Trace effective model/provider selection across unified reasoning, fallback, composition and evaluation without exposing credentials.
- [ ] Correct the observed production authentication/configuration problem; verify a bounded authorized request against each selected runtime route.
- [ ] Classify authentication errors separately from ambiguity, empty retrieval and unavailable capabilities.
- [ ] Add bounded degraded operation and provider-health backoff so repeated turns do not repeatedly pay for a known-invalid credential.
- [ ] Use fallback only through an explicitly configured, authorized route; expose an honest limitation when no functional route exists.
- [ ] Record whether the primary or fallback path served each reply, with sanitized error categories and turn correlation.

### 2. Contextual dialogue and connector discovery

- [ ] Resolve short references against the latest task, previous question and heard assistant history before choosing tools.
- [ ] Route workspace capability inventory to connector availability services; keep public catalog discovery separate from installed and executable capability checks.
- [ ] Validate Microsoft 365 availability, action support and OAuth scopes before offering execution; distinguish disconnected, unsupported and insufficient-scope cases.
- [ ] Search the broader authorized connector catalog when the requested capability is absent; report grounded alternatives without installing or granting anything.
- [ ] Handle speech corrections, ambiguous transcription, pronouns, topic changes, long context, reconnect and switching between text and voice.
- [ ] Preserve explicit user choice and avoid inventing accounts, integrations, capabilities or completed actions.

### 3. Useful recovery, suggestions and response ownership

- [ ] Replace generic confidence suffix behavior with a contextual recovery decision.
- [ ] Separate missing evidence, missing essential input, transcription uncertainty, unavailable tools and provider failure.
- [ ] Detect repeated unsuccessful clarification; use existing context, change retrieval strategy or explain a specific blocker.
- [ ] Offer relevant next steps and alternatives when they advance the user's stated goal; suggestions do not authorize writes.
- [ ] Assign one final response owner; document what each upstream classifier, validator and composer may change.
- [ ] Consolidate overlapping spoken instructions and measure whether length limits suppress useful suggestions or explanations.
- [ ] Preserve groundedness and action honesty while improving natural wording, depth and variation.

### 4. Audio continuity and conversational timing

- [ ] Collect turn/reply-bound TTS input boundaries, generated/received/played audio timing, queue depth, underrun duration/count, duck/unduck events, flush reason and audio-context state.
- [ ] Distinguish provider silence, intentional linguistic pauses, client starvation, false overlap classification and genuine interruptions.
- [ ] Reproduce fading on real iOS Safari and desktop browsers, speakers and headphones, clean Wi-Fi and impaired networks.
- [ ] Evaluate bounded overlap classification and timely gain restoration without weakening explicit stop or cancellation handling.
- [ ] Compare semantic phrase/sentence chunking, first-chunk policy, buffering, voice settings and delivery tiers using identical speech.
- [ ] Compare current PCM/WebSocket playback with the existing LiveKit/WebRTC candidate using matched functional, continuity, cost and governance trials.
- [ ] Promote a transport or synthesis configuration only after measured improvement and rollback readiness.

### 5. Fine tuning and controlled optimization

- [ ] Tune dialogue prompts, context selection, capability retrieval, model tiers, TTS chunking and prosody using a versioned evaluation set.
- [ ] Keep training and held-out evaluation sets separate; track prompt/config/data hashes, baseline, candidate, cost and per-category regressions.
- [ ] Use existing DSPy compilation/promotion controls where applicable; reject candidates that improve averages while degrading mandatory cases.
- [ ] Evaluate whether actual model weight fine-tuning is needed only after routing/configuration defects are repaired.
- [ ] Any weight training requires a separate data-purpose/consent decision, qualified data, budget, evaluation and rollback proposal. This PR authorizes no transcript upload, third-party training or new memory purpose.
- [ ] Never train on the user's production conversation merely because it was available for debugging.

## Mandatory regression scenarios

Use synthetic workspace facts and controlled accounts. These are unexecuted acceptance cases, not result fixtures.

| ID | Scenario | Required behavior |
| --- | --- | --- |
| CQ-01 | Gmail unavailable; Microsoft 365 present | Identify the alternative and verify executable scopes |
| CQ-02 | “What other email connectors do I have?” then “Do I not have others?” | Continue workspace inventory without unrelated public search |
| CQ-03 | Garbled opening speech followed by clear correction | Use the correction; ask only the remaining essential question |
| CQ-04 | Same intent repeated after an unhelpful reply | Repair the strategy; no repeated generic-context loop |
| CQ-05 | “Let's pick something else” | Acknowledge topic change naturally; no irrelevant retrieval |
| CQ-06 | Missing installed capability; supported catalog alternative exists | Explain installed versus available and offer a useful choice |
| CQ-07 | Connector exists but lacks scope | State the exact limit; do not claim execution readiness |
| CQ-08 | Provider 401 during a multi-turn conversation | Bounded truthful degradation; no unrelated ambiguity explanation |
| CQ-09 | “Any suggestions?” after a factual answer | Give grounded, relevant options with reasons |
| CQ-10 | Brief backchannel, breath or speaker echo during output | No unintended cutoff or sustained attenuation |
| CQ-11 | Genuine correction or explicit stop during output | Yield correctly and preserve action authority |
| CQ-12 | Stop speaking but keep working versus cancel the task | Distinguish audio control from task cancellation |
| CQ-13 | Reconnect, then text-to-voice transition | Preserve current task, approval state and heard history |
| CQ-14 | Twenty-minute conversation with topic changes | Maintain coherence and stable delivery without template drift |
| CQ-15 | Impaired network and mobile audio interruptions | Recover honestly; record continuity defects and network conditions |
| CQ-16 | Cross-tenant request, revoked permission and repeated approval | Zero unauthorized or duplicate writes across all paths |

## Acceptance and parity scoring

All results start NOT RUN / NOT_CERTIFIED. The existing product benchmark requirements remain mandatory; the following gates add specificity and do not lower them.

| Dimension | Required evidence / proposed target |
| --- | --- |
| Critical regressions | Every CQ-01–CQ-16 invariant passes; zero unauthorized/duplicate writes or fabricated capabilities |
| General task success | At least 95% over a frozen representative multi-turn set, plus all existing dimension coverage and comparison requirements |
| Simple reply latency | Target median first meaningful audio <=1000 ms and P95 <=2000 ms on declared clean-network/device conditions; filler excluded |
| Relative latency | Also satisfy existing P95 <=1.2x observed reference +250 ms; disclose tool-task and impaired-network strata separately |
| Audio continuity | Zero unintended duck/cutoff or starvation on controlled clean-network runs; correlate interruptions and pauses before scoring |
| Speech naturalness | Existing blinded independent-rater rubrics, no more than 0.5 mean quality-point gap to the observed reference |
| Comparison integrity | Contemporary actual ChatGPT sessions, matching tasks/conditions, private audio evidence and hashes; API completions cannot stand in for the product |
| Fine-tuning benefit | Held-out improvement with per-category results, latency/cost and no mandatory regression |
| Operational acceptance | Exact deployed SHA and runtime configuration, real devices, both answer paths, rollback evidence and named remaining gaps |

Freeze case counts, device/network matrix, scoring and numerical thresholds before collecting candidate results. A subsequent change invalidates earlier comparison evidence; do not adjust thresholds to fit a candidate.

ChatGPT is the primary reference. Claude dialogue and ElevenLabs voice agents may be secondary references where actually accessible and comparable. Record product/model/version/date/feature limits rather than assume an equivalent configuration. Unsupported connector tasks remain explicit non-comparable gaps. Scope claims to observed tasks; retain whole_product_equivalence_claim=false.

## Evidence, release and current disposition

- [ ] Offline regression and contract checks pass for the exact candidate SHA.
- [ ] Full CI passes; prompt/model/spec changes rerun the full standing combined battery.
- [ ] Live-provider, actual-device, blinded review and contemporary reference evidence exist.
- [ ] Deployment and authenticated text/voice acceptance match the certified SHA/configuration.
- [ ] Metrics include primary/fallback route, first meaningful audio, continuity and task outcome.
- [ ] A rollback plan and baseline are retained; unresolved failures remain merge/release blockers for this quality release.

The initial plan commit requires documentation/link review only. No runtime tests are claimed. Runtime fixes, production credential validation, physical listening trials, reference comparisons and parity certification remain pending.

Existing refusal to fund paid-provider tests remains in force: creating this PR does not authorize billable inference, training, a paid transport subscription or deployment. Record those gates NOT RUN until separately authorized; do not silently skip them and declare parity.

No production migrations, runtime toggles, connector grants, customer-facing claims or automatic learning are introduced.
