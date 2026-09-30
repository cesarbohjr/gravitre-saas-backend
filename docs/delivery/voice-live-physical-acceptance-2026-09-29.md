# Voice live physical acceptance — post-3.0 hardening

Date: 2026-09-29
Current production merge: `086e549d65a260e2864bd57702412d807af02958`

## Owner-reported failure

The live product previously completed a voice session with **no audible output**.

Synthetic PCM, provider TTS success, transcript success, and unit tests are not
sufficient to close that defect.

## Browser-path fix already merged

The production browser now reuses the AudioContext unlocked by the user's Talk
gesture, queues Pipecat PCM if the context is suspended, exposes **Enable sound**,
and never closes the shared output context during session teardown.

## Additional production hardening

1. Spoken prompt V2 is enabled by default for spoken turns.
2. Played-audio reconciliation is enabled by default so interrupted history
   reflects what the human actually heard.
3. Adaptive response-length prompting stays opt-in because prior live measurements
   showed it was not reliably obeyed.
4. Pipecat has a browser-side output watchdog:
   - assistant text received;
   - no PCM audio frame arrives for five seconds;
   - the session surfaces a visible voice error instead of remaining silently
     "healthy".
5. The browser now watches the live AudioContext after session start. If the
   browser suspends output later, the session enters the explicit **Enable sound**
   recovery state instead of silently scheduling audio against a stopped clock.
6. A failed AudioBufferSource start no longer drops a Pipecat PCM chunk. The chunk
   is held for retry and the user sees the sound-recovery state.
7. Barge-in captures the real played-audio offset before playback teardown clears
   the PCM origin, so interruption reconciliation can reflect what was actually
   heard rather than an undefined offset.

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


## Current production classification

- Browser/frontend hardening through main merge:
  `086e549d65a260e2864bd57702412d807af02958`
- Exact-head PR CI: PASS
- Integration Smoke: PASS
- Lighthouse: PASS
- Backend voice runtime remains on the previously successful Railway deployment
  because the latest merge changed only browser/frontend voice code.
- Synthetic/shared text-voice gates remain supporting evidence only.

The code defect class has been hardened as far as can be established without a
real speaker test. Do not change the status to `VOICE_LIVE_PROVEN` from CI,
TTS provider success, transcript success, PCM receipt, or browser scheduling
alone.


## V5 recovery path hardening

The text-only Pipecat recovery path now prefers the same user-unlocked WebAudio
context used by duplex PCM before falling back to HTMLAudio.

Why this matters:

- HTTP TTS synthesis is asynchronous and can finish after the browser's transient
  user-activation window expires.
- `HTMLAudioElement.play()` can therefore be blocked even when the Talk gesture
  already unlocked an AudioContext.
- recovery TTS now decodes the returned audio blob with the shared running
  AudioContext and schedules an AudioBufferSource directly;
- HTMLAudio remains a codec/browser fallback;
- if that fallback is blocked, the existing **Enable sound** recovery stays visible.

This closes another silent-output class without changing the cognitive or TTS
provider path.

Physical closure still requires a human to hear production audio.


## V6 playback evidence telemetry

The browser now emits best-effort lifecycle diagnostics for the physical output
chain:

- audio_missing
- output_unavailable
- playback_blocked
- playback_started
- playback_recovered

These events are authenticated and tenant-scoped and intentionally contain no
audio samples, transcript text, access tokens, provider credentials, or device
identifiers.

The purpose is diagnostic only: they make it possible to distinguish in live
production whether a turn reached browser playback, became blocked by the
browser, recovered after an explicit user gesture, or never received audio at
all.

A `playback_started` event is supporting evidence that browser playback was
scheduled/started. It still does not replace the physical acceptance rule:
`VOICE_LIVE_PROVEN` requires a human to hear the response.
