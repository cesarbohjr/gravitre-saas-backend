# Voice 3.0 architectural reassessment — V5 addendum

Status: source assessment; no candidate certified. Parent plan: gravitre-voice-3-master-engineering-qa-plan.md. Baseline source: baaebe1ec2b89c993f7a05b11877fb232148e867. Existing September 5 ADR remains operative until a replacement is approved with evidence.

## Findings
- Flux owns EOT; pipeline.py explicitly omits Silero on Flux. Do not remove the committed-turn barrier or backchannel strategy on assumptions of duplication.
- Current FastAPI WebSocket transport and browser PCM player own audio delivery and buffering; native RTC is a legitimate controlled comparison.
- livekit_candidate.py is an isolated RTC-to-WebSocket adapter, not a native reference pipeline. engine_benchmark.py intentionally rejects aggregate-only evidence as certification.
- tts_factory.py separates TTS and Dialogue adapters; v4 Turbo is not currently allowlisted. Verify pinned SDK/adapter, protocol, voice availability and pricing before enabling.
- Freeze further speculative custom DSP optimization pending transport/engine attribution. Retain prior code and regression evidence.

## Candidates
A: exact existing fixed-control path; B: native Pipecat WebRTC with same providers and canonical cognition; C: ElevenLabs Speech Engine using documented Pipecat integration with Gravitre-owned reasoning; D: native realtime speech-to-speech reference with all business actions delegated to canonical server authority. First use a tool-free reference workload to isolate speech loop, then identical canonical-kernel fixtures. No production router activation.

## Required gates
1. Inventory actual provider/SDK versions, supported endpoints, session identity, credentials, voice identity, region, retention and costs; no credentials exposed to browser.
2. Isolated reference: paired inputs, same device/network and workload, randomized order; record mic end, committed turn, first text, first provider audio, first audible audio, cancellation and subsequent completion. Minimum 20 paired trials per engine per workload for screening, report p50/p95 and all failures; no parity claim from this sample alone.
3. Functional fence: server-bound tenant/user/session and committed revision, no speculative side effects, no provider-issued approval or authority, cancellation fences worker threads, durable executed outcomes survive interruption, exact spoken-history reconciliation, duplicate/reconnect/replay tests.
4. Acoustic and quality: no premature speech, no unintended gaps or cross-turn bleed; preserve existing applicable synthetic thresholds; measure real-device latency, naturalness, prosody, interruptions and task completion; blinded review, actual competitor measurements with consent, cost and privacy review.
5. Promotion: no safety regression; paired evidence, exact SHA, recording integrity, independently reviewed quality and explicit approval; retain rollback and current V0–V7 sequencing. Synthetic success is not live certification. No production deployment or paid live activation under this addendum.

## Sources reviewed
- https://elevenlabs.io/docs/overview/capabilities/speech-engine
- https://elevenlabs.io/docs/eleven-api/guides/how-to/speech-engine/pipecat-integration
- https://elevenlabs.io/docs/overview/models
- https://docs.pipecat.ai/client/concepts/choosing-a-transport

## Next implementation
Build provider-native tool-free reference and paired baseline measurement, then native WebRTC and Speech Engine adapters behind isolated acceptance entry points. Confirm exact SDK compatibility first. Retain canonical governance and prior ADR until comparative evidence warrants a new decision.
