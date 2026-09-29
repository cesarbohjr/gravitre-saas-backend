# Voice live physical acceptance — post-3.0 hardening

Date: 2026-09-29
Branch: `fix/voice-live-physical-acceptance-v2`

## Owner-reported failure

The live product previously completed a voice session with **no audible output**.

Synthetic PCM, provider TTS success, transcript success, and unit tests are not
sufficient to close that defect.

## Browser-path fix already merged

The production browser now reuses the AudioContext unlocked by the user's Talk
gesture, queues Pipecat PCM if the context is suspended, exposes **Enable sound**,
and never closes the shared output context during session teardown.

## Additional hardening in this branch

1. Spoken prompt V2 is enabled by default for spoken turns.
2. Played-audio reconciliation is enabled by default so interrupted history
   reflects what the human actually heard.
3. Adaptive response-length prompting stays opt-in because prior live measurements
   showed it was not reliably obeyed.
4. Pipecat now has a browser-side output watchdog:
   - assistant text received;
   - no PCM audio frame arrives for five seconds;
   - the session surfaces a visible voice error instead of remaining silently
     "healthy".

The watchdog distinguishes **no audio delivered** from **audio delivered but
browser playback blocked**. The latter keeps using the explicit Enable sound path.

## Acceptance trace

Physical acceptance still requires:

browser microphone
→ capture
→ WebSocket transport
→ Pipecat STT
→ CognitiveTurnKernel / unified response composition
→ ElevenLabs TTS
→ outbound PCM frame
→ browser audio frame receipt
→ running user-unlocked AudioContext
→ scheduled AudioBufferSource
→ audible speaker output

## Closure rule

`VOICE_LIVE_PROVEN` requires a human to hear the response on the production
browser/device.

Until that happens:

`VOICE_LIVE_STATUS = CODE_HARDENED / PHYSICAL_PROOF_PENDING`
