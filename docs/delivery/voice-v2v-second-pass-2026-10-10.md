# Voice-to-voice second pass (2026-10-10)

What this covers: a comparison of SpeakRail and the OpenAI and Claude voice docs against Gravitre's voice path, the changes on this branch, baseline-versus-candidate results from a new offline scenario bench, the remaining uncertainties, and a rollout plan.

Evidence labels:
- **[DOC]**: vendor documentation.
- **[CODE]**: read in source (SpeakRail, read only and never run; or Gravitre).
- **[AUTHOR]**: a number reported by the SpeakRail author (README, charts, comments, or the Reddit post) that was not reproduced here. The Reddit post itself could not be fetched (site blocked), so no number from it is used.
- **[BENCH]**: measured on this branch's offline bench (n and conditions are given).
- **[HYP]**: inference.

Everything that already existed stays in place: Deepgram Flux, Pipecat, CognitiveTurnKernel, ElevenLabs Flash, routing, memory, knowledge, connectors, approvals and execution. The changes extend the existing processors (the turn strategy, the cognitive bridge, the interrupt reporter, speculative generation and the serializer). There is no new voice controller and no second reasoning path.

## 1. Source-to-Gravitre comparison

| # | Mechanism | Source | Gravitre before (b7c93f4) | Gap | This branch |
|---|---|---|---|---|---|
| 1 | Versioned, evolving requests | SpeakRail: the fork is adopted only if the live context length is unchanged and the live words are a word-prefix of the fork's [CODE session.py:898-905]. | Exact normalized string match, or a character prefix under the `voice_speculative_v2` flag (off). No version check. | Speculation was not bound to the state it ran against. | `voice_request_revisions_v1` (off): monotonic revisions bound to transcript, conversation, pending task, approval and context versions; a strict transcript check rejects qualifiers, negations and corrections; word-boundary prefix match. |
| 2 | Speculation before end of turn | SpeakRail fires at 0.5 and confirms at 0.9, generating in parallel with the turn decision [CODE]. OpenAI `semantic_vad` eagerness [DOC]. | Flux eager end of turn starts a speculative brain run. | The run used the full write path with no dry-run, so a discarded run could persist task state, objective, memory or audit rows. It had no timeout and an unbounded buffer. | **On by default:** a context-var dry-run scope. Durable writes are deferred and replayed only on adoption. Connector writes, approval staging and approval consumption are refused, which makes the run non-adoptable. 5 s timeout. 2000 char / 512 event buffer with backpressure. |
| 3 | Held audio | SpeakRail holds PCM until confirmation [CODE]. | Not implemented; speculative output stays text until adoption. | — | **Evaluated and not built.** Ceiling is about one TTS first byte (p50 120 ms [measured earlier, `voice-slo-parallelism-standard-2026-09-05.md`]). It would need a second ElevenLabs context, character spend on discards and a moderation wait. Revisit once production shows adopted runs have text ready at confirmation in 20% or more of turns. |
| 4 | Side-effect gating during speculation | SpeakRail gates stateful tools on `!held` [CODE 1137-1169]. | Text heuristics only. | See #2. | See #2, plus **on by default**: a turn now cancels its adopted speculative run when it ends. The adopted run kept working after a barge-in and committed the write the user had cut off (S11, also on main). |
| 5 | Backchannel versus interruption | SpeakRail: turn-head probability, lexical tiling and a 1.5 s safety yield; ducks to 0.15 gain while overlapping [CODE]. | Rule classifier with a 0.6 s grace window (up to 1.8 s with no words). | "Mm-hmm." was dropped by the utterance gate before the strategy saw it, so it counted as a barge-in (S2 interrupted 20/20). Barge-in to silence was about 1.65 s. | **On by default:** gated filler counts as a backchannel. Ducking: see §3. |
| 6 | Interruption intents | SpeakRail decision sets {continue, yield, listen} [CODE]. OpenAI GPT-Live guide: test "corrections while backend work runs" [DOC]. | Stop, correction, new question and interruption all behaved the same. | No "stop talking, keep working", no cancel report, no "explain". | `voice_interrupt_intents_v1` (off): backchannel, explain, correction, speech stop, task cancel, stop and new. Speech stop silences the reply and delivers the result once it is ready. Task cancel reports completed, unconfirmed and refused writes from recorded effects. |
| 7 | Write-stop race | — | The stop marker was armed after the ElevenLabs cancel, inside a thread. | A write past its check could commit. | **On by default:** an in-process stop is armed synchronously before anything else, and there is a last stop check right before the provider call. Each write's outcome is recorded. |
| 8 | Late audio from a cancelled reply | SpeakRail: per-utterance TTS kill, late PCM dropped at the router [CODE tts.py:61-98]. OpenAI: server truncation (WebRTC) or client `conversation.item.truncate` with `audio_end_ms` [DOC]. | The reply id was read from mutable session state at send time. | Mis-stamp risk. | **On by default:** reply id bound to the TTS context through in-band reply marks. Late frames played: 0 in S6 (provider keeps emitting 300 ms after close). |
| 9 | Concurrent conversation and deep reasoning | SpeakRail async frontier tasks with result injection [CODE]. OpenAI: measure acknowledgements separately from answers [DOC]. | Ack, progress narration and answer all went to TTS as produced. Metrics counted the ack as "first audio". | The answer queued behind filler (first answer about 6 s while first audio was about 1.4 s). Filler counted as the answer in SLO A. | **On by default:** labelled segments (filler / progress / answer), and SLO A now uses first *answer* audio. `voice_answer_first_v1` (off): non-answer lines are held as text, paced on a playout clock, and dropped once the answer is ready. Stale "let me check X" lines are dropped. |
| 10 | Playback-grounded history | SpeakRail pins history at the word playing at speech onset [CODE]. OpenAI truncates by played audio ms [DOC]. | Heard text came from the server transport clock, not the speaker. Filler and narration leaked into the stored reply on a cut. | History did not match what was heard. A reconnect showed the full unheard reply. | **On by default:** stored history keeps only answer text, with no filler or narration. `voice_playback_grounded_history_v1` (off): the browser sends `playback.progress` reports, the stored message is cut at the played word (whole-word rule), and reconnects are reconciled. |
| 11 | Incomplete thoughts and long pauses | OpenAI `semantic_vad` "less likely to interrupt the user" [DOC]. Claude voice mode is "designed to handle natural pauses" [DOC]. | Flux commits on silence. A fragment got its own reply (S1b, 9/20). | — | `voice_incomplete_turn_hold_v1` (off): a syntactically incomplete final holds its first output up to 600 ms. If the user resumes, the fragment joins the next turn. |
| 5b | Overlap ducking | SpeakRail ducks to 0.15 gain while the user overlaps, then the model decides [CODE]. | Bot kept full volume until the classification (about 1.65 s on a barge-in). | Slow audible yield. | `voice_overlap_duck_v1` (off): `speech.duck` / `speech.unduck` events, web gain stage at 0.15. |
| 12 | TTS chunking and phrase cache | SpeakRail: first clause of 3+ characters, then 40+, hard cut at 160, pre-rendered openers [CODE]. | Sentence chunks, emergency split at 180 characters. | Small. | Not changed. Answer-first removes most of the opener delay that a phrase cache would hide. |
| 13 | Audio-clock latency split | SpeakRail anchors at ASR word end plus the client play start [CODE]. | Per-stage turn trace already existed. | Filler was not separated. | First audio per kind in the turn trace. |
| 14 | Session setup (WARP) | DTLS 1.3 + SPED + SNAP for fewer round trips at WebRTC setup [DOC]. | WebSocket transport. | Session setup only; no effect on turn latency. | Out of scope. |
| 15 | Confirmation then hesitation ("yes… wait") | OpenAI GPT-Live guide: test "corrections while backend work runs" [DOC]. | A bare "yes" ran the approval and send at once. | Email sent 5/20 (S8, seed 7). | **On by default:** `voice_confirmation_hold_v1` holds a bare confirmation 600 ms. |

Weak spots in SpeakRail that were not copied [CODE]:
- its plain-text history is not cut to the heard words;
- `played_words` ignores underruns;
- held buffers are unbounded;
- `killed_utts` grows forever.

## 2. Bench: what it is

`backend/scripts/bench_voice_scenarios.py` runs the production `build_pipecat_voice_task` on a virtual clock with:
- scripted Flux STT frames;
- a fake ElevenLabs-shaped TTS, including late frames;
- a scripted brain that uses the real write gate;
- a browser model with the client's drop rules and jitter lead.

The bench runs 15 scenarios (S1–S12 plus S1b, S2b and S7b). Each one is described in the results file.

**Not modelled:**
- acoustics, echo and echo cancellation;
- real Deepgram, ElevenLabs and model latency distributions;
- network jitter and loss;
- CPU load;
- multi-worker Redis.

These are **synthetic** numbers. They compare code versions under identical conditions and do not predict live latency.

## 3. Results: baseline versus candidate (n = 20 per scenario, seed 1000, P50 / P95 ms)

Baseline is main at b7c93f4. "Default" is this branch with every new flag off. "All flags" turns on:
- voice_interrupt_intents_v1
- voice_request_revisions_v1
- voice_playback_grounded_history_v1
- voice_tts_idle_refresh_v1
- voice_incomplete_turn_hold_v1
- voice_answer_first_v1

The all-flags numbers below exclude `voice_overlap_duck_v1`, which is measured separately after the correctness table.

### First answer audio heard

First audio of any kind is unchanged in every configuration, at about 1.35–1.5 s.

| Scenario | Baseline | Default | All flags |
|---|---|---|---|
| S1 long pause | 6038 / 6315 | same | **3282 / 4603** |
| S1b STT commits early | 6264 / 6719 | same | **4564 / 4754** |
| S2 backchannel | 5903 / 6310 | same | **3284 / 4396** |
| S3 correction before speech | 4874 / 6536 | same | **3245 / 3426** |
| S4 barge-in correction | 6750 / 7066 | same | **4792 / 5245** |
| S5 repeated interruptions | 6099 / 6297 | same | **3168 / 4226** |
| S7 slow tool (4 s) | 8435 / 8609 | same | **6115 / 6609** |
| S7b failed tool | 8053 / 8443 | same | **4524 / 4893** |
| S9 deep reasoning | 10087 / 10427 | same | **7633 / 8170** |
| S12 reconnect | 6098 / 6453 | same | **3263 / 4599** |

With all flags on, the filler and progress share of talk time drops from about 4.5 s to about 1.9 s in S1, S2 and S12.

### Correctness

| Scenario | Baseline | Default | All flags |
|---|---|---|---|
| S11 "cancel it" during an approved write: write committed | **20/20** | **0/20** | 0/20 |
| S11 brain time after the interrupt (orphan runs) | 56.1 s (20) | 0 | 0 |
| S2 "Mm-hmm." while the bot talks | interrupted 20/20 | **kept speaking 20/20** | kept speaking 20/20 |
| S10 "stop talking, keep working" | report never spoken | task cancelled, answered as a turn | **task completed, report spoken 20/20** |
| S1b reply to the fragment during the pause | 9/20 | 9/20 | **0/20** |
| History = heard (S1b / S2 / S4 / S5 / S6 / S12) | 0 / 0 / 0 / 0 / 0 / 0 of 20 | 2 / 20 / 0 / 0 / 0 / 0 | **20 / 20 / 20 / 20 / 19 / 20** |
| S12 brain sees the full unheard reply after reconnect | 20/20 | 20/20 | **0/20** (sees the heard part, marked) |
| Late frames of a cancelled reply played (S4, S6) | 0 | 0 | 0 |
| Speculative side effects before adoption | not prevented | refused or deferred (tests) | same |

### "Yes… wait" on an approval (S8)

The user says "yes", pauses about 0.5 s, then says "wait". With seed 7, main sent the email in **5/20** runs. Seed 1000 happens not to hit the timing. Two causes:
- the bare "yes" started the brain, the approval and the send at once;
- a wordless "wait" start during thinking was held as a non-interruption.

The fix is `voice_confirmation_hold_v1`, **on by default**. A bare go-ahead ("yes", "send it", "yeah go ahead") that answers an assistant question waits `voice_incomplete_turn_hold_ms` (600 ms) before anything runs. If the user resumes with a stop, a correction or a new request, the "yes" is withdrawn and carried into the next turn.

| | Baseline | Candidate |
|---|---|---|
| S8 email sent, seed 7 | 5/20 | **0/20** (default and all flags) |
| S8 email sent, seed 1000 | 0/20 | 0/20 |
| Bare "yes" with no follow-up: end of turn to send | 0.78–1.03 s | 1.40–1.65 s (**+0.62 s**, the hold) |

Every other scenario is identical with the fix on or off.

Known gap: a wordless start followed by "stop" while a *non*-confirmation write turn is already running is still queued behind that turn instead of blocking the write. Closing it needs an interruption that does not flush the new turn [CODE trace].

### Overlap ducking (`voice_overlap_duck_v1`, off by default; measured separately)

While a user's speech is being classified (up to about 1.8 s with no words, because Flux sends no interim transcripts), the bot's audio drops to 0.15 gain within one ramp. It comes back to full level on a backchannel or echo, and is cut on a real interruption.

| Scenario | Barge-in to silence (flag off) | Barge-in to ducked (flag on) |
|---|---|---|
| S4 correction | 1638 / 1809 | **211 / 239** |
| S6 late audio | 1624 / 1806 | **230 / 242** |
| S5 repeated | 757 / 845 | **215 / 239** |
| S11 "cancel it" | 770 / 778 | **213 / 245** |
| S2 / S2b backchannel | kept speaking | ducked about 200 ms, restored 20/20 after about 590 ms, kept speaking |

- Every other metric is identical with the flag on or off. Ducked audio still counts as heard.
- The time to silence itself is unchanged. Ducking makes the bot get out of the way in about 0.2 s while the words are classified.
- The 0.2 s figure is the bench's 150 ms start detection plus the 60 ms ramp.


Raw results (Markdown, every metric and scenario condition) are in `docs/delivery/voice-v2v-bench-2026-10-10/`. Reproduce with:

```
cd backend
python scripts/bench_voice_scenarios.py --runs 20 --seed 1000 --out /tmp/bench-default
python scripts/bench_voice_scenarios.py --runs 20 --seed 1000 --out /tmp/bench-flags \
  --setting voice_interrupt_intents_v1=true --setting voice_request_revisions_v1=true \
  --setting voice_playback_grounded_history_v1=true --setting voice_tts_idle_refresh_v1=true \
  --setting voice_incomplete_turn_hold_v1=true --setting voice_answer_first_v1=true
```

## 4. Remaining uncertainties

- **Live acoustics and echo.** Nothing here was tested with a real microphone, speaker or echo canceller. Gated-filler backchannels and ducking depend on real Flux timing (final before `ProposedUserStoppedSpeaking`) [HYP].
- **Answer-first pacing.** The pacing constants (0.35 s lead, 0.25 s TTS-quiet window, 1 s grace for result lines) were tuned on the fake TTS and need checking against live ElevenLabs [HYP].
- **Playback-grounded history.** It assumes word alignment arrives close to its audio. Real ElevenLabs alignment can trail, which errs toward under-claiming [HYP]. S6 is 19/20 (one word off, not traced).
- **Incomplete-turn hold.** It only helps when the user resumes within brain time plus 600 ms. Longer pauses still get a reply to the fragment.
- **Request revisions.** They are measured but do not yet reuse partial work. The adoption rate in production is unknown until the counters (started / adopted / discarded / wasted s) are in the turn trace from live traffic.
- **Untested surfaces.** No real devices, mobile networks or reconnect storms were tested. The bench assumes zero network latency.

## 5. Recommended rollout

The code that is on by default is a set of correctness fixes:
- the speculation dry-run and bounds;
- adopted-run cancel;
- the synchronous write stop;
- reply-id binding;
- gated-filler backchannels;
- the bare-confirmation hold (adds 0.62 s before an approved action runs);
- answer-only heard history;
- segment labels.

Except for the 0.62 s confirmation hold, it does not change latency in any scenario (default equals baseline). It closes three real bugs:
- "cancel it" committing a write;
- "yes… wait" sending the email;
- "mm-hmm" cutting the bot off.

After merge, turn the flags on one at a time on Railway, each followed by a live voice test:
1. `VOICE_ANSWER_FIRST_V1=true`. Largest audible gain (first answer about 2.5 s sooner on the bench). Check that progress lines still cover slow tools.
2. `VOICE_OVERLAP_DUCK_V1=true`. Talk over the bot with "mm-hmm" (it should dip and come back) and with a correction (it should dip, then stop). Watch for any change in own-voice echo triggering.
3. `VOICE_PLAYBACK_GROUNDED_HISTORY_V1=true`. Cut a reply mid-sentence and ask "what did you just say?". Then drop and reconnect.
4. `VOICE_INTERRUPT_INTENTS_V1=true`. Test "stop talking, keep working", "cancel it" and "wait, explain that".
5. `VOICE_INCOMPLETE_TURN_HOLD_V1=true`. Test "I want to check… last month's traffic".
6. `VOICE_REQUEST_REVISIONS_V1=true`. Watch the adoption and discard counters for a day.
7. `VOICE_TTS_IDLE_REFRESH_V1=true`. Low risk; only rebuilds a dead socket after 45 s idle.

Rollback: unset the variable (each flag is independent), or revert the merge commit for the default-on fixes.
