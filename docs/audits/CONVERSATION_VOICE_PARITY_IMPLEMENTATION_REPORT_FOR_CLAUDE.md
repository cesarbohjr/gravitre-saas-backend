# Gravitre Conversation + Voice Parity — Implementation Report for Independent Review

**PR:** #301  
**Branch:** `fix/conversation-parity-p0`  
**Review head:** 278ca328f8910046005ca73a6285ed16ff3504d0  
**Base:** `930db32a891af551dfbeb6001d5f1af38c920e67`  
**Scope:** P0/P1 conversational text↔voice continuity, evaluation integrity, model routing, voice interruption/duplex evidence, permanent parity contract, and owner-live acceptance.

## 1. Reviewer mandate

Review this implementation adversarially. Do not accept this report as proof. Inspect the exact PR/head, code, tests, workflow logs and changed-file history. Try to falsify every claim below. Classify each material claim/finding as **CONFIRMED / PARTIAL / REJECTED / UNPROVEN** and cite file + line/commit/workflow evidence.

The implementation deliberately separates:
1. code implemented,
2. automated CI evidence,
3. synthetic/browser harness evidence,
4. production telemetry,
5. human owner-device evidence.

A lower layer never proves a higher layer.

## 2. Original high-risk findings

The independent audit identified:
- voice socket context was fresh/in-memory while text had durable conversation state;
- reconnect and text↔voice continuity were therefore not proven;
- production conversational gate contained exact prompt-keyed canned replies that contaminated behavior evidence;
- model routing could silently use lower-quality/legacy mini paths;
- interrupted speech could persist/generated text the listener never heard;
- browser/server barge-in ownership and the duplex guard needed verification;
- prior latency evidence mixed first hold audio with first meaningful answer audio;
- physical audible output and owner acceptance remained unproven.

## 3. Durable text↔voice state implementation

`backend/app/services/pipecat_voice/cognitive_llm.py` now hydrates an owned conversation before the first Pipecat turn:
- verifies conversation ownership by org/user;
- loads rolling summary;
- loads the most recent durable conversation messages;
- normalizes user/assistant history;
- merges durable history with in-socket Pipecat history;
- detects reconnect overlap to avoid replay duplication;
- caps merged context to the same bounded recent-history policy;
- passes `history_summary` into the same cognitive execution path;
- persists completed voice turns through the same durable conversation persistence used by text;
- updates in-memory durable history after persistence.

Regression coverage is in `backend/tests/services/pipecat_voice/test_durable_conversation_parity.py`.

Reviewer must specifically test/falsify:
- cross-tenant ownership isolation;
- duplicate user/assistant inserts;
- differing Pipecat vs durable message shapes defeating overlap detection;
- summary-loader signature/schema assumptions;
- text→voice→reconnect→text with a real conversation;
- whether text itself server-hydrates or still depends on client history;
- circular/layering risk from voice importing private assistant-router persistence helpers.

## 4. Benchmark contamination removed

`backend/app/services/conversational_turn_gate.py` no longer returns exact canned answers for the known “improve SEO/hiring/priorities/outbound/contract/SaaS access” prompts or exact definition prompts. Those helpers now fall through to normal reasoning.

`backend/tests/services/test_conversation_parity_no_canned_eval_answers.py` includes known examples plus unseen paraphrases.

The intent is that production behavior cannot pass a benchmark merely because the benchmark wording is hard-coded.

Reviewer must search the entire repository for equivalent prompt-specific answer banks, test-only production branches, hidden regex answer keys, or fixtures that still contaminate the scored path.

## 5. Model routing

`backend/app/services/unified_turn_reasoning_service.py` resolves conversational depth to an explicitly configured `voice_conversational_model` only when one is set. Otherwise it inherits the standard medium/high OpenAI tier.

Current `MODEL_TIERS` in `backend/app/config.py`:
- low: `gpt-5.4-mini`
- medium: `gpt-5.5`
- high: `gpt-5.5`

Full unified reasoning no longer silently falls through to a legacy mini model. Explicit task-tier or explicit voice override remains allowed and testable.

Coverage: `backend/tests/services/test_conversation_parity_model_routing.py`.

Reviewer must trace actual runtime routing, not just unit helpers: ordinary text, complex text, ordinary voice, tool-heavy voice, agent-pinned model, provider failover, missing-provider configuration, and production env overrides.

## 6. Permanent behavioral parity contract

A provider-neutral scenario registry/scoring harness was added for text, memory, cross-modal, voice, governance, honesty and recovery behavior. It scores invariants/dimensions rather than exact prose and compares Gravitre and competitors from the same run instead of assuming competitor scores.

Key files:
- `backend/app/services/conversation_parity_benchmark.py`
- `backend/app/services/conversation_parity_scoring.py`
- `backend/tests/services/test_conversation_parity_benchmark.py`
- `scripts/run-conversation-parity-benchmark.py`
- `.github/workflows/conversation-parity-contract.yml`

This is a contract/evaluation scaffold, not a claim that current ChatGPT/Claude have already been exhaustively live-benchmarked.

## 7. Voice duplex guard investigation

The historical browser duplex guard was described as backend-independent, but workflow evidence showed requests escaping through Next voice route handlers to `127.0.0.1:8000`, causing `ECONNREFUSED` before the mocked Deepgram socket could open.

The E2E-only route behavior is now explicitly self-contained under `PLAYWRIGHT_E2E=1` for:
- `apps/web/app/api/voice/stt/live-token/route.ts`
- `apps/web/app/api/voice/turn-taking/event/route.ts`
- `apps/web/app/api/voice/session/turn/route.ts`

Production behavior is unchanged when the E2E flag is absent.

Reviewer must verify this does not weaken production coverage, leak E2E behavior into deploys, or turn the guard into a tautology. The guard should prove browser capture/AudioContext/PCM/session behavior while separate backend tests prove backend voice endpoints.

## 8. Interrupted speech / barge-in

This remains a critical falsification target. The cognitive bridge historically had access to the model's full generated completion, while a barge-in may mean only a prefix was actually audible. The required invariant is:

> Durable assistant history after interruption must reflect what was actually delivered/heard (or an explicit interrupted-state representation), never an unseen generated tail.

Review `interrupt_reporter`, spoken-alignment tests, Pipecat interruption events, client playback reconciliation, and the new durable persistence path together. Do not mark this PASS from a full-completion unit test.

## 9. Latency evidence

Prior ~254 ms “first audio” evidence included plan-hold/early audio and must not be represented as speech-end→first-meaningful-answer latency. Any parity claim must use comparable metric boundaries across Gravitre/ChatGPT/Claude and distinguish:
- endpoint/finalization;
- first model token;
- first speakable/meaningful chunk;
- first audible playback;
- completion;
- speculative/hold audio.

## 10. Owner-live acceptance

`docs/delivery/conversation-parity-owner-acceptance.md` is the final human gate. It requires both desktop Chrome and iPhone, real owner tenant/account/mic/speaker/connectors, audible output, five consecutive exchanges, text→voice, reconnect, voice→text correction, backchannel, barge-in, thinking pause, governed write/approval and recovery with telemetry correlation.

`OWNER_LIVE_ACCEPTANCE` remains **NOT RUN** until that human evidence exists.

## 11. CI incident history and fixes

During this PR, two infrastructure/test-contract failures were found rather than waived:
- parity workflow initially lacked pytest; dependency was added;
- next run exposed backend import path (`ModuleNotFoundError: app`); workflow now executes focused pytest with `PYTHONPATH=.`;
- voice duplex browser guard exposed the Next route proxy leak to an absent localhost backend; E2E-only route mocks were added as described above.

Reviewer should inspect the final head workflow results. Earlier red runs are useful evidence of what was fixed but are not final-head status.

## 12. Evidence-status rules

At review time:
- **CODE IMPLEMENTED** means present in the exact head.
- **CI PASS** means the exact head workflow completed successfully.
- **BROWSER/SYNTHETIC PASS** is not physical audio proof.
- **PRODUCTION PASS** requires production tenant/telemetry.
- **OWNER LIVE PASS** requires the documented physical acceptance.
- Anything else is **UNPROVEN**.

## 13. Required Claude review output

Return:
1. executive verdict;
2. severity-ranked findings (P0/P1/P2);
3. a ledger of each claim above as CONFIRMED/PARTIAL/REJECTED/UNPROVEN;
4. exact file/line, commit, test or workflow evidence;
5. regressions/security/tenant-isolation concerns;
6. whether benchmark contamination is genuinely removed;
7. actual runtime model-routing map;
8. whether text↔voice durable continuity really survives reconnect;
9. whether interrupted assistant persistence matches actually heard speech;
10. whether client/server interruption authority can misclassify backchannels;
11. whether the duplex guard now tests the intended boundary rather than mocking away the behavior;
12. remaining work required before merge;
13. remaining work required before claiming parity with current ChatGPT/Claude.

Do not give credit for documentation claims without code/evidence. Do not treat UNPROVEN as FAILED, and do not treat code/CI as production or human proof.
