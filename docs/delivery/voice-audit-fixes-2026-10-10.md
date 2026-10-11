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

## Full audit, step 2 (F3): explain while the task keeps running

Behind `VOICE_EXPLAIN_ASIDE_V1`, which needs `VOICE_INTERRUPT_INTENTS_V1`. Both default to off.

Before: asking "what does that mean?" while a task ran either waited behind the task (during silent thinking) or cancelled it (while it was speaking).

After: the question is answered as a short aside, and the task keeps running.
- The turn strategy and the transcript relay both use `VoicePipelineSession.explain_aside_applies`, so the browser and the server agree the words are an aside and not a new turn. If the final words turn out to be something else ("what does that mean, actually cancel it"), they become an ordinary turn after all.
- The aside's reply runs alongside the task's reply:
  - The task's reply is silenced and closed.
  - The aside speaks under its own reply id.
  - The task's reply then reopens, still silent, under a new id.
  - The task's result is spoken once after the aside, or only shown if the user moved on or had asked for silence. The turn never closes its reply in the middle of an aside.
- The aside runs the same brain in fast mode, with the task's facts so far: the request, finished tool results, tools still running, and the answer text so far. It runs inside a discarded speculative scope, so it cannot write anything. Its question and answer are stored as their own exchange.
- Cancelling the task ("cancel it", a correction) also cancels its aside, so no stale result is spoken. A real barge-in cuts the aside off. A newer aside replaces an older one. A failed aside says "I couldn't answer that just now" and the task still delivers. An aside is cut off after 20 seconds.
- The web client shows the aside as its own exchange. The running reply keeps its place and finishes after it.

Tests: `tests/services/pipecat_voice/test_explain_aside.py` (19 tests). Each fence was removed in turn and a test failed every time. Web: `voice-playback-progress.test.ts`.

Not covered: the aside is not tested on real devices or with live models yet (audit step 3).

Step 1 follow-up: saves erased keys they did not know. On main too, every task_state save rebuilt the column from the known keys only, so a later save erased `conversation_memory` (and any other key outside `DEFAULT_TASK_STATE`). It showed up as a rare failure in `test_adopted_speculative_turn_persists_the_same_state_as_a_confirmed_turn`, which failed 1 in 60 runs under load on main and 6 in 60 after step 1 moved saves off the loop. Saves now keep unknown keys (`_normalize_state(keep_unknown=True)` in the read-merge-write). Reads are unchanged. The test now ignores only where the fire-and-forget memory save lands in the write order, and still compares the full end state. Under the same load it fails 0 in 60. Regression: `test_a_save_never_erases_keys_it_does_not_know`.

Step 1 note: task_state saves are serialized per conversation within one server process. Across several server processes the database update is still last-write-wins. The cancellation fence still applies, but it is not a database-side conditional update.

Step 1 follow-up (Bugbot): every task_state writer takes the same lock. Step 1 locked only the save. The approval claim (`_compare_and_set_pending_status_sync`) and the channel override still wrote task_state without it, so a save could wipe a live approval claim, or a claim could wipe a save. Both now run under the per-conversation lock. The channel override uses `apply_task_state_change_sync`, which applies its change to fresh state under the lock instead of writing back the snapshot its turn read. Regressions: `test_an_approval_claim_and_a_save_never_wipe_each_other` and `test_a_channel_override_keeps_what_was_saved_since_the_turn_read`; both fail without the fix.

Second Bugbot pass:
- The channel override checked its cancellation fence before it waited for the lock, so a cancel that landed while it waited could still save `channel_override`. `apply_task_state_change_sync` now checks the fence under the lock, after its read and right before the write, like the save does. Regressions: `test_a_channel_override_cancelled_while_waiting_for_the_lock_is_not_saved` and `test_a_channel_override_cancelled_during_its_read_is_not_saved`.
- A guardrail refusal of the aside question was caught as a generic failure, so the user heard "I couldn't answer that just now" instead of the guardrail's line. The aside now speaks the guardrail's line. Regression: `test_a_refused_aside_says_the_guardrail_line_and_the_task_still_delivers`.
