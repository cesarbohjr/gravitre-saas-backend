# Phase 2 live acceptance attempt — 2026-10-27

Status: incomplete. This report does not certify Phase 2 or authorize rollout
of governed memory for any customer organization.

## Generated responses

The fixed synthetic evaluation corpus now includes 26 cases across all ten
current personas, unified/classical prompt builders and paired text/voice:
520 paired judgments and 1,040 generated replies when a complete run succeeds.
Additional cases cover Spanish/French, language switching, mixed-language hold
instructions, multilingual injection, session corrections, unavailable private
history, memory revocation, human handoff honesty and objection repair.
These evaluate generated behavior, not persistence, RLS or actual handoff delivery.

Live Railway credential probes at 17:52 UTC returned HTTP 401 for Anthropic and
OpenAI. Deepgram and ElevenLabs each returned HTTP 200. No secret values or
provider error bodies were recorded. Valid inference credentials remain required.

## Real provider audio

Private one-shot Railway capture deployment:
`f19bebda-6a92-407e-b980-ada4a27045cd`. Fixed synthetic speech only, with the
existing Sarah voice, Flash v2.5 model and source expression settings:
stability 0.4/0.5/0.6; similarity 0.75; style 0; speaker boost enabled.
WAVs are mono 16-bit PCM at 16 kHz, with SHA-256 checks verified after retrieval.

| Profile | First provider audio | Longest internal silence | Duration |
| --- | --- | --- | --- |
| light | 148.3 ms | 60 ms | 2,275.6 ms |
| medium | 142.5 ms | 60 ms | 2,275.6 ms |
| deep | 135.5 ms | 130 ms | 2,368.4 ms |

Each recording was transcribed successfully by Deepgram. The transcribed
synthetic hold phrase was then checked through the real spoken approval
classifier and final local write gate: `hold_commit`, `invoke_allowed=False`,
and provider write refused. No business write executor was called.

One recording per profile is not a reliability distribution. Provider first
audio is not user-perceived Pipecat latency. Internal silence includes intended
pauses and is not a discontinuity verdict. Playback interruption, real Pipecat
streaming, turn-taking and expressive naturalness remain unverified. The WAVs,
capture timestamps and analysis are available in
[the recording evidence archive](https://chatgpt.com/library?file_id=libfile_3f1203ff54bc81918ffcc9a647cb3049&account_id=personal).

## CI regression

CI on `676e7cf` reported 14,091 backend passes, 21 skips and one failure:
`test_interrupted_voice_reply_then_new_request_answers_the_new_request`.
The replaced, unanswered request survived in voice history and the new session
continuity section copied it into the next request. Replacement now removes
only the trailing abandoned request while preserving earlier answered history.
The end-to-end scenario assertions are unchanged; the helper contract now
requires abandoned history removal and verifies the input history is not mutated.
Continuations, repetitions and explicit corrections retain their existing paths.

## Remaining access and release gates

Automatic approval review rejected transferring Supabase service-role and JWT
signing credentials into the separate evaluation service, and rejected the
dependent privileged authenticated probe. Neither action was applied. A scoped,
short-lived isolated smoke-tenant session is the preferred next input. A privileged
setup instead requires explicit approval explaining that credential scope.

Real memory retention/revocation and tenant/agent boundaries, human delivery and
acceptance, deployed-SHA text/voice certification and physical audio acceptance
remain open. Governed memory stays default-off pending organization configuration.
The integrated head must pass full CI before merge and deployment; no CI or
production success is implied by local regression tests or this evidence file.
