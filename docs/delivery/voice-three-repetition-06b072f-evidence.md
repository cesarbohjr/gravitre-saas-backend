# Three repeated real-transport trials

Measured source: `06b072f57b547b9ac8b1b4cc51117b9789740d17`.
Run: https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/41155311334
Artifact `13025134525` (27,670,494 bytes), independently checked ZIP SHA256:
`284f6a6836ddb90f6574bb17fe218ed4e92d194602b2094be7363a3e91d669ff`.

All three scheduled repetitions executed through real authenticated loopback
WebSocket and LiveKit RTC transports, using identical digest-checked recordings,
live Flux STT, Anthropic inference and ElevenLabs synthesis. LiveKit reuses the
production Pipecat cognitive pipeline; this is a transport comparison, not a
separate LiveKit Agents cognition implementation. No production data or connector
grants were used. Native assignment workers were not launched; created jobs were
retired after their creation/replay checks.

## Actual result: aggregate FAIL, no certification

Voice: **27/30 PASS**. Native assignment cases: **12/12 PASS**. Every voice phase
failed on its LiveKit backchannel verdict; those failed manifests remain intact.
The separate provider-only job also failed before inference because pip exhausted
runner disk space. Full CI on the measured source passed independently:
https://github.com/cesarbohjr/gravitre-saas-backend/actions/runs/41155311250

## Cancellation measurements

Values below are receiver PCM cutoff in milliseconds, measured from the start of
the 1,904.0625 ms cancel recording. These are not physical speaker measurements.

| Repetition | Pipecat spoken cancel | LiveKit spoken cancel | Pipecat control | LiveKit control |
|---|---:|---:|---:|---:|
| 1 | 508.918 | 427.195 | 0.000 | 72.071 |
| 2 | 708.932 | 585.324 | 0.000 | 92.341 |
| 3 | 457.681 | 299.319 | 0.000 | 66.609 |

The existing harness's spoken-cancel gate is **500 ms after recording end**.
Both transports met that gate in all three repetitions: original reply cutoff
was 1,195–1,605 ms before the recording ended. If the requirement instead means
500 ms from recording start, **Pipecat failed two trials and LiveKit failed one**.
No assertion or reference point was changed to turn those measurements green.
WebSocket PCM receipt does not measure queued browser playout; control zeros mean
no further original-reply PCM was received after the control timestamp.

## Independent write evidence

The accompanying `voice-three-repetition-06b072f-write-audit.json` contains fresh
Supabase SQL readbacks and independent SQLite ledger reads, not assistant claims.

- All twelve control/spoken-stop workers held original cancelled turn tokens and
  were refused by both final fences. Independent DB reads found zero native probe
  rows for all twelve conversations.
- Each of three SQLite ledgers passed `integrity_check`, contained exactly one
  HTTP 200 positive-control attempt/effect, and contained zero stop attempts or
  effects. No unauthorized fixture write was observed.
- All six native cancellation conversations had cleared pending state, zero jobs
  and zero creation audits.
- All six native approvals had executed pending state, exactly one job and one
  `assignment.created` audit. The recorded live approval replays added no jobs.
  No duplicate assignment write was observed.

These prove the exercised insert/final-fence and native approval paths. They do
not prove arbitrary customer connector side effects or cancellation of a provider
request already committed before a stop.

## Latency, authorization, reconnect and audio

Baseline first received speech after input recording end (milliseconds):

| Repetition | Pipecat | LiveKit |
|---|---:|---:|
| 1 | 3076.86 | 2472.11 |
| 2 | 2609.82 | 2008.66 |
| 3 | 2513.85 | 1956.16 |

The earlier LiveKit baseline stall did not recur. Fresh-session reconnect on the
same conversation passed six cases, retaining prior durable history. This does
not test mid-turn network-fault recovery. Five live production-route Auth/RLS
denials passed: missing, tampered and expired JWTs, foreign organization and
revoked membership with a still-valid JWT. RTC token issuance and in-flight tool
reauthorization remain outside that route test's scope. The disposable actor was
removed. Anthropic authentication/inference returned HTTP 200 in 491.85 ms.

WAVs, output hashes and provider transcription request IDs are retained in the
artifact. Maximum clipping fraction among voice outputs was approximately
`0.0000082313` (0.00082313%). This is signal integrity evidence, not a human audio
quality rating. The welcome-keyword check is not a complete two-sentence semantic
instruction grade. Physical microphone/speaker and blinded human quality checks
remain NOT RUN.

## Backchannel measurement repair and required revalidation

All three LiveKit backchannel traces classified the utterance as `backchannel`,
recorded two durable messages and one assistant-turn completion, and had no
pipeline error or interruption after that utterance. The only RTC flush followed
reply completion and carried `rtc_disconnect`. The harness read the original
mutable token **after** teardown; LiveKit's correct disconnect fence then made
that token cancelled. This caused a failed backchannel verdict after the reply
had completed.

The follow-up snapshots cancellation at completed reply **before transport
teardown**, retains the post-teardown value separately, and still fails on a
missing snapshot or any actual pre-completion cancellation. A regression test
uses real cancellation tokens to prove both preserved backchannels and actual
earlier cancellation remain distinguishable. This changes the observation phase,
not the cancellation safety requirement. The old failed cases are not regraded.
The supplemental provider job disables pip's download cache to reduce duplicate
wheel/install disk usage without removing dependencies or assertions.

Post-repair focused checks: **178 passed**, including two lifecycle subtests.
Fresh live revalidation is required; neither repair is certified by those local
checks. The earlier failed batch remains separately recorded in
`voice-three-repetition-afbc-evidence.md`. Gates 2/3 aggregate, intelligence,
fault recovery and final release certification remain incomplete. Keep the PR
draft and unmerged.
