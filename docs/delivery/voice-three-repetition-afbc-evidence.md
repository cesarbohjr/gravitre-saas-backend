# Three repeated voice trials: failed batch retained

Source: `afbc8be8dd2916eab51f0c8112797ab8ac967b0b`.
Run: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/41145854571
Artifact: `13021634962`; ZIP SHA256
`38f7500f0d4ebd8bc922c9dc6163063dbe69f99f33e28c80532a54d502bd4301`.

All three scheduled voice phases and all three native-assignment phases executed.
Every phase failed overall. This batch does not certify either transport.

| Trial | Pipecat spoken cutoff from cancel start | Cutoff from cancel recording end | LiveKit spoken cancellation |
|---|---:|---:|---|
| 1 | 285.448 ms | -1618.615 ms | NOT RUN: baseline timeout |
| 2 | 502.973 ms | -1401.089 ms | NOT RUN: baseline timeout |
| 3 | 434.427 ms | -1469.635 ms | NOT RUN: baseline timeout |

These are receiver PCM measurements, not physical speaker measurements. Negative
end-relative values mean the original reply stopped before the cancel recording
finished. The existing 500 ms assertion is relative to recording end. Trial 2
does not meet a distinct 500 ms start-relative criterion; no threshold was changed.

All six executed Pipecat control/spoken-stop probes had cancelled original tokens,
blocked canonical write fences, zero fixture attempts/effects and zero native
insert effects. Independent SQLite reads found `integrity_check=ok` for all three
ledgers, each with exactly one positive-control attempt/effect and no stop effects.
This is not cancellation evidence for the unexecuted LiveKit stop scenarios.

Independent acceptance-only database readback across twelve native conversations:
all six cancellation conversations had zero jobs/creation audits; all three
LiveKit approval conversations had exactly one job and one creation audit, with
no replay duplicate. Pipecat approval staged unsuccessfully in all three trials,
so its zero jobs do not prove a functioning approval path. LiveKit native cancel
passed trial 1 but failed staging assertions in trials 2 and 3. Zero rows alone
do not turn those failures into passes.

Pipecat baseline and fresh-session reconnect passed three times; its backchannel
case passed once, with startup errors in two trials. LiveKit baseline reached
final transcription and LLM start but timed out three times before completed
speech, preventing its later voice scenarios. The original raw provider logs
were deliberately excluded from portable artifacts; sanitized diagnostics lacked
the task locations needed to identify the stalled await.

## Follow-up change, pending live validation

The partial-word bridge introduced Flux interim frames into ordinary listening,
which also activated prefetch work that this provider previously did not trigger.
Narrow the bridge to active work/speech overlap and mark its frames as control
only so speculative prefetch does not consume them. Preserve SDK-owned final
transcripts, ordinary non-Flux partial prefetch, cancellation assertions and the
same pinned recordings. This is a scoped repair hypothesis, not a proven root
cause. Add sanitized SDK error categories and timeout coroutine locations to
make any remaining failure diagnosable without exposing keys or response bodies.

Full CI on the failed voice batch's source passed:
https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/41145854481
CI success does not override the live acceptance failures.
