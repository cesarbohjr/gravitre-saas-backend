# PR #600 / #601 — Browser acoustic evidence capture and release gate

**State: IMPLEMENTED SOURCE, LIVE DEVICE ACCEPTANCE NOT RUN.** This procedure
does not authorize production recording, credential extraction, provider
billing, customer-data capture, deployment or release promotion.

## What changed

- The existing non-production `/e2e/voice-duplex` browser harness provides
  explicit **Start local audio capture / Stop capture** controls.
- The real `useVoiceDuplexSession` Pipecat path injects an acceptance-only tap
  at the *post-duck* PCM output gain stage. No recording is created without an
  explicit user click. The default product voice route has no recorder.
- The browser stores the output only in a MediaRecorder Blob and exports
  `gravitre-post-duck-browser-audio.webm` and
  `gravitre-acoustic-timeline.json` as local download links. Safari may
  encode MP4 instead; use the actual manifest MIME type, not the filename
  suffix, as the source of truth.
- Metadata uses the browser monotonic clock and AudioContext clock for
  `pcm_enqueue`, `playback_started`, `rebuffer`, `duck`, `unduck`,
  `flush` and `context_state` events. It does not contain transcripts,
  credentials, microphone samples or user-entered speech.
- The offline script `scripts/analyze_voice_acoustic_capture.py` parses the
  local JSON and optional matching audio, records the audio SHA256, and
  produces tentative failure signatures. It never uploads material.
- The existing `scripts/voice_paired_live.py` captures *received* PCM from
  actual provider-side sessions only when the separately authorized isolated
  acceptance environment and paid-provider credentials are supplied. That
  recording alone cannot establish the browser's output or physical sound.

## Browser workflow (acceptance only)

1. Run a **non-production** frontend with the guarded E2E route enabled,
   and a dedicated synthetic Pipecat harness WS backend. Use
   `/e2e/voice-duplex?transport=pipecat&ws=<authorized-test-ws-base>`.
   The `/e2e` route is disallowed in normal production builds.
2. On the tested device/browser, click **Toggle voice**, verify a running
   AudioContext and a ready harness socket, then click **Start local audio
   capture**. This click is an affirmative capture action; do not replace it
   with an automatic observer or hidden initialization.
3. Use only synthetic dialogue and approved fixture audio. Exercise clean
   speech, 200ms delayed PCM chunks, short acknowledgments, a genuine
   interruption, explicit stop, reconnect and a browser state interruption.
   Keep the device and network conditions recorded outside the transcript.
4. Click **Stop capture** and separately save both local links. Do not upload
   the files into GitHub Actions or an uncontrolled artifact bucket.
5. Analyze locally:
   `python scripts/analyze_voice_acoustic_capture.py gravitre-acoustic-timeline.json --audio <saved-audio-filename> --output acoustic-triage.json`.
   Store the exact commit SHA, browser version, device, provider/test-server
   version, test condition, audio checksum and any human rating in the approved
   private acceptance evidence location.
6. Repeat on real **iOS Safari speaker/headphones** and **desktop Chrome/Safari**
   under clean and impaired network conditions. These runs need a human or
   authorized device-farm operator, and artifacts must actually be inspected.

## What this does and does not prove

| Evidence | Strongest admissible conclusion |
| --- | --- |
| Test audio + metadata from local recorder | The browser PCM output **after ducking** and its observed player timeline |
| Rebuffer marker | A same-reply queue starvation recovery was observed; confirm audible gap in output |
| Long `pcm_enqueue` gap without rebuffer | Transport or synthesis timing changed; *not* automatically a starvation defect |
| Long duck without stop | Check VAD/overlap decision and gain restoration |
| Non-running AudioContext | Browser context interruption may explain missing sound |
| Server-side received PCM WAV | The backend's provided PCM arrived at the harness; browser/physical output not proven |
| External speaker recording | Physical sound for the declared device; correlate with browser events |
| Independent blind matched pair | Relative audible naturalness under stated comparable permissions/tasks |

The local browser capture is **not** an external microphone measurement and
does **not** independently measure provider TTS generation timestamps. To
separate TTS silence from transport delay, pair the browser manifest with
server-side generation/send/receive times and a monotonic-offset calibration
or transport-side relative stage deltas for each reply. Do not combine
absolute timestamps from distinct clocks without a measured offset.

## 20-minute and blinded-reference gate

A 20-minute voice session must actually run on an isolated authorized test
tenant with real STT/TTS and a working inference provider; a synthetic
two-minute E2E harness pass is not a substitute. Capture a synchronized
timeline and consented external audio (speaker/headphones), verify reply
continuity, reconnect, short backchannels and true interruptions, and check
the independent write fence. Repeat comparable, contemporary prompts with
ChatGPT under matched permissions, record actual reference product/date,
hash the recordings, and collect blinded independent ratings using the frozen
PR #587/#600 criteria. No synthetic provider session qualifies for this
comparison. Keep `whole_product_equivalence_claim=false`.

## Promotion gate

No buffer/gain/duck/transport adjustment is selected from the synthetic
jitter test alone. Before promotion require: exact-head full CI; real browser
capture with recording and manifest; physical device/independent listening;
causality analysis; measured latency/continuity improvements; unchanged
interruption/cancellation/write authorization; and a rollback candidate.
Missing provider, consent, device or human comparison evidence must be
recorded as **NOT_RUN / NOT_CERTIFIED** rather than passing by omission.


## Streaming DSP underrun defect and source repair — 2026-11-03

**Code-level cause identified:** `apps/web/public/voice-worklets/pcm-player-processor.js`
used the `PcmPlayoutQueue.process` before-underrun callback to call
`StreamingResampler.flush()` whenever the queue could not fill the next
128-frame render quantum. `flush()` emits zero-padded FIR tail samples
**and resets resampler history/phase**. A later PCM chunk from the *same*
speech stream was therefore resampled as though a new stream had started.
Under repeated short transport/TTS stalls, this creates artificial
resampling boundaries on top of jitter-buffer mute/re-prime transitions.
The causal mechanism follows directly from the source; its contribution
to any particular reported physical recording remains unquantified.

**Repair:** leave the streaming FIR lookahead intact when the queue runs
dry; let the already-present 4 ms underrun fade and jitter-buffer
re-prime handle the temporary silence. The explicit `flush` command
still calls `resampler.reset()` on actual barge-in, stop or cancellation.
The old pre-underrun callback is removed from the worklet; no changes
to authentication, background task cancellation, duck attenuation,
jitter policy or provider selection. Worklet cache version bumped 6→7.

**Regression:** `apps/web/__tests__/lib/voice-audio-dsp.test.ts` feeds
a 24 kHz 440 Hz signal into a 44.1 kHz worklet in two chunks, drains
the queue between arrivals, asserts continuous resampler output phase
count on recovery, then asserts a real `flush` resets that count.
This is unit-level evidence, not yet an independent listening verdict.

**Tradeoff:** the unpadded filter lookahead remaining when an utterance
terminates may omit a sub-millisecond trailing tail until the next PCM
chunk or explicit reset; acceptance recordings must check end-of-reply
consonants and any reply-boundary smoothing before release. Real iOS,
desktop and blinded comparison evidence remains NOT_RUN.
