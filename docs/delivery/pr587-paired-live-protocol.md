# Paired voice execution protocol

The controller is `scripts/voice_paired_live.py`; the execution job is
`paired-runtime-readiness` in `voice-gates-2-3.yml`. It uses the exact checked-out
PR head, the pinned acceptance database, an Auth-verified smoke actor and an
explicitly internal smoke organization. It does not deploy or select an engine.

## Transport and provider scope

Both paths use the unchanged production `build_pipecat_voice_task`: live
Deepgram, Gravitre's cognitive bridge and Anthropic, then live ElevenLabs.
Pipecat uses an actual authenticated loopback WebSocket. LiveKit uses native
RTC audio and the existing candidate adapter against a hash-verified, ephemeral
loopback LiveKit server. This compares transports, not independent orchestration
engines. The controller WebSocket is not the production HTTP router.

One fixed synthetic speech recording is generated once and replayed unchanged.
The same PCM hash applies to every trial. No private user speech is used.

## Matched scenarios and criteria

Each transport runs baseline, interrupt and reconnect. Reconnect creates a fresh
transport session against that engine's original conversation ID; it repeats
the identical recording. This proves a new session can generate audio for an
existing conversation only. It is not a semantic memory-restoration score.

Baseline/reconnect must yield non-silent generated audio and a live Deepgram
read-back containing the expected sky/light explanation. An acknowledgment,
startup greeting or canned failure alone does not pass. The interrupt trial
sends the canonical control after generated speech begins. Its original reply
must stop within 500 ms at the receiving PCM boundary. Reply identity separates
a later acknowledgment from the interrupted reply. Physical speaker cutoff and
echo suppression require separate microphone/speaker acceptance.

Latency is measured from input start and input end to first non-silent received
speech, not first RTC silence or first packet. Reconnection additionally records
session start to first speech, including fixed warmup and pipeline startup.
RMS, clipping fraction, audio hashes, WAVs and event-type counts are recorded.
These are signal/content checks, not blinded perceptual quality ratings.

## Independent evidence and incomplete gates

The controller queries durable `audit_events` separately after each session and
records IDs and action names only. It refuses to treat the process-local
`voice_barge_in_write` ledger as an independent provider audit. A truncated query
is identified. Absence of an audit row does not establish absence of a side
effect, so `business_effect_sink_verified` remains false until an independent
controlled connector/provider sink has been exercised and reconciled.

The 115 governed-action regression cases remain a separate layer. They do not
certify a complete speech-to-confirmation-to-authorization-to-provider write.
No customer connector is installed or invoked by this informational experiment.
The existing model router forces OpenAI when `AI_FAILOVER_ENABLED=false`, even
when `PREFERRED_AI_PROVIDER=anthropic`. The isolated job therefore enables its
priority router while explicitly leaving OpenAI and Gemini credentials empty:
Anthropic is the only configured inference provider. No production setting is
changed. The initial run's non-silent spoken errors are not accepted as answers.
Revocation, cancelled/duplicate real writes, seven-capability intelligence,
provider faults, crash recovery, physical audio and human quality review remain
required before final certification. Reports keep `certified: false`.

All failures remain failures. Sanitized diagnostics include exception classes
and stack locations, never provider bodies, keys or raw generated transcripts.
Raw pipeline debug logs stay in the disposable runner and are not uploaded.
