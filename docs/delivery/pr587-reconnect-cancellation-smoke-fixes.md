# Reconnect, cancellation and smoke-identity correction

Baseline: `af18c1db2eb41c378bc54ca5e982068f3d21fd8d`,
[voice run 41173364208](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/41173364208).
This record preserves that failing baseline; it does not regrade it.

## Observed defects

- Matched real-audio repetitions: 28/30 voice cases passed. Both first-repetition
  reconnect answers referred to the earlier rewrite rather than supplying it.
  All 12 native assignment cases passed. All 12 stop probes independently showed
  zero fixture attempts/effects and zero native insert effects.
- Pipecat's first spoken-cancel cutoff was 509.09 ms from input recording start.
  The old harness added the cancellation recording's duration to its 500 ms
  allowance. That older PASS is not a strict start-relative PASS.
- Standing batteries never reached live prompts: bootstrap and mint ran in the
  same GitHub step. The bootstrap exports the actual isolated actor through
  GITHUB_ENV, which is only applied to subsequent steps. Mint therefore used the
  legacy actor and failed the required membership check.

## Candidate corrections

- The shared prompt builder detects a repeated user request after case/punctuation
  normalization and explicitly requires the requested content in the current
  reply. It does not interpolate history into policy text, replay a tool call,
  grant permission, or waive fresh approval/cancellation/idempotency checks.
  Both text and voice consume the same correction.
- WebSocket output is chunked at 10 ms rather than the SDK's default 40 ms.
  LiveKit native playout capacity is 20 ms rather than 100 ms. This reduces the
  amount of irrevocably sent/queued audio; the live comparison must establish
  whether it meets the target. Smaller WebSocket chunks increase packet count.
- The receiver gate now enforces 500 ms from recording start for spoken cancel
  as well as explicit interrupt. Recording-end timing remains diagnostic only.
  The current input-start offset, cutoff limit and reference are exported. A
  regression test proves 509 ms fails despite a longer cancellation recording.
- Bootstrap and mint are successive GitHub steps. Target pinning, live Auth,
  membership verification, predecessor sequencing and no-customer guards remain.

## Validation and exit criteria

Local offline regression: **1,703 passed**, including voice turn control,
interruption/write boundaries, SDK PCM framing, real LiveKit SDK contracts,
shared prompt assembly and voice rules. Controller/target tests: **17 passed**.
Workflow YAML and separate-step actor handoff were checked. No dependency,
schema, production credential, connector grant or production deployment changed.

These are engineering results, not live certification. Run the same three
matched repetitions with the same pinned recordings, independent SQLite/native
write readbacks, then the full standing intelligence batteries, full CI and
combined-source checks. Retain every failure. No stage is complete until its
new results and source provenance have been inspected. Physical audio and the
remaining comparative/human-review requirements are outside this narrow result.

## Executed result on `5e766f352dd795b0617638b170a1930ad464669a`

[Matched run 41216971203](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/41216971203)
retains aggregate **FAIL**: 25/30 voice cases and 12/12 native-action cases pass.
All six reconnect cases now pass. All twelve stop probes independently show
zero fixture attempts, fixture effects and native insert effects. Spoken-cancel
receiver cutoffs in repetition order (Pipecat / LiveKit, milliseconds) are
877.49 / 754.31, 972.77 / 864.54, and 715.64 / 460.13. Five of six exceed 500 ms.
The artifact ZIP digest is
`15ac1f1222bc0b6db77a16a5a27371144f4c4fd22cd80c1106ea09fc5fde34c8`.

Trace alignment places the first Flux partial around 780–980 ms after the
cancellation input starts. Local intent classification follows within roughly
1–9 ms. The unchanged recording exceeds PCM amplitude thresholds of 100–1000
beginning around 18–28 ms;
leading recording silence does not explain this delay. Smaller output queues
did not resolve provider recognition latency. A natural silence gap can also
yield a short receiver cutoff despite late recognition; receiver silence alone
must not be described as proof of timely logical cancellation.

Full CI and the connected RTC workflow passed on this source. Connected RTC
measured 9.33 ms control delivery, 92.24 ms rejoin and 0.9771 waveform correlation;
these do not certify spoken provider control or physical playout. Standing
batteries successfully passed the separated provisioning and token-mint steps
and reached live prompts; their final result is still pending.

`voice_stt_control_latency.py` now defines a bounded diagnostic comparison of
Flux and Nova-3 using these exact cancellation and backchannel PCM digests,
three matched repetitions, real-time input and no retries. It exports first
speech-start, transcript and explicit control-word timings without transcript
or provider-body retention. It has no tenant, TTS, canonical final-transcript or
runtime selection authority. Four local regression tests pass. A faster model
must first be measured; this diagnostic alone cannot close the 500 ms gate or
justify interrupting backchannels.

## Measured diagnosis and next candidate

[Provider-only comparison 41220909176](https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/41220909176)
completed all twelve observations on `bb302a6c02ce48464b13161ba44f4c193589bc53`.
[Unabridged sanitized numeric results](pr587-stt-control-latency-bb302a6.json)
match the downloaded artifact; ZIP SHA-256 is
`cc619c76ffe91d9aaf7ce046c4ef53a95b17092a5e6d8f79e3ef319b93843c38`.
Flux's cancellation word arrived at 492.50 / 494.08 / 492.57 ms, before native
StartOfTurn at 731.93 / 734.25 / 732.79 ms. The existing bridge discarded these
pre-start partials. Nova-3's word arrived at 1040.55 / 1040.16 / 1038.01 ms;
switching to Nova-3 is not supported by this experiment. Neither model reported
a cancellation word in any backchannel trial. Maximum sender lateness was
under 2 ms. These observations do not establish a full runtime 500 ms PASS.

The next candidate therefore retains Flux and forwards an indexed, explicit
task-cancel Update before native StartOfTurn to the same existing turn
classifier and echo/origin protections. Bare "stop" waits for its continuation,
so "stop talking, keep working" does not become task cancellation. Approvals,
backchannels, ambiguous text, inactive sessions and updates from committed or
unknown provider turns cannot take this early path. A later native StartOfTurn
adopts that same proposal rather than starting another turn. Only the SDK's
EndOfTurn emits final transcription; connection-local indices reset on reconnect.

The paired harness also independently observes the original token's cancellation
event during input. Its event-loop timestamp is a conservative upper bound and
must meet the same 500 ms deadline. Silence or later teardown cannot substitute
for cancelling the original work. Fifteen controller tests pass, including
late/missing cancellation despite an early audio gap and generation replacement.
Fresh live certification is required; the measured 493 ms recognition leaves
little margin for transport and playout, so this remains an unproven candidate.
Focused backend regression: **1,700 passed** in 76.42 seconds; the additional
connection-index reset regression also passes (15 bridge tests total). No
provider switch, second recognizer, new inference path or widened deadline was
introduced.

## Standing results and harness follow-up

The standing job on `5e766f3` finished **FAIL**. Phase 2 exceeded its unchanged
1,200-second controller budget and persona exceeded 600 seconds; neither wrote
a final report. Pending-reply passed, mapper and task-TTFT failed, breakdown
completed diagnostically, and injection exited with HTTP 401 before a report.
[Exact manifest](pr587-standing-5e766f3-manifest.json), from artifact
`13049879841`, ZIP SHA-256
`99d4dd5492106919f93995e164b0652b4433cb34f60d73e453d4dcaa6fc0b623`.
The earlier sanitized reports omitted too many field names to establish the
missing-audit/mapper root cause. Those failures are not regraded.

The `b82b528` paired job did not run its matched trials: its 1,200-second
predecessor wait expired. Unit-test fixture PASS lines earlier in its log are
not live measurements. Its provider and governed-action jobs passed; full CI
also passed. Cancellation timing on this candidate remains **NOT RUN**.

Inspection found injection minted a JWT with the actor's email as `sub` rather
than its UUID. It now uses the existing issuer-bound 600-second smoke-token
minter, refreshed between cases. A regression intercepts the real battery's
first protected request and verifies its signature, UUID subject, issuer,
audience and expiry with all outbound sockets forbidden.

Phase 2 and persona now atomically checkpoint each completed case with verdict
RUNNING. Timeouts remain failures and retain incomplete evidence. The redundant
eight-second sleep before Phase 2's existing bounded audit poll is removed;
the controller and request deadlines, prompts, repetitions and assertions are
unchanged. Portable artifacts retain fixed field names, source-defined case
identifiers, closed failure categories and numeric health/audit observations.
Raw prompts, replies, provider bodies, arbitrary keys and credentials remain
omitted. Server diagnostics export fixed category counts from a bounded log
tail. Seven controller/privacy/checkpoint tests and the actual-request JWT
regression pass locally. Live confirmation and diagnosis of the remaining
standing failures are still required. No workflow was cancelled.
