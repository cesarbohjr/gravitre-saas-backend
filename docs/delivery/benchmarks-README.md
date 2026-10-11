# Benchmarks: how to run them and what they measure

Two offline benches, a runner that compares two git revisions, and flag profiles. Everything is committed under
`backend/scripts/`; results from 2026-10-11 are in `docs/delivery/bench-results-2026-10-11/`.

| What | Script | Clock | Deterministic |
|---|---|---|---|
| Voice scenarios (multi-turn, interruptions, flag interactions) | `backend/scripts/bench_voice_scenarios.py` | virtual | yes, for a given revision, profile, seed and N |
| Chat-turn latency (text and voice surfaces, single turns) | `backend/scripts/bench_chat_turns.py` | real wall clock | no: host-dependent |
| Two revisions under identical conditions | `backend/scripts/bench_compare.py` | both | as above |
| Flag profiles | `backend/scripts/bench_profiles/*.json` | | |

## Running

From `backend/`, with the repository's Python environment. No keys or network are needed; the scripts set the test
Supabase/OpenAI placeholders themselves when they are missing.

```bash
# Voice scenarios, production flag set (inferred: see below), 20 runs per scenario
python scripts/bench_voice_scenarios.py --profile production_inferred --runs 20 --seed 1000 --out /tmp/bench/voice-prod

# The same with code defaults; one extra flag on top of a profile; a subset of scenarios
python scripts/bench_voice_scenarios.py --profile defaults --runs 20 --out /tmp/bench/voice-defaults
python scripts/bench_voice_scenarios.py --profile defaults --setting VOICE_OVERLAP_DUCK_V1=true --scenarios S16,S17,S18 --runs 20 --out /tmp/bench/duck

# Chat turns, 15 samples per turn and surface (about 8 minutes)
python scripts/bench_chat_turns.py --runs 15 --out /tmp/bench/chat

# Base revision vs the current checkout (uncommitted edits included), same profile, seed and N
python scripts/bench_compare.py --base a7719cba --head WORKTREE --profile production_inferred \
    --runs 20 --seed 1000 --chat-runs 15 --out /tmp/bench/compare
```

`bench_compare.py` checks each non-current revision out with `git worktree add --detach` into a temporary directory,
copies the current checkout's bench driver over it (`scripts/bench_*.py`, `scripts/bench_profiles/`,
`tests/e2e/voice_scenarios/`) so both sides run the same scenarios, metrics and grading against their own product code,
runs both sides one after the other with the same Python, and writes `comparison.md` plus each side's results.
`--revision-harness` keeps each revision's own driver instead (needed when the driver no longer fits an old revision);
`--keep-worktrees` leaves the checkouts for inspection. `--head` may be any revision too.

Each results directory holds `results.json` (every run's metrics and seed, aggregates, scenario conditions, resolved
flags, git revision and `backend/app` tree hash) and `results.md`.

## Reproducibility rules

- **Profiles.** `--profile NAME` loads `scripts/bench_profiles/NAME.json` and clears every other `VOICE_*` variable
  inherited from the shell (listed in `meta.cleared_env`), so a result depends only on the revision, the profile, the
  seed and N. `meta.effective_flags` / `meta.effective_settings` record what Settings actually resolved, with the same
  functions the live session logs (`pipecat_voice_effective_flags`).
- **`production_inferred` is not verified.** It was inferred from Railway variable names on 2026-10-11: five flags were
  seen set to true (answer-first, interrupt intents, overlap duck, playback-grounded history, incomplete-turn hold); ten
  more were present with unreadable values and are assumed true; `VOICE_DEEP_ACK_SECONDS` unset (0.6 default);
  `VOICE_TTS_IDLE_REFRESH_V1` not seen. Verify against the `pipecat_voice_effective_flags` log line of a live session
  and edit the file.
- **Seeds.** Run *i* of scenario *S* uses `seed + i*7919 + crc32(S) % 100000`; every run's seed is in `results.json`.
  The voice bench is deterministic: the same revision, profile, seed and N give identical numbers (the compare runner's
  smoke run on identical product code showed zero deltas).
- **Same code?** Two results with the same `meta.app_tree` ran the same `backend/app`.
- **Chat bench** times real wall clock on whatever host runs it; only compare numbers produced on one host in one
  sitting (the compare runner does this). Sample counts, warm-up count, host, CPU count and simulated delays are in
  the output.

## What the voice bench reports

Per scenario, as P50 / P95 with the sample count (runs where the event happened), plus accuracy:

| Metric | Meaning |
|---|---|
| accuracy | Runs whose outcome meets the scenario's expected outcome (`pass_outcomes` or the scenario's own rule), over runs graded |
| first useful audible response | First **answer** audio played, from the user's end of speech of the measured request; filler and tool narration never count |
| first audio (any) | First audio of any kind (filler, progress or answer) |
| filler heard before answer | Filler/progress talk time played before the first answer audio |
| barge-in → quiet | Barge-in speech onset until the old reply is ducked (`speech.duck` ramp done) or, without a duck, stopped |
| barge-in → silence | Barge-in speech onset until the old reply's last audio stops playing (full stop) |
| completion | End of speech of the measured request until the last `assistant_turn.complete` |
| answer / filler words heard | Words of the measured response actually played, answer and filler counted separately |
| duplicate lines | Played lines (two words or more) that repeat a line already played in the measured response |
| spoken, not displayed | Answer words played that the transcript (`assistant_text` deltas) never showed |
| history = heard | Stored assistant text equals what was played (no unheard words stored, no heard words missing) |

Older columns (late frames, mis-stamped frames, premature replies or actions, speculative runs, orphaned brain time)
are still reported further down `results.md`.

Scenarios S1–S12 cover pauses, backchannels, corrections, repeated interruptions, late audio, slow and failed tools,
approval safety, deep turns, "stop talking", "cancel it" and reconnects. S13–S18 cover the production flag
interactions: explanation during a running task with answer-first (bare "why?" and a phrased "why is it taking so
long"), the explain aside's stored history with playback-grounded history, an explanation that cuts the spoken answer,
and interrupt intents with ducking (bare "stop", a backchannel, a correction while ducked).

## What is and is not modelled

Real: every Pipecat processor between the socket and the providers, wired by the production `build_pipecat_voice_task`
(utterance gate, Flux turn strategies with backchannel/duck/aside handling, speculative generation, cognitive bridge,
answer-first narration, interrupt reporter, playback reconciliation, TTS audio contexts, output pacing, persistence and
the barge-in write gate). The chat bench runs the production turn path (intent gateway, tiers, classifiers, tool
selection, governed tools) on both surfaces.

Not modelled:

- **No acoustics.** No microphone, echo, echo cancellation, noise or audio quality; "voice quality" here is a text
  proxy (answer vs filler words, repeated lines, speech the transcript does not show), not a listening test.
- **No real vendor latency.** Deepgram Flux, ElevenLabs and the model are scripted with fixed, jittered delays
  (`Conditions` in `tests/e2e/voice_scenarios/harness.py`, listed per scenario in `results.md`). The chat bench's model
  is scripted (no model time) and its web search (1000 ms) and Gmail reads (150 ms) are simulated.
- **No network** (one-way delay 0), no CPU load in the voice bench (virtual time makes processing free), no multi-worker
  Redis (in-process stop markers), no client-side `bargeIn()` path, HTTP fallback or AudioContext jitter.
- The scripted brain does not choose tools or words; the plans are fixed per scenario, so accuracy measures the voice
  pipeline's handling of turns, not the model's answers.

Live audio therefore still needs a live check: the bench says which behaviour to expect and where it breaks; real
first-audio and interruption timings come from production session logs (`pipecat_voice_effective_flags`, the voice
latency observer) on the verified flag set.
