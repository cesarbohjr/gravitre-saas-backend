# Live email audit fixes, 2026-10-11

This change covers the ChatGPT audit of Cesar's live email test against main c869f04a (PRs #352 and #353): its first PR (F1–F4) and the answer-ownership, narration and repair parts of its second. It changes routing, state handling and what is said. Reasoning depth, models and voices stay the same.

## F1: no public web search for actions, slot answers, retries or apologies

**Before:** thin internal retrieval (no RAG hits) started a web search for every turn. That included "email Stephanie", "Gmail.", "Try again… the email now?" and "Sorry." Each search cost seconds and sent private requests to Serper/Tavily.

**After:** `should_run_internet_research` runs auto-escalation only for real information needs. The new `auto_internet_research_blocked(query)` blocks auto-escalation for:
- action requests in the user's apps;
- retries;
- apologies and repair phrases;
- small talk;
- short slot answers of three words or fewer with no question mark.

Explicit research ("research … online", "search the web …") and a chosen internet scope still search. Reasoning depth and the routing tier are untouched.

The voice knowledge path (`unified_turn_knowledge_context`) called this check without the query, so no intent check could run there. Every call site now passes the query, and a test enforces it.

## F2: retry and "the email" continue the draft

**Before:** `recent_write_status_turn` matched a bare "the email" and loose "did you…". With no finished write, it stopped the turn with "I don't have a matching prior write in this conversation."

**After:**
- Identity questions must ask which record or address was used ("what's the email", "which contact").
- Status questions must ask about a write ("did it go through", "did you send the email").
- When nothing was written yet, the turn continues normally instead of hitting that dead end.
- A retry continues the task through the normal approval path. The one exception is a retry after an uncertain send: it is answered without resending ("I already tried that once and can't tell yet whether it went through, so I won't send it again until I've confirmed it didn't.").

## F3: a failed state read never replaces stored state

**Before:** `_persist_state_sync` treated a failed read as `DEFAULT_TASK_STATE`, merged the patch into it, and replaced the whole column. That erased the pending task and memory.

**After:** the read is retried once. If it fails again, the patch is dropped and logged as `persist_task_state_skipped_unknown_state`. The cancellation fence, the lock and off-loop I/O are unchanged.

## F4: memory cancelled during lookup or embedding is not written

**Before:** `promote_turn_memories` checked cancellation only on entry. A cancel during the agent lookup or embedding still wrote the row.

**After:** cancellation is checked again right before each insert or upsert. It is not checked between a temporal upsert's insert and its supersede update, because those must land together.

## F5: one answer per reply

**Before:** inside a task in progress, LIVE could start speaking a reply and then hand the turn to the pending-task path, which gave its own answer. The missing-details question reached text-to-speech twice (02:35:12 and 02:35:18).

**After:** `spoken_should_stream_live_deltas` does not stream LIVE speech while a task is pending (a draft waiting for details, an approval, a running plan). Only the final reply is spoken. Chitchat outside a task still streams.

## No retrieval chatter in voice

**Before:** voice said "Let me check your knowledge base" and "I found 5 of them".

**After:**
- Internal lookups (knowledge base, memory, web research, document search) are not narrated.
- A count is spoken only with a noun from the result ("I found 7 deals." or "I found one contact."). Otherwise nothing is said.

## Repair after "Sorry." and "No."

**Before:**
- While gathering email details, "No." cancelled the draft.
- "Sorry." was taken as a field value and planned as a write.

**After:**
- "Sorry", "my bad" and similar keep the draft. The reply is one short line: "No worries. I've still got the email to Stephanie. I just need the subject and body."
- A bare "No." while gathering details keeps the draft and asks "Okay. Should I drop the email to Stephanie, or change something?"
- Once the email waits for approval, "No." still cancels, as do "cancel it", "never mind" and the other cancel phrases.

## Tests

`backend/tests/services/test_live_email_audit_fixes.py` has 33 tests covering F1–F5 and the repair replies. Each regression was checked to fail without its fix. Narration tests in `tests/services/pipecat_voice/` now use real CRM tools and nouns.

## Not in this PR

- Enabled-state evidence for the flags (an effective-flags log at session start is already added by #353; checking it on Railway needs Cesar).
- Explain-aside playback history.
- The measured voice A/B (three voices on Flash, 30+ reps per scenario).
