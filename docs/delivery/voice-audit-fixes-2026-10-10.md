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
- Each buffered event's retained size is counted. Past the retained budget (512 KB in #351, 2 MB since the full-audit pass) the run stops, releases its buffer and is never adopted (`over_budget`).
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

## Follow-up after the PR #351 review

The review of #351 at 7ef50af reproduced three gaps. All three were confirmed in code and fixed in the follow-up PR. Tests: `tests/services/pipecat_voice/test_audit_followup_fences.py`; 8 of its 10 tests fail without the fixes, and the other 2 are controls.

1. **A failed state read counted as known state.** `ConversationStateService.get_task_state` caught read errors and returned the default state, so strict adoption saw "known and empty".
   - It now takes `strict=True`, which raises on a failed read.
   - The adoption state read uses it, so a failed read is `known=False` and is never adopted.
   - Other callers keep the old fallback.
2. **A late replay could overwrite a correction.**
   - Every deferred write now records the turn token that deferred it, and it replays (or drains late) under that token.
   - `_persist_state` drops a task_state write when its turn is cancelled. The check runs right before the database update, with no await between them.
   - So a cancelled or superseded turn's state cannot land, whether it comes from a replay, the late-write thread or the turn itself.
   - Audit writes are not fenced.
3. **The size count missed deep and unknown payloads.** The count now walks the whole event, including objects.
   - A payload deeper than 32 levels or over 50,000 nodes counts as over budget.
   - Unknown objects count their in-memory size.

## Full audit, step 1 (F1, F2, F6)

The full voice audit (`/mnt/project-files/audits/chatgpt-voice-full-prompt-audit-2026-10-10.md`) recommended five steps. This pass does step 1. Tests: `tests/services/pipecat_voice/test_audit_followup_fences.py`.

1. **F1: task_state saves blocked the voice event loop.** `_persist_state` ran its read and update on the loop.
   - The read-merge-write now runs on the I/O pool, on one worker thread, under a striped per-conversation lock, so concurrent writers cannot lose updates.
   - The cancellation fence sits under the lock, right before the update.
   - Regression: a 150 ms database no longer delays a 10 ms timer on the loop (it fired after 331 ms before the fix).
2. **F2: a cancelled turn could still promote memory.** Writers that change what later turns believe are now dropped when their turn is cancelled (`superseded_write` in `turn_cancellation.py`):
   - task_state and the active objective;
   - the channel override;
   - turn memory promotion and confirmed workspace memory.

   Factual records still land for a cancelled turn: audit events, latency and turn traces, connector outcomes, created recommendations and conversations.
3. **F6: the size count missed slotted objects and wide text.** Strings count their real in-memory size, objects are walked through `__slots__` as well as `__dict__`, and an unknown opaque container counts as over budget. Because real sizes are larger than character counts, the retained budget is now 2 MB (a normal answer measures about 22 KB).

Not in this pass: separate task and reply lifetimes (step 2, also finding 6 above), real-device validation (step 3), dependency-scoped preparation reuse (step 4) and held audio (step 5).
