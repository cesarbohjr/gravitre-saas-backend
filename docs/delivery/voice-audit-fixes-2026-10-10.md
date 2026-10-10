# Voice audit fixes after PR #349 (2026-10-10)

This pass answers the external audit of PR #349 (main at b70c992). The audit is kept at `/mnt/project-files/audits/chatgpt-voice-audit-pr349-2026-10-10.md` in the project's shared files. Each finding below says what was checked and what changed, and names the tests that cover it.

## Per-finding changes

### 1. P0: a late "cancel it" during silent work did not interrupt
Confirmed in code. Once the turn was in held thinking (no audio playing), a later "cancel it" was only noted as an escalation. The running kernel call kept going until its next event, and a slow connector write could commit.

Fix:
- Each turn gets a `TurnCancellation` token (`app/services/turn_cancellation.py`).
- The token is bound into the turn's context and into the worker threads `async_bridge` starts.
- `is_stop_requested` checks the token first.
- The turn loop now waits on the token alongside the event stream (`with_silence_ticks(..., cancelled=...)`), so it stops in the middle of a silent tool call.
- The held-thinking branch of the turn strategy cancels the token for task cancel, stop and correction intents.

Tests: `tests/services/pipecat_voice/test_turn_scoped_cancellation.py`.

### 2. P1: cancellation was conversation-scoped
Confirmed. The stop marker was keyed by conversation, so a new turn or a reconnect cleared it while the old work was still running.

Fix: cancellation now belongs to the turn's token. A cancel is final for that token. A new turn creates a new token and cannot un-cancel the old one. An adopted speculative run's token is linked, so cancelling the turn also cancels the run.

### 3. P1: strict adoption was optional and matched on unknown state
Confirmed on all four points.

Fixes:
- Strict version checks are always on, and `VOICE_REQUEST_REVISIONS_V1` is retired.
- When state could not be read, `known=False` is set and the run is rejected with `versions_unknown`. Two unreadable states no longer count as equal.
- Principal (org, user, agent) and prompt versions are part of the match.
- Number punctuation is kept in normalization ("1.5" no longer matches "15"; thousands commas are ignored).
- "again" is no longer an inert tail.

Tests: `TestAdoptionContract` in `test_speculative_bounds_and_revisions.py`, plus the adoption and parity tests.

### 4. P1: playback history overclaimed
Confirmed.

Server fixes:
- With no browser report, exposure is marked unknown, and stored history gets an explicit "not known how much was heard" marker. Sent audio is no longer counted as heard.
- Client reports are clamped so played ≤ received ≤ sent.

Browser fix: a newer reply no longer marks an older reply's reporting as final while its audio is still playing. It only stops receiving, and becomes final once played catches up.

Tests: `test_voice_reply_playback.py`, `test_interrupt_reporter_answer_history.py`, and `apps/web/__tests__/lib/voice-playback-progress.test.ts`.

### 5. P1: bookkeeping and replay were on the critical path
Confirmed.

Fixes:
- A barge-in now waits only for the shared stop write before the next reply.
- History rewrites and the cancel report run in the background. `flush_bookkeeping()` is awaited before persisting rows, so ordering holds.
- The heard text is recorded provisionally the moment the stop frame is pushed.
- An adopted run's deferred writes replay in the background while its events stream. The turn awaits the replay before it ends.

Tests: `TestAdoptedReplayOffTheFirstWord`, and `test_interrupt_reporter_durable_behaviour.py`.

### 6. P1: an "explain" interrupt did not preserve the running task (deferred)
Confirmed and **not fixed in this pass**. An explain answer during a running task needs that task to keep running detached from the turn while a second reply speaks. It also needs the TTS, the interrupt reporter and the client to interleave two replies safely. That is the audit's own step 5 ("separate lifecycles"), and it is too risky to ship without a live test. Behaviour is unchanged from main:
- An explain barge-in while a reply is playing stops the running work, like any barge-in did before.
- During silent held thinking, an explain does not cancel. That is the one place this pass leaves work running.

### 7. P2: speculative limits did not bound payloads
Confirmed. The limits counted characters and events, not the size of tool outputs or the final payload.

Fixes:
- Each buffered event's retained size is counted. Past 512 KB the run stops, releases its buffer and is never adopted (`over_budget`).
- A run that reaches 256 deferred writes is blocked from adoption.

Tests: `TestRetainedBudget`.

### 8. Bench evidence gap (not done here)
The offline bench cannot be replaced by a live bench from this environment. Railway and production are not reachable from here. The live check is Cesar's combined test after deploy.

## Not changed
- The S6 19/20 history discrepancy and the numeric pronunciation alignment in the audit's notes are not addressed in this pass.

## Flags
- `VOICE_REQUEST_REVISIONS_V1` is retired: strict adoption is always on, and the variable is ignored. It can be deleted from Railway at any time.
- All other voice flags are unchanged and stay as set on Railway.

## Rollout and rollback
- Merging to main deploys Vercel and Railway. Merge happens only on Cesar's go.
- Rollback: revert the merge commit on main, which redeploys both. No migration is involved, and no Railway variable needs changing.
- Signs to watch after deploy:
  - a "cancel it" during a long lookup stops it and reports what was done;
  - a reconnect after a cut shows the unheard marker, not the full reply;
  - first-word latency on adopted turns is no worse than before.

## Validation
- Backend: 1241 tests in `tests/services/pipecat_voice` and `tests/services/test_speculative_execution.py` pass. Related bridge and side-effect tests also pass.
- Web: vitest for `voice-playback-progress` passes, and `tsc --noEmit` is clean.
