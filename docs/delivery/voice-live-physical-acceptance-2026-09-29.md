# Voice live physical acceptance — post-3.0 hardening

Date: 2026-09-29
Current production merge: `3ac840ff27609673a9a876c40d8ea202728b9d6d`
`VOICE_LIVE_STATUS = CODE_HARDENED / PHYSICAL_PROOF_PENDING`
`VOICE_LIVE_PROVEN` remains unset

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


## V7 silent-PCM physical-output hardening

A non-empty PCM transport frame is not proof that useful audio reached the
browser. A provider or transport can emit leading silence or zeroed/near-zero
PCM while assistant text is already present.

The browser now tracks separately:

- total PCM frames received;
- PCM frames with meaningful audible energy;
- maximum observed PCM peak for the turn.

The no-audio watchdog clears only after an audible-energy frame arrives. If the
five-second window expires after assistant text and only silent PCM was received,
the turn is classified as `audio_silent` and handed to the existing HTTP TTS
recovery path. If zero PCM arrived, it remains `audio_missing`.

The energy gate uses a deliberately low int16 threshold so normal quiet speech is
accepted while digital silence, tiny transport noise, and isolated sample spikes
do not falsely prove speech.

Output diagnostics remain content-free: counts and peak level only, with no audio
samples or transcript text.

This still does not set `VOICE_LIVE_PROVEN`. Physical closure requires a human
to hear the response in production.

## V7 merged to production (2026-09-30)

PR [#224](https://github.com/cesarbohjr/gravitre-saas-backend/pull/224) was marked ready and merged at
`2026-09-30T05:09:25Z`. Merge commit: `3ac840ff27609673a9a876c40d8ea202728b9d6d`
(head SHA `03dbfaaf6570913c84709967ad8f542d3fbf640d`).

Deploy evidence:

- Railway backend production workflow
  [36672116600](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36672116600):
  SUCCESS on `3ac840ff`.
- `GET https://api.gravitre.app/health` at `2026-09-30T05:18:08Z`:
  `status=ok`, `environment=prod`, `git_sha=3ac840ff27609673a9a876c40d8ea202728b9d6d`.
- Vercel production deployment `dpl_94tpoewm5PJG227QJ1nqxXewLnky` READY; aliases
  include `gravitre.app`. Commit SHA `3ac840ff`.

Required CI on the PR SHA (`03dbfaaf`) was green before merge (Web, backend
pytest, voice gate, dependency audit, Integration Smoke, Marketing Lighthouse).
Exact-head CI on the merge commit
[36672116488](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/36672116488):
SUCCESS (Web, backend pytest, voice gate, dependency audit, Integration Smoke;
Billing E2E skipped).
Marketing Lighthouse on this merge is **out of this workstream**. The merge-commit
run failed home performance `0.73` vs `>=0.75` and is tracked separately in
`docs/delivery/marketing-lighthouse-home-perf-2026-09-30.md`.

Production telemetry re-query on `smyeexlrqdpymwjmgzqu` after deploy:

- `audit_logs` `action LIKE 'voice.output.%'` = 0 rows
- `audit_events` `action LIKE 'voice.output.%'` = 0 rows

A signed-in production browser session was observed at
`https://gravitre.app/intelligence` in org **Gravitre Isolated Conversation
Smoke**. That is not an owner voice session and was not used as physical proof.

`VOICE_LIVE_STATUS = CODE_HARDENED / PHYSICAL_PROOF_PENDING`

`VOICE_LIVE_PROVEN` remains unset until a human hears a production reply and a
`voice.output.*` row exists for that same Talk turn.

RLS on `agent_custom_voices` and `billing_topup_events` is **out of this
workstream** and unchanged. Tracked separately in
`docs/delivery/supabase-rls-follow-up-2026-09-30.md`. Not a voice-acceptance
blocker unless a Talk turn proves otherwise.
