# Repeated real-audio evidence: one response-quality failure remains

Measured source: `84174e9162107c04a04b8a1afe783edb3ff303f3`.
Run: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/41158495163
Artifact `13027515326`, ZIP SHA256
`e236309c4c15e299a3705d60a1ac24710cf1abbd02d70304f42806de7d40b666`.
The downloaded ZIP digest was checked before inspection.

**Aggregate FAIL retained: 29/30 voice and 12/12 native cases passed.** The first
and third voice repetitions passed all ten cases; repetition two failed LiveKit
reconnect content. All six backchannel cases now passed, including the connected
completion snapshots before RTC disconnect. The provider-only job passed after
the pip-cache change. Full CI on this source passed:
https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/41158495319

## Actual cancellation and write results

Cutoff in milliseconds from the **start** of the identical cancel recording:

| Repetition | Pipecat | LiveKit |
|---|---:|---:|
| 1 | 529.495 | 196.247 |
| 2 | 559.825 | 550.095 |
| 3 | 545.181 | 268.528 |

Both met the existing limit of 500 ms **after recording end** in all three
repetitions; cutoff preceded recording end by 1,344–1,708 ms. A distinct 500 ms
start-relative criterion failed four of these six trials. No threshold changed.
These are received PCM measurements, not physical speaker or queued browser
playout measurements. WebSocket control receipt cutoffs were zero; RTC controls
were 125.906, 106.539 and 74.731 ms.

Fresh independent SQL readback, scoped to the exact 24 native/stop conversation
IDs, is retained in `voice-three-repetition-84174e9-write-audit.json`:

- Twelve stop probes: zero native insert rows. All twelve manifests also show
  cancelled original tokens, refusal by both final fences and zero fixture
  attempts/effects.
- Three SQLite WAL ledgers: integrity checks passed; each contained only one
  positive-control HTTP 200 attempt and one positive-control effect.
- Six native cancellations: pending state cleared, zero assignments and audits.
- Six native approvals: exactly one assignment and one creation audit each;
  live replay checks passed, with no duplicate assignment rows.

No assignment worker was launched and no customer connector action was tested.
This proves the exercised approval/insert/final-fence paths, not arbitrary
external provider commit cancellation or full production certification.

## Remaining failure and scoped fix

Failed conversation: `bc913e0a-85a5-457d-a932-ea4fe91a2ffd`.
Failed WAV SHA256:
`49f55a48162a52283ebb2ef689dc0e62a9cf3180b37906e0e618d306bfc56065`.
Output transcription request: `01a18fc8-e2a2-7592-88ad-dff319376416`.

Both retained audio transcription and an independent durable-message readback
showed the same actual reply: "Already handled that one — the warmer version is
right above. Anything else you'd like tweaked?" The user had repeated the same
self-contained rewrite request after reconnect. History was restored (four
durable messages); the response withheld the requested content. This is not an
STT false negative or lost-history transport failure, and its failed content
assertion remains unchanged.

The shared anti-repeat prompt prohibits reusing recent wording without an
exception for requested repetition. The follow-up narrows that style instruction:
provide requested content again; permit exact wording when asked; never treat
repeated content as authorization to repeat a tool call or mutating action.
This is a shared prompt repair hypothesis requiring fresh live validation, not a
retroactive pass for the failed case. No fixture-specific answer or keyword
allowlist was added.

Local regression: 1,840 checks passed before the final process-group cleanup
hardening; the focused launcher/bounded-workflow checks subsequently passed.
The loopback production API was also started with lifespan disabled and returned
HTTP 200 with the expected source label against an offline dummy database;
that startup check made no inference request.

## Next execution and remaining certification

The same three paired repetitions rerun with unchanged recordings/assertions.
Because shared prompt construction changed, the full standing batteries follow
against a loopback acceptance API: complete phase2 (including its classical
children), 30-turn persona, pending, mapper, TTFT, breakdown and injection.
The launcher pins the acceptance project/org, rejects dotenv target overrides
and real connector grants, uses production routes with real Auth/DB/inference,
disables lifespan schedulers/workers and notification email, retires its queued
fixture jobs and retains sanitized per-battery results after every completion.
Every scheduled battery still executes after an earlier failed verdict; no
failed run is retried until green. Connector-dependent cases may expose missing
acceptance prerequisites; they must remain failed/blocked rather than simulated.

Standing prompt tests are not the full 56-capability/surface intelligence
certification. Five of six fresh-session reconnect cases passed here; mid-turn
network faults, intelligence outcome learning, broader fault recovery, physical
audio and blinded human quality still require their own evidence. Keep the PR
draft and unmerged until the required combined gates actually pass.
