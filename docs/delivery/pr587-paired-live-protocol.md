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
Subsequent executions download the immutable recordings from run `41134456513`
and check both PCM hashes before playback. They fail if the artifact is absent
or altered; they never silently synthesize a different input on a rerun.

## Matched scenarios and criteria

Each transport runs baseline, interrupt control, spoken cancel and reconnect.
If its baseline fails, dependent interruption/reconnect scenarios are marked
NOT RUN and the overall execution fails; a spoken error is not a valid reply to
interrupt or a meaningful conversation to restore. This saves unnecessary
provider calls without relaxing any required gate.

Reconnect creates a fresh
transport session against that engine's original conversation ID; it repeats
the identical recording. This proves a new session can generate audio for an
existing conversation only. It is not a semantic memory-restoration score.

Baseline/reconnect must yield non-silent generated audio and a live Deepgram
read-back containing the provided welcome-note rewrite (Alex, team, welcoming
sentiment, no configuration/knowledge refusal). An acknowledgment,
startup greeting or canned failure alone does not pass. The interrupt trial
sends the canonical control after generated speech begins. Its original reply
must stop within 500 ms at the receiving PCM boundary. Reply identity separates
a later acknowledgment from the interrupted reply. Physical speaker cutoff and
echo suppression require separate microphone/speaker acceptance.

The spoken-cancel case replays a second, separately synthesized fixed recording
("Cancel it. Do not send anything.") through the actual audio/STT path. It sends
no out-of-band interrupt control. That identical cancel PCM and its digest are
shared by both transports. Original-reply receiver cutoff is reported from both
cancel-speech start and end; the limit is 500 ms after cancel-speech end. The
control-only case retains its separate 500 ms control-to-cutoff limit. Neither
case alone certifies a business write was pending or prevented.

The final-fence experiment starts a separate loopback-only HTTP fixture process
with its own SQLite WAL ledger. A positive control must produce exactly one
HTTP attempt and one effect. For each stop case, a real worker binds the
original production turn's cancellation token, waits across the actual control
or spoken-cancel ingress, then calls the canonical `begin_write_effect` gate.
The controller never cancels that token itself. Separate-process ledger reads
must find zero requests and zero effects for the cancelled worker. Both
authenticated attempts and effects are retained, so provider-side deduplication
cannot hide an application retry. Wrong actor/tenant and unauthenticated
requests are independently covered by the fixture's real HTTP tests.

This is expressly a final-write-fence integration experiment. It uses the
existing mutating catalog key `gmail.send` only to exercise that gate; the
provider effect is `acceptance.note.create` in a local disposable SQLite file.
No Gmail/email is sent, no vendor credential is provisioned, and no production
tool registry is replaced. It does not substitute for complete confirmation,
HMAC approval, fresh authorization, revocation or vendor-side-effect acceptance.

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

Run `41133238281`, source `0c1102790ddd10aa9713c3033c238d895c1bd5dd`,
artifact `13014077287`, then verified valid canonical headers, real STT, durable
messages and composer/latency audit rows on both paths. The sky-explanation case
still failed: the unchanged source-bound knowledge policy returned its explicit
no-KB/no-web-search refusal. The controller correctly rejected that output and
did not run dependent interruption/reconnection cases. This result remains FAIL.
The next case, `provided_welcome_rewrite_v1`, is a distinct generative task using
only user-provided text, with no external factual grounding requirement. This is
a change of case, not a waiver or relabeling of the failed factual-answer test.

Run `41134087803` exposed an acknowledgment-only capture before durable turn
completion. Source `ad7337311c521b012d2bad2e2cb1c1844e9d6ca3` requires the
canonical `assistant_turn.complete` event for baseline/reconnect captures and
adds actual spoken cancellation. Run `41134456513`, artifact `13017080382`, then
passed all eight matched trials. Shared source PCM hash:
`bd1062d37671b640cf0be2ae4397d3c133bd23131ac2d6f568c1ec1c076e3731`.

| Receiver-boundary measure | Pipecat | LiveKit |
| --- | ---: | ---: |
| Baseline first speech after input end | 4655.30 ms | 2098.57 ms |
| Control to original-reply cutoff | 2.84 ms | 52.25 ms |
| Spoken cancel start to original-reply cutoff | 465.53 ms | 531.58 ms |
| Reconnect first speech after input end | 1998.05 ms | 1760.82 ms |

Each baseline wrote two durable messages; reconnection observed both prior
roles and grew each conversation from two to four messages. Both spoken cancel
transcripts were classified as reject by the canonical classifier. These are
single-trial observations on one fixed generative case, not an engine-selection
benchmark, physical acoustic cutoff, semantic memory score or complete Gate 3.
