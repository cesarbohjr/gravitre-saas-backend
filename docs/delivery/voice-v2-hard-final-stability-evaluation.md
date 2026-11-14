# Voice V2 — bounded provider-final stability evaluation (engineering draft)

**Status:** implementation and deterministic tests in PR #610; exact-head CI, live
acoustic acceptance and production release remain pending. Feature is **off by
default** (`VOICE_FINAL_STABILITY_V2=false`).

## Objective

Deepgram Flux may emit a real, finalized `EndOfTurn` during a mid-sentence
pause. Suppressing `EagerTranscriptionFrame` alone cannot prevent that event
from entering the canonical Pipecat user-turn aggregator, triggering a model
response or an approval while the speaker intends to add a clause. The
stability processor inserts a bounded quiet period **after**
`CommittedTurnBarrierProcessor` and **before** `LLMUserAggregator`.
It holds source `TranscriptionFrame` and stop frames together. It does not
alter provider STT, reroute model calls, create approvals, or bypass the
original governed-action runtime.

## Initial conservative policy (must be evaluated before activation)

| Intent / condition | Quiet interval | Bound and trade-off |
|---|---:|---|
| Ordinary speech | 400 ms | +400 ms to first committed reasoning on uncorrected turns |
| Exact short confirmation (e.g. yes, send it, go ahead) | 1200 ms | +1.2 s to approval, buying room for a trailing 'wait/not yet' |
| A session already awaiting approval | 1200 ms | Applies even when recognition is 'proceed' or 'no' |
| Explicit upstream `InterruptionFrame` | 0 ms | Cancellation/control is never delayed |
| Synthetic typed browser text | 0 ms | Existing text ingress bypasses acoustic heuristic |
| New speech before expiry | Timer cancelled | Preserve original provider-final words; no isolated approval |
| No subsequent speech | Timer expires | Forward the exact provider finals followed by their stop |
| End/cancel/disconnect | Pending buffers dropped | Do not synthesize or commit on shutdown |

Policy settings: `VOICE_FINAL_STABILITY_NORMAL_MS` (default 400, range
0–1500) and `VOICE_FINAL_STABILITY_APPROVAL_MS` (default 1200, range 0–1500).
The approval window is never shorter than the ordinary window.
Both remain inert unless `VOICE_FINAL_STABILITY_V2` is enabled.

## Deterministic engineering acceptance

- A first hard final containing 'yes' is buffered and cannot reach the model
  as an isolated turn; a resumed 'wait, do not send' is emitted before a
  single canonical stop.
- A bare 'yes' still reaches the same approved-action workflow once after the
  bounded delay; never infinitely delayed or duplicated.
- Real provider final after 400/800/1200 ms synthetic pause is evaluated
  separately from Flux's earlier *probable* EOT. Processor tests use
  controlled wake-up events, not wall-clock sleeps and do **not** claim to
  measure live speech-to-audio latency.
- A filler-only continuation filtered by `UtteranceGateProcessor` must not
  deadlock the original confirmation; it closes on the next stop.
- An explicit interruption is delivered immediately while buffered text
  remains governed; repeated legitimate turns after expiry remain distinct.
- The existing e2e voice scenario harness must prove no unauthorized writes
  on `yes → wait`, and exactly one on bare `yes`.

## Acceptance criteria before enablement

1. Full exact-head test suite and S8 approval scenarios green; ensure
   retention fixture stays clock-pinned.
2. Paired live Flux STT sessions showing actual final, resumption, first
   generated token, first server-side PCM, browser playback, and cancellation.
   Do not mistake a provider-final/resume heuristic for confirmed STT error.
3. No isolated approval writes on `yes ... wait` or correction, and no
   lost single-word confirmations after filler.
4. Compare latency distributions for on/off cohorts: p50, p95, tail, plus
   first *answer* audio (not filler) and client-heard playback, by tier.
   Expected imposed wait is 0.4 or 1.2 s; this is an explicit cost, not a
   guaranteed observed end-to-end shift.
5. Test rapid *distinct* consecutive turns: within-window turns can be
   combined, so evaluate false-join rate before any rollout.
6. Use the existing approval and connector isolation controls; do not run
   live external writes or promote the feature during engineering.

## Known boundaries

A hard final followed by **resumption after the configured interval** can
still produce an early answer. A false final may also lack a new start signal.
The algorithm chooses a bounded trade-off rather than claiming perfect
language-intent inference. No user/audio contents are captured in telemetry.
