# Chat and voice engineering pass (2026-10-11)

One reviewable change for the 2026-10-11 brief: correctness first, then request revisions, retrieval routing, interruption meanings, timing, delivery, reconnect, measurements, and finding people by name (item 16).

Supporting audits, in `/mnt/project-files/audits/voice-pass-2026-10-11/`:
- `baseline.md`: revisions, flag inventory, capability matrix, key gaps.
- `correctness-findings.md`: state, cancellation, stale-write and duplicate-answer audit.
- `source-comparison.md`: SpeakRail and OpenAI/Anthropic practices against Gravitre, with proposed adaptations.
- `interruptions-timing-reconnect.md`: interruption meanings, turn timing, reconnect, playback grounding and voice quality with the production flags on.
- `name-resolution.md`: item 16, connector capability table, supported versus proposed.
- `measurements.md`: bench method and raw numbers.

## 1. Revisions

| | Commit | Notes |
|---|---|---|
| Baseline | `b5fad269` | main after PR #356. |
| Candidate | this branch | Every change below. No migration. No new required setting. |

Production values were not observable from this session (Railway, production Supabase and api.gravitre.app are unreachable). Every claim about production configuration comes from project notes.

## 2. Ranked findings and what this PR does about them

| # | Severity | Finding | In this PR |
|---|---|---|---|
| 1 | High | A cancelled voice turn lost the record of a write that had already gone out, and the carried request could send it again. | Fixed. Write effects are recorded whatever happens to the turn; a cancelled turn that reached a provider with a write is never carried or re-run; a write not yet sent never starts. |
| 2 | High | A write's outcome record was built from a snapshot taken before the provider call, so a newer draft saved meanwhile was overwritten. | Fixed. Outcomes are built from state read under the per-conversation lock (`update_task_state_from`), and a newer draft survives a late outcome. |
| 3 | High | "Actually, make the subject Weekly update" after the approval prompt got "still waiting for your approval", and the yes sent the old subject. | Fixed. The draft is revised, the approval is re-bound to the new details (new approval id and digest), the prompt is shown again, and the send carries exactly the approved details. Both chat paths. |
| 4 | High | "Send an email to Stephanie" never looked anyone up; a model-written address could reach the approval prompt. | Fixed for Gmail (item 16). See section 4. |
| 5 | Medium-high | One failed read wiped conversation memory, and two concurrent writers lost an entry. | Fixed. Unknown state saves nothing rather than defaults; memory updates are read-modify-write under the lock. |
| 6 | Medium | Memory was promoted for failed or uncertain writes ("Confirmed action: Send email" after a 4xx). | Fixed. Only a successful write is promoted. |
| 7 | Medium | Text turns had no cancellation fence; Stop could not stop a late save or a write not yet sent, and always said nothing was completed. | Fixed. Text turns get the same per-turn token as voice; the stopped-turn copy comes from the recorded write effects. |
| 8 | Medium | Arithmetic, clock, "what did I just ask", own-data and definition questions escalated to a public web search when the knowledge base was empty. | Fixed in both the research gate and the evidence escalation loop. News and other recency questions still search. |
| 9 | Medium | A draft request in Gmail returned "That tool isn't connected yet". | Fixed with an honest answer: drafts are not supported yet, nothing was saved, and the user can have the text or approve a send. |
| 10 | Medium | "Thanks!" after a missing-details question became the email subject, and the question was repeated. | Fixed. Social replies never fill a field unless the message body is the only thing missing; the missing-details question reads like a person and is asked once. |
| 11 | Low-medium | A write's "Done, that went through" and the answer both reported the same outcome in voice. | Fixed. The result line waits 2.5 s for the answer and is spoken only if no answer comes. |
| 12 | Low-medium | In voice, a clarifying question could be followed by a generic fallback line. | Fixed. When the streamed text is the question, it is the answer. |
| 13 | High | A spoken "yes" over the email approval prompt was treated as a backchannel, and "yes... wait" got no hold, because the prompt ends "Say yes, or tell me what to change." rather than "?". | Fixed. A reply ending in a reply invitation counts as a question for both the backchannel check and the confirmation hold. |
| 14 | High | "Cancel it" said over a reply answered "Okay, cancelled" but left the staged email awaiting approval, so a later "yes" could still send it. | Fixed. The cancel also withdraws an unclaimed staged write and says so ("I've dropped the email too, so nothing will be sent."). A write already claimed for execution finishes and is reported as before. |
| 15 | Medium | With answer-first on (production), a write's result line waited only 1.0 s for the answer, so the outcome could be said twice. | Fixed. It waits 2.5 s, as without the flag. |
| 16 | Medium | The voice bench showed a new short acknowledgement ("Let me check.") released a held tool line ("Let me check google analytics report.") ahead of the answer, adding about 1 s in some runs. | Fixed before merge: acknowledgements no longer include "Let me check." or lines much shorter than before. |
| 17 | Low | The session flag report left out every number (acknowledgement delay, Flux thresholds, TTS model) and shared switches, and listed a retired flag. | Fixed. `session.ready` and the start log now carry `effective_settings` (names from a fixed allow-list, never keys or URLs). |
| 18 | Low | Cross-process lost updates (the lock is per process), text-only answer dedupe, no request-level idempotency on turn persistence. | Not changed. Documented in `correctness-findings.md`. |
| 19 | Low | "Who won the World Cup in 2022?" is classified as social and never searches. | Not changed (pre-existing classifier behaviour, outside this pass's write and voice paths). |

Interruption, timing, reconnect, playback and voice-quality findings are in `interruptions-timing-reconnect.md`. Its findings 1, 2 and 8 are fixed here (rows 13 to 15). Still open, ranked, as proposals:
- High: "why?", "hold on" or "wait, why?" while a task runs cancels the task, and the request is lost once anything was spoken. Needs a wider explain-aside phrase set and a carry rule for filler-only speech.
- Medium-high (inferred): a dropped socket does not stop its pipeline, so a result finishing after a reconnect is spoken into the dead socket. Needs the reconnect to cancel the old session's turn and hand its result to the new one.
- Medium: a bare "stop" keeps the reply playing ducked for up to 1.8 s; the acknowledgement clock starts after pre-answer work; Flux end-of-turn timeout is left at 5 s; an explain aside mutes later progress lines; no deterministic number, date, URL or email clean-up before Flash.
- Untested flag pairs: intents with ducking, explain aside with answer-first or with playback-grounded history, ducking with playback-grounded history.

## 3. Request revisions

`app/services/pending_write_revision.py` recognises subject, message and recipient edits to a staged email ("make the subject X", "the subject should be X", "make it say X", "change the message to: X", "send it to Y instead"). Questions, cancels and approvals are not edits. Only a write that is awaiting confirmation, unclaimed and not yet executing can be revised; a queued, claimed or finished write cannot. A revision:
- re-binds the approval with `bind_plan_dict` (new approval id and argument digest), so the old approval cannot approve the new details;
- updates the plan step, the clarified parameters and the parameter ledger;
- shows "Got it, I changed the subject." followed by the full approval prompt again.

Execution compiles the approved arguments as approved (`args_approved`), so the ledger and the original sentence can no longer override an edited field. The preflight proof still seals the compiled parameters.

## 4. Finding people by name (item 16)

Gmail recipients are supported in this PR on both chat paths, so chat and voice share one contract. Lists, segments, files, CRM records and Outlook are proposed, with a connector-by-connector table in `name-resolution.md`.

- One match: "I found Stephanie Khan in your Gmail correspondence. What would you like to say?"
- Two or more: "I found two Stephanies: Stephanie Khan and Stephanie Miller. Which one?"
- None: "I couldn't find Stephanie in this mailbox. Is there another name I should look for, or do you have the email address?"

The lookup reads message headers only, never writes, excludes the user's own address, ranks draft-only matches below real correspondence, and gives up after 4 seconds without guessing. The chosen address goes through the normal approval prompt and binding. No public web search is involved.

## 5. Regression evidence

New scenario and unit tests (chat and voice surfaces where a surface applies):
- `tests/scenarios/test_pending_write_revision_scenarios.py`: changed subject, message and recipient are what is sent, once; the old approval id is replaced; claimed, queued and finished writes are not revised.
- `tests/scenarios/test_recipient_resolution_scenarios.py`: one, two and no matches, picks by surname, ordinal and full name, own address, drafts, duplicate names, aliases and lists.
- `tests/scenarios/test_retrieval_routing_scenarios.py`: seven questions start no web search on either surface; a news question still does.
- `tests/scenarios/test_email_request_edges_scenarios.py`: honest draft answer, "thanks" is not a subject, one question.
- `tests/services/test_state_write_correctness.py`: findings 1a, 1b and 3a.
- `tests/services/pipecat_voice/test_explain_aside.py`: the settings report has the tuning values and no secrets.
- `tests/services/pipecat_voice/test_confirmation_hold.py` and `test_voice_live_test_regressions.py`: "yes" over the approval prompt is an answer and is held.
- `tests/services/pipecat_voice/test_interrupt_intents.py`: "cancel it" withdraws an unclaimed draft and leaves a claimed write alone.
- `tests/services/pipecat_voice/test_cognitive_llm_tool_narration.py`: a write's outcome is said once, with and without answer-first.

FULL_SUITE_RESULT

## 6. Measurements

MEASUREMENTS

## 7. Configuration

No new required setting and no migration. Nothing here changes a default flag.

- After deploy, read one voice session's `pipecat_voice_effective_flags` log line (or `session.ready`), which now includes `settings=`. It settles which flags and values production actually runs with.
- `VOICE_DEEP_ACK_SECONDS` is not set in production (per notes), so the "One moment" acknowledgement fires after 0.6 s of silence. Set it to `0` to turn it off.
- Web research stays governed by `INTERNET_RESEARCH_ENABLED`; this PR only stops searches for questions a web search cannot answer.

## 8. Uncertainties

- Bench numbers are synthetic: the turn bench uses the scenario harness with simulated provider delays, and the voice bench uses a virtual clock. They compare versions; they do not predict live latency.
- The name lookup has not run against a real mailbox. Newsletters and forwarded threads may add candidates; the ranking favours people the user has written to.
- An approve tap on an older approval card after a revision approves the latest details, because the latest prompt is what the binding now holds. The latest prompt is always the one shown last.
- A model-written address is dropped only when a name lookup runs. Without a name, it stays visible in the approval prompt for the user to check.
- The per-conversation lock and the write-effects record are per process. Two workers on one conversation are not fenced against each other (finding 14).

## 9. Rollback

Revert the merge commit. No data migration, no schema change, and the one new conversation-state key (`recipient_candidates`) is ignored by the previous code.

## 10. Rollout

1. Merge on Cesar's go. Vercel and Railway deploy from main.
2. Read one voice session's effective flags and settings line.
3. Live checks, chat then voice: "Send an email to <a test contact's first name>", change the subject before approving, approve, and confirm one email with the new subject; "What's 2 plus 2?" and "What time is it?" answer without "searching the web"; Stop mid-email in chat reports truthfully.
