# PR #601 — Failure register and remediation acceptance gates

**Evidence cutoff:** 2026-11-02. Production backend commit `35dbc5bb3fa63b791b457c9ddfc10ee361eff5ae`. This register separates observed failures from unverified risks. PR #600 remains a separate draft; avoid duplicate implementation or unsafe cherry-picks.

| ID | Severity | Classification | Evidence | Repair investigation and acceptance gate |
|---|---|---|---|---|
| F01 | P0 | CONFIRMED | Railway unified-turn logs: repeated OpenAI HTTP 401 invalid API key in shadow/model path; `unified_turn_reasoning_service.py` catches model-call exception and returns error | Inspect effective selected provider, explicit overrides, shadow/live model resolver and credentials without exposing secrets. On auth failure, do not repeatedly retry a known-bad key. Route only to an authorized configured healthy provider, or report provider unavailable. Test both live and shadow, no silent provider switch against user policy. |
| F02 | P0 | CONFIRMED handoff behavior; outcome risk | `run_unified_turn_shadow` returns error, and live caller marks fallthrough and returns `None` at `unified_turn_reasoning_service.py` ~2408-2443 | Trace classical caller after fallthrough. Regression test preserving conversation history, task state, provider selection, connector intent and approval state through 401; verify no duplicate writes or invented completion. |
| F03 | P1 | CONFIRMED user-facing symptom | Production Pipecat/ElevenLabs logs generated repeated generic “I may be missing context” clarification; sampled deep turn first text ~7,993 ms | Correlate exact voice turn with 401, gateway, context payload and composer. Repair fallback response only after proving cause. Test non-repetitive context-aware recovery and task continuation. |
| F04 | P1 | CONFIRMED latency | Voice cognitive LLM first_text_delta_ms ~7,993 in one deep turn, despite ElevenLabs TTFA ~0.15–0.17 s | Break down pre-model/model/first-token/tool/queue and compare against targets; avoid treating fast TTS as fast full answer. Preserve genuine task quality. |
| F05 | P1 | CONFIRMED connector health issue | Production `slack_auth_test_failed ... invalid_auth` repeatedly for one connector | Isolate connector credential/refresh/revocation and retry cadence; avoid broad Slack claims or changing user credentials. Report affected connection accurately; acceptance: bounded backoff and actionable reconnect status. |
| F06 | P1 | CONFIRMED persistence failure | `workflow_failure_prediction_org_failed` with insert/upsert error in Railway logs | Retrieve full sanitized DB error and schema/migration context; verify transactional behavior, retry/idempotency and alerts; do not assume root cause before evidence. |
| F07 | P1 | REPORTED / NOT YET MEASURED | User heard choppy, fading audio; no raw playback inspection yet | Correlate server TTS frames with client jitter/PCM queue/ducking/gain/interruption; capture actual output and device tests. No acoustic pass based only on TTFA. |
| F08 | P1 | OBSERVED but ambiguous | Pipecat idle timeout cancelled pipeline worker; may be normal lifecycle | Correlate cancellation with session state and expected idle policy; test reconnect, interruption, 20-min session; do not classify idle cleanup as defect without evidence. |
| F09 | P0 acceptance | UNVERIFIED | Seven intelligence capabilities and persona manifests exist at deployed SHA; no correlated per-turn proof | Instrument bounded evidence for all seven (including deferred), persona source/selection/injection, text/voice parity and final answer effect. Ensure advisory intelligence never grants permissions. |
| F10 | P0 acceptance | UNVERIFIED | Autonomous task/connector completion not proven for Outlook-after-Gmail scenario | Test connector inventory → authorized Outlook discovery → real read → cited response; preserve task state and governed-write approval. Record actual provider invocation, never infer success from prose. |
| F11 | P1 | EXPECTED deployment gap | PR #600 draft is not in deployed main; PR #601 documentation not deployed | Reconcile PR #600 changes into combined test tree when ready; retain authorship, avoid duplicate code and do not count draft changes as live. |
| F12 | P1 | OBSERVABILITY GAP | Railway tracing disabled; effective variable values redacted by OAuth, though voice flags logged | Introduce privacy-safe correlated turn ID, provider family/model (not keys), capability/agent evidence, tool invocation, response and audio-playback outcomes; verify no secrets or cross-tenant data in logs. |
| F13 | P2 | SECURITY OBSERVATION, NOT A DEFECT YET | HubSpot inbound webhook with invalid signature returned HTTP 401 | Confirm rejection is expected; no remediation if protective behavior is correct. |
| F14 | P1 | UNVERIFIED | Frontend current hosting/deployment SHA and audio client build not yet reconciled | Verify actual Vercel/other frontend production deployment and version against backend; test playback/client-server compatibility. |

## Repair order
1. **F01 + F02** model auth/fallthrough, preserve task and permissions; include negative provider and duplicate-write tests.
2. **F03 + F04 + F10** contextual connector execution, repetition and latency with an Outlook scenario.
3. **F07 + F08 + F14** audible voice continuity and client deployment verification.
4. **F09 + F12** seven-intelligence/personality integration and observable acceptance.
5. **F05 + F06** independent Slack auth and prediction persistence defects (parallelizable; no secret rotations without permission).
6. **F11** integrate draft #600 only after code review; **F13** close if security check expected.

## Completion criteria
Each item must have owner/source file, root-cause evidence, minimal integration repair, deterministic regression test, exact combined-tree CI result, and when authorized live verification. Skipped provider/physical tests remain **not run**, not passes. Preserve tenant IAM, approval, write fences, consent, privacy, model policy, and no paid-provider testing or production deploy without authorization.

**Status:** Failure register created for remediation; this is not a claim fixes have been made. PR #601 stays draft and **NOT_CERTIFIED**.
