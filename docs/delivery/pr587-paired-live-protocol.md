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

Each transport runs baseline, interrupt and reconnect.
If its baseline fails, dependent interruption/reconnect scenarios are marked
NOT RUN and the overall execution fails; a spoken error is not a valid reply to
interrupt or a meaningful conversation to restore. This saves unnecessary
provider calls without relaxing any required gate.

Reconnect creates a fresh
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

## Initial execution checkpoint

Run `41129683591`, source `e0ca9dec9cf2780ea73c15156a172f9f20c95e35`,
returned audio over both real transports. Artifact `13012876954` contains the
shared input PCM hash `5b47a4b2c270a59dbd3238a89b1988f944dd246dd8e2d607a23d15168480d4a0`.
Each session also emitted an error event; independent database reads found no
durable user/assistant messages or conversation audit rows. Its permissive
per-row PASS values are rejected as end-to-end voice evidence. Source
`5bd2530c96c8c7513ecae095d884ff6baa48217f` adds explicit error rejection,
semantic output checks, paired interruption/reconnection and sanitized exception
locations. Source `009410188eac4efb59c5c2087b7a5c75985ef109` corrects the
isolated model-router configuration. Neither correction alone certifies runtime.

A separate direct database check confirmed zero connectors in the smoke tenant.
Full business-write safety remains unexecuted until an isolated provider fixture
is available; an empty audit result is not a substitute.

Run `41132228873`, source `3036d227f43986c0e2dafbe31a120017096eb454`,
artifact `13014460189`, reproduced the failure before any audio/provider work
through the canonical service client. The validity-only request hook confirmed
the correct acceptance host and configured key, a nonempty bearer, and control
characters plus trailing whitespace in headers. No header values were exported.
`Settings` now trims surrounding whitespace from Supabase API tokens, rejects
empty/internal whitespace/control characters, and hides validation input values.
The legacy JWT signing secret is unchanged. A loopback HTTP/1.1 regression uses
the real canonical client and SDK with a newline-terminated fixture credential.
