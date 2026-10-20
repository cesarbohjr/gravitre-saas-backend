# Phase 1 perception remediation

Scope: corrections to the original artifact-readiness branch, existing shared
text/voice intelligence path and Pipecat pipeline. No new intelligence engines,
model training, schema changes or production configuration changes.

## Implemented corrections

| Gap | Correction | Evidence required in live acceptance |
| --- | --- | --- |
| Shortcut bypasses context and sentiment | Shared `perceive_turn` runs before routing shortcuts; respects organization sentiment preference and retains history. Spoken understanding keeps the existing rule-first, no-extra-LLM behavior. | Compare typed and spoken requests; inspect contextual extraction, classification, history and org settings. Measure perception overhead. |
| LIVE response ignores conversational adaptation | Closed-set adaptation reaches unified prompt assembly through the existing classification object. Arbitrary text and non-string values cannot supply instructions. | Frustration gets a brief acknowledgment; uncertainty gets clear options; urgency gets concise answers. Facts and approvals must remain unchanged. |
| Speech has no connection to perception | The same adaptation reaches the existing Pipecat intelligence event; bounded stability updates use the selected synthesizer's own Settings type. Settings reset between turns; raw model-generated delivery tags remain untrusted and stripped. | Capture the settings update before answer audio and compare actual listening experience. This is delivery control, not a claim of laughter/giggle generation. |
| Live acoustic path disconnected | A tap after STT observes forwarded microphone PCM, retaining only a rolling eight-second window. One background analysis per session; no PCM is persisted. Correct-rate WAV goes to the existing tenant-scoped audit writer. Non-mic origins, unsupported channels/rates, invalid formats and silence do not generate fabricated observations. | In a microphone session, read back `voice.acoustic.analyzed` / `voice.acoustic.flagged_for_review` with the correct org and conversation. Verify frame passthrough and shutdown. |
| Unsupported acoustic accuracy claims | Removed fixed literature accuracy bands and numeric confidence. Acoustic data is explicitly unvalidated observation and cannot enter adaptive-learning signals or count as a business outcome. | Verify audit metadata is unvalidated and measured learning counts do not change from audio alone. |
| v3 comparison uses the wrong protocol | Existing opt-in A/B selection now constructs `ElevenLabsDialogueTTSService` for v3 and `ElevenLabsTTSService` for Flash. Added `eleven_v3_conversational` to the existing eval allowlist. Session metadata identifies the actual protocol. | Verify selected model/protocol, successful audio, interruption cancellation, playback/history consistency, latency and listening quality with the actual provider. |
| Artifact metadata mistaken for runtime evidence | Earlier branch correction downloads/deserializes the registered artifact before reporting it loaded. | Authenticated org-specific artifact and inference probes; registry rows alone are not accuracy evidence. |

The Flash default and ordinary model-resolution safeguard remain in place.
The existing `VOICE_TTS_AB_V1=true` and
`VOICE_TTS_AB_MODEL=eleven_v3_conversational` select the comparison in an isolated
test deployment. These are deployment settings, not per-user trial switches;
do not enable them on a shared production service merely to test one session.
No environment variables have been changed by this remediation.

Provider protocol references:

- https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tdd
- Installed Pipecat 1.12 `services/elevenlabs/dialogue/tts.py` and `tts.py`.
- Existing deployment dependency: `pipecat-ai>=1.12,<1.13`.

## Verification and release gates

Offline tests use `-p tests.offline_network_guard` to reject outbound socket/DNS
calls. They do not send test prompts to provider APIs or use production secrets.
The existing simulated voice harness runs the actual pipeline with scripted
providers and modelled browser playback. Its passing tests establish pipeline
reachability, not perceptual quality or production latency.

The natural-prosody contract previously searched for constructor text and a
comment in `pipeline.py`. Construction now lives in `tts_factory.py`; the test
was strengthened to instantiate the provider and assert actual auto mode and
sentence aggregation. No expected behavior was weakened.

Before production acceptance, run CI, deploy this exact revision to the intended
test environment, then run the standing LLM batteries in
`docs/delivery/llm-quality-test-suite.md` and actual microphone-to-speaker trials.
The live batteries are required because unified prompt assembly changed.

| Live scenario | Required result |
| --- | --- |
| Same question typed and spoken | Same evidence/intent/tool authority; appropriate channel formatting |
| Frustrated, uncertain, urgent turns followed by a neutral turn | Appropriate bounded adaptation, then reset; no asserted emotional certainty |
| Connector lookup and correction | Correct target, grounded readback, preserved conversation context |
| Staged write with correction before approval | Approval bound to the revised action; no premature or duplicate execution |
| Interrupt, backchannel, silence and noisy mic | Stop/resume and history consistent with actual playback; no answer to silence |
| Flash versus v3 conversational | Correct protocol and audible result; measure first meaningful audio and recovery; listening assessment recorded |
| Foreign organization and synthetic audio | No cross-tenant access and no synthetic acoustic observations entering real learning |

Live provider calls, production deployment, full CI and measured learning remain
separate acceptance gates. No production-operational certification is claimed
from offline tests.

## Final local result

**1,722 tests passed; zero failures, errors or skips** in the consolidated run.
This included the complete `tests/services/pipecat_voice` directory, unified
reasoning, knowledge context, text/voice task parity, classifier honesty, spoken
shortcut regressions, voice usage/acoustic tests, catalog artifact checks and
`tests/e2e/voice_scenarios/test_voice_scenarios.py`. Provider sockets/DNS were
blocked using `-p tests.offline_network_guard`.

The recorded summary is `phase1-perception-verification-20261020.json`.
`git diff --check` and compilation of changed modules also passed locally.
Deprecation warnings remain in existing Pipecat APIs; no test assertions were
relaxed to suppress failures.

Restored perception adds memoized org/domain lookups to shortcut turns, so live
latency must be measured before accepting the change in production. This report
is readiness evidence for CI and isolated live testing, not a live quality score.
