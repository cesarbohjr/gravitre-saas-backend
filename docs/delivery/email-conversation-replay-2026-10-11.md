# Email conversation replay (2026-10-11)

Follow-up to PR #355. The full email conversation from Cesar's live voice test was replayed on both surfaces (text and voice) through the real turn path. Every reply was checked for what a person would notice. The replay is now a permanent test: `backend/tests/scenarios/test_email_conversation_scenarios.py`.

## What the conversation says now

| User says | Before | Now |
|---|---|---|
| Can you send an email to Stephanie on Gmail? | "…what subject and body should I use?" | "…what subject and message should I use?" |
| The subject is Quick update. | Filled the subject **and** used the sentence as the body, so the draft went straight to approval with "Body: The subject is Quick update" | Fills only the subject. "What should the email say?" |
| Tell her the proposal is ready for review. | "still waiting for your approval" (the body was already wrong) | The message becomes "The proposal is ready for review." |
| (approval prompt) | "I'll run this in Gmail: **Send email**. - To: … - Body: … Reply **yes** to approve…" on one run-on line | "Here's the email to stephanie@…:" followed by Subject and Message lines, then "Should I send it? Say **yes**, or tell me what to change." |
| Okay, go ahead. | Not treated as approval | Sends exactly once |
| (after the send) | "**Send email** is on its way. I'm still checking… Verified in Gmail… completed Verifiedly… _Suggest only — reply_ **What should I do next with this?**" | "Done, and I've confirmed it. Sent to stephanie@… with the subject "Quick update". A copy is in your Gmail Sent folder." plus the links |
| Did you send the email? (after) | "Yes, that's done, and I've confirmed it." | "Yes, it went to stephanie@…, and I've confirmed it." |
| Try again. (after a confirmed send) | Went to the model ("Okay."), with nothing stopping a second send | "That already went through to stephanie@…, so I won't send a duplicate. If you want something new, tell me what to change." "Send it again" and "resend" still take the normal approval path. |
| Unclear reply while details are missing | "I'm not sure how to apply that to **X**. Still needed: subject, body" | "I still need a few details for the email to Stephanie. What should the subject and message be?" |

The PR #355 repair lines ("Gmail.", "No.", "Try again… the email now?", "Sorry.", "Did you send the email?") now end in the same single question.

## Fixes that reach beyond email

- **Paragraph breaks were being collapsed in replies.** Three last-mile cleaners (`scrub_internal_tool_references`, and two spots in `response_composer`) collapsed every run of whitespace, newlines included. Every finalized reply lost its paragraph breaks and its first list line. They now collapse only spaces (`collapse_spaces_keep_lines`).
- **Voice read out link labels** ("View in Gravit tree, View in Gmail"). The voice tag scanner flattened newlines before the spoken-text normalizer could see them. Lines are now kept, and a line that holds nothing but links is screen-only. A line ending in ":" no longer gets a "." added.
- **Raw message IDs in the Gmail send summary.** The "Message id: …" text was removed; the ID stays in structured data.
- **"Verified in {vendor}" was said even when nothing was verified.** It now says "Confirmed in {vendor}" only when verification passed.
- **The generic "decide the next step" card no longer appears in the text.** A specific next step becomes one plain sentence: "If it helps, next I can … Just say so."
- **Natural approvals.** "Okay, go ahead.", "yes please", "Sounds good, send it." and "Yeah go for it" now approve. "Perfect, thanks!" and a bare "please" do not. "Yes… wait." still holds the send.

## Explain-aside history (audit item)

With `VOICE_EXPLAIN_ASIDE_V1` (which needs `VOICE_INTERRUPT_INTENTS_V1`), a barge-in during an aside was stored as the running task's answer. The aside's words ("Conversions are the sign-ups…") were written under the task's question ("Pull last month's ads report"), giving a duplicate user row. That text was also handed to the next turn as what the user heard.

The interrupt reporter now knows when the live reply is an aside:

- It marks `speech.interrupted` with `aside: true`.
- It skips the heard-text rewrite and the in-memory heard text for the task.
- On a socket drop during an aside, it leaves the task's row alone.

The task still stores its own row when it finishes. Regression test: `test_a_barge_in_during_an_aside_never_stores_the_aside_as_the_task_answer`, with grounded history on and off.

Known remaining gap: an aside whose text finished streaming before the user cut off its audio is still stored in full.

## Tests

- `tests/scenarios/test_email_conversation_scenarios.py` replays the 12-turn conversation on text and voice and asserts:
  - no web searches;
  - the draft survives "No." and "Sorry.";
  - the subject alone does not fill the message;
  - "Yes… wait." holds;
  - "Okay, go ahead." sends exactly once;
  - no duplicate after "Try again.";
  - no link labels are spoken;
  - paragraph breaks survive in text.
- The scenario harness's fake Gmail now returns a message ID and answers `messages.get`, as real Gmail does, so sends can be verified.
