# PR601 live voice trace checkpoint

Read-only Railway production deploy logs, deployed main SHA 35dbc5bb3fa63b791b457c9ddfc10ee361eff5ae. Sensitive identifiers and credential fragments deliberately excluded.

## Directly observed
- Pipecat pipeline active, Deepgram Flux STT active, ElevenLabs TTS active.
- Effective voice flags event reports unified_turn_live_enabled=True, internet_research_enabled=True, voice_pipecat_enabled and voice_expressive_tts_v1 enabled; Flux STT, Nova-3 fallback and eleven_flash_v2_5 TTS.
- Actual conversation tiers medium and deep observed in cognitive_llm logs.
- Speculative generation adoption/discard observed.
- Seven searchKnowledgeBase tool-latency events observed; elapsed_ms 0-1. These events alone do not establish successful source retrieval or task completion.
- Unified-turn model path logs repeated HTTP 401 invalid OpenAI API key errors, including voice turns. This is a confirmed model-authentication blocker; whether a correctly configured provider fallback was attempted remains unverified.
- Deep turn first_text_delta_ms=7993 in sampled voice turn; generated clarification text indicates missing context, despite earlier user requests. Causation between model 401 and this particular response needs correlation, not inference.
- ElevenLabs TTFA sampled approximately 0.150-0.167 seconds, which measures TTS initiation, not end-to-end conversational latency or audible continuity.
- Pipecat idle-timeout cancellation observed. This may be normal lifecycle cleanup; investigate only if it aligns with unexpected session termination.

## Priority next engineering checks
1. Trace unified-turn 401 handling to fallback and response composer, including chosen provider and retry backoff; avoid logging credential text.
2. Trace context/history and connector discovery into the voice prompt and tool dispatch for the email-provider request.
3. Trace all seven intelligence evidence slots and selected agent persona into final model prompt.
4. Validate user-task completion and playback independently; no parity certification from these logs.

Status: runtime voice components confirmed ACTIVE, unified model-auth path FAILED, complete autonomy and personality integration NOT_VERIFIED. No production changes.
