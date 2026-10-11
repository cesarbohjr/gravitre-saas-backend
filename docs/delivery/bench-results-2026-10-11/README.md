# Bench results, 2026-10-11

Product code: `backend/app` at a7719cba (tree a87a03439f64d079deda64e4686dc9fc5d7591a7; the bench branch changes no
product code). Bench driver: the commit that adds this directory. How to run and what is modelled:
`docs/delivery/benchmarks-README.md`.

| Run | Directory | Conditions |
|---|---|---|
| Voice, production flags (**inferred, not verified**) | `voice-production_inferred/` | 22 scenarios × N=20, seed 1000, virtual clock |
| Voice, code defaults | `voice-defaults/` | same |
| Chat turns | `chat-turns/` | 8 turns × 2 surfaces × N=15 (+1 warm-up per surface), real wall clock, web search 1000 ms, Gmail read 150 ms; 4-CPU Linux container |

Reproduce: `python scripts/bench_voice_scenarios.py --profile production_inferred --runs 20 --seed 1000 --out …`
(identical numbers on the same revision), `python scripts/bench_chat_turns.py --runs 15 --out …` (host-dependent).

## Headline

| | production_inferred | defaults |
|---|---|---|
| Voice accuracy (all graded runs) | 380/440 (86%) | 312/440 (71%) |
| First useful audible response (answer), simple traffic question S2, P50 / P95 | 3217 / 4388 ms | 4324 / 4968 ms (answer-first off: 2880 ms of filler queued ahead) |
| First audio of any kind, S2, P50 / P95 | 1413 / 1512 ms | same |
| Barge-in → quiet (duck), S4, P50 / P95 | 211 / 239 ms | 1638 / 1809 ms (no duck: full stop) |
| Barge-in → silence (full stop), S4, P50 / P95 | 1638 / 1809 ms | 1638 / 1809 ms |
| Bare "stop" → silence, S16, P50 / P95 | 735 / 884 ms (ducked at 209 / 241) | 735 / 884 ms |
| Slow tool (4 s), first answer, S7, P50 / P95 | 6115 / 6609 ms (filler before it 3200 ms) | 6835 / 7009 ms (filler 4000 ms) |
| Duplicate lines / words spoken but not displayed (all runs) | 0 / 0 | 0 / 0 |

Chat turns (P50, text / voice): own-data and small-talk turns 1.8–2.0 s with no web search; email by name 0.48 / 0.50 s;
"thanks" 26 / 9 ms; news control 3.1 s with one search. 240/240 samples met their expected outcome.

## Product problems the new scenarios exposed (not fixed here)

1. **Explain aside never starts; the running task is cancelled instead** (S13b, S14: 0/20 under the production
   profile). `backchannel_turn_strategy.py`, on-final branch of the aside hold: `trigger_user_turn_started(...)` fires
   `handle_user_turn_started`, which clears `self._buffer_text`; the next line calls
   `_try_start_aside(self._buffer_text)` with an empty string, so the aside is refused, the code logs
   `voice_turn_taking_explain_aside_escalated text=''` and broadcasts an interruption, which cancels the adopted task
   (`pipecat_voice_adopted_run_cancelled`). With Flux (no interim transcripts) this on-final branch is the only path in
   production, so "why is it taking so long" / "what does that mean" during a running task cancels the task. With the
   lost text restored in a scratch run, S13b passed (aside spoken, result spoken once afterwards).
2. **Aside history order** (latent behind 1; seen only in that scratch run): the aside's user/assistant rows are stored
   before the running task's own user row, so the next turn's history reads "why …?" → aside → "pull the pipeline
   report" → result, the reverse of what was said (S14 outcome `request_stored_after_aside`).
3. **Bare "why?" is not an explanation request** (S13, 0/20 in both profiles): `classify_interrupt_intent("why?")` is
   NEW_REQUEST, so a bare "why?" during a running task cancels the task and becomes a new turn; the cancelled task's
   request is then not in durable history at all (only "why?" and its answer are stored).

Expected-by-design failures under `defaults` (flags off): S1b speaks during the pause (9/20), S10 cancels the task on
"stop talking, keep working", S12/S15 store unheard text (no grounded history).
