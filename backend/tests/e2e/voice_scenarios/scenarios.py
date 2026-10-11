"""The scripted conversations. Each scenario = user timeline + brain plan + outcome.

Scripts speak through ``Run.say`` (scripted Flux STT) and wait on what the
modelled browser is playing, so the user reacts to the bot the way a person
would ("start talking 1.2 s into the answer"). Brain plans are keyed on the
query text the production pipeline actually sends to ``execute_task_streaming``.

Where current code has no dedicated behaviour (S10 "keep working", S11
"cancel it"), the scenario still runs and the outcome column records what
actually happened.
"""
from __future__ import annotations

import fnmatch
import re
from typing import Any

from tests.e2e.voice_scenarios.fakes import Say, Think, Tool, norm_words
from tests.e2e.voice_scenarios.harness import Conditions, Run

LONG_TRAFFIC_ANSWER = (
    "Last month the site had twelve thousand four hundred visits. "
    "That is up eight percent on the month before, mostly from organic search. "
    "Paid traffic was flat, and referrals dipped a little after the partner newsletter paused."
)


def _q(query: str) -> str:
    return " ".join(norm_words(query))


def _has(query: str, *needles: str) -> bool:
    q = _q(query)
    return any(re.search(rf"\b{re.escape(n)}\b", q) for n in needles)


def _answering_calls(run: Run) -> list[Any]:
    """Brain calls whose output a confirmed turn consumed (fresh, or adopted speculative)."""
    return [c for c in run.rec.brain_calls if not c.speculative or (c.spec_run or {}).get("adopted")]


def _assistant_texts(run: Run) -> list[str]:
    return [c.full_content for c in run.rec.brain_calls if c.completed and c.full_content]


def _answer_heard_after(run: Run, t: float, label: str = "answer") -> bool:
    for sock in run.sockets:
        for c in sock.browser.chunks:
            if c["label"] == label and c["start"] >= t and c["played_end"] > c["start"]:
                return True
    return False


def _old_reply_kept_playing(run: Run, mark: str, seconds: float) -> bool:
    t = run.marks.get(mark)
    old = run.mark_replies.get(mark, 0)
    if t is None:
        return False
    for c in run.socket.browser.chunks:
        if c["reply_truth"] == old and c["played_end"] > c["start"] and c["start"] >= t + seconds:
            return True
    return False


class Scenario:
    id = "S?"
    title = ""
    description = ""
    expected = ""
    notes = ""
    max_seconds = 60.0
    seed_history: list[tuple[str, str]] = []
    write_allowed_after: str | None = None
    no_write_expected = False
    # Outcomes (fnmatch patterns) that meet ``expected``: the bench's accuracy
    # column. Empty means the scenario does not grade itself.
    pass_outcomes: tuple[str, ...] = ()

    def conditions(self) -> Conditions:
        return Conditions()

    def planner(self, query: str, history: list[dict[str, Any]], run: Run) -> list[Any]:
        return [Think(run.jit(0.5)), Say("Okay.")]

    async def script(self, run: Run) -> None:
        raise NotImplementedError

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        return "ok"

    def passed(self, run: Run, m: dict[str, Any]) -> bool | None:
        """Whether this run met ``expected`` (None: not graded)."""
        if not self.pass_outcomes:
            return None
        outcome = str(m.get("outcome") or "")
        return any(fnmatch.fnmatchcase(outcome, pattern) for pattern in self.pass_outcomes)

    # Shared brain behaviour -------------------------------------------------

    def traffic_plan(self, query: str, run: Run, *, period: str = "month") -> list[Any]:
        answer = LONG_TRAFFIC_ANSWER
        if period == "week":
            answer = "Last week the site had two thousand nine hundred visits, about the same as the week before."
        elif period == "quarter":
            answer = "Last quarter the site had thirty six thousand visits, up eleven percent on the quarter before."
        return [
            Think(run.jit(run.cond.brain_first_token_s)),
            Tool("google_analytics_report", run.jit(1.0)),
            Say(answer, token_s=run.cond.token_s),
        ]

    def short_ack_plan(self, run: Run, text: str = "Okay.") -> list[Any]:
        return [Think(run.jit(0.45)), Say(text, token_s=run.cond.token_s)]


def _period(query: str) -> str | None:
    q = _q(query)
    # The last period named wins ("last week, no, last month").
    hits = [(m.start(), m.group(1)) for m in re.finditer(r"\b(week|month|quarter)\b", q)]
    return hits[-1][1] if hits else None


# ---------------------------------------------------------------------------


class S1LongPause(Scenario):
    id = "S1"
    title = "long pause / incomplete thought"
    description = "User: \"I want to check... [1.2 s pause] ...last month's traffic\". Flux emits EagerEndOfTurn in the pause and TurnResumed when speech resumes (the turn is not committed)."
    expected = "No bot audio during the pause; one answer about last month."

    def planner(self, query: str, history: list[dict[str, Any]], run: Run) -> list[Any]:
        if _has(query, "traffic"):
            return self.traffic_plan(query, run, period=_period(query) or "month")
        return [Think(run.jit(0.7)), Say("Sure, what would you like me to check?", token_s=run.cond.token_s)]

    async def script(self, run: Run) -> None:
        await run.say(
            "I want to check last month's traffic",
            pauses={3: 1.2},
            mark_start="request_start",
            mark_end="request_end",
        )

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        texts = _assistant_texts(run)
        clarify = any("what would you like" in t.lower() for t in texts)
        answered = any("last month" in t.lower() for t in texts)
        if m.get("premature_response"):
            return "spoke_during_pause"
        if clarify and answered:
            return "clarified_then_answered"
        return "answered" if answered else "no_answer"

    def passed(self, run: Run, m: dict[str, Any]) -> bool | None:
        # Graded on what was heard: a clarification the brain produced but
        # nobody heard (a discarded speculative run) is not a failure.
        heard = _spoken_texts(run)
        clarify_heard = any("what would you like" in t for t in heard)
        answer_heard = sum(1 for t in heard if t.startswith("last month the site"))
        return not m.get("premature_response") and not clarify_heard and answer_heard == 1


class S1bLongPauseCommitted(S1LongPause):
    id = "S1b"
    title = "long pause, STT commits early"
    description = "Same words, but Flux commits EndOfTurn on \"I want to check\" during the 1.2 s pause; the rest arrives as a new turn."
    expected = "Ideally no audible reply to the fragment; the full request answered once."

    async def script(self, run: Run) -> None:
        await run.say(
            "I want to check last month's traffic",
            pauses={3: 1.2},
            commit_on_pause=True,
            mark_start="request_start",
            mark_end="request_end",
        )


class S2Backchannel(Scenario):
    id = "S2"
    title = "backchannel during playback"
    backchannel = "Mm-hmm."
    description = "User asks for traffic; 1.5 s into the spoken answer says \"Mm-hmm.\" (0.4 s)."
    expected = "Bot keeps speaking; no new turn; history = full answer."
    pass_outcomes = ("kept_speaking",)

    def planner(self, query: str, history: list[dict[str, Any]], run: Run) -> list[Any]:
        if _has(query, "traffic"):
            return self.traffic_plan(query, run)
        return self.short_ack_plan(run, "Sure.")

    async def script(self, run: Run) -> None:
        await run.say("what was our website traffic last month", mark_start="request_start", mark_end="request_end")
        await run.wait_for(lambda: run.audio_playing("answer"), timeout=15)
        await run.sleep(1.5)
        await run.say(self.backchannel, role="backchannel", mark_start="backchannel_start")

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        stopped = m.get("interrupt_events", 0) > 0
        kept = _old_reply_kept_playing(run, "backchannel_start", 1.0)
        extra_turn = any(_has(c.query, "mm", "hmm", "uh", "huh", "yeah") for c in run.rec.brain_calls)
        if kept and not stopped:
            return "kept_speaking" + ("+answered_backchannel" if extra_turn else "")
        return "bot_interrupted" + ("+answered_backchannel" if extra_turn else "")


class S2bBackchannelYeah(S2Backchannel):
    id = "S2b"
    title = "backchannel \"Yeah.\" (control)"
    backchannel = "Yeah."
    description = "As S2 with \"Yeah.\", a word the utterance gate does not drop."
    expected = "Bot keeps speaking."


class S3CorrectionBeforeSpeech(Scenario):
    id = "S3"
    title = "correction before speech starts"
    description = "User: \"show me traffic for last week, no, last month\" with a 0.35 s hesitation after \"week\"."
    expected = "One answer about last month; nothing about last week is spoken."
    pass_outcomes = ("answered_last_month",)

    def planner(self, query: str, history: list[dict[str, Any]], run: Run) -> list[Any]:
        return self.traffic_plan(query, run, period=_period(query) or "month")

    async def script(self, run: Run) -> None:
        await run.say(
            "show me traffic for last week, no, last month",
            pauses={5: 0.35},
            mark_start="request_start",
            mark_end="request_end",
        )

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        heard = _spoken_texts(run)
        if any("last week" in t for t in heard):
            return "spoke_last_week"
        if any("last month" in t for t in heard):
            return "answered_last_month"
        return "no_answer"


def _spoken_texts(run: Run) -> list[str]:
    """Text of segments that were at least partly played."""
    played = {c["seg"] for s in run.sockets for c in s.browser.chunks if c["played_end"] > c["start"]}
    return [run.rec.segments[s].text.lower() for s in sorted(played) if s in run.rec.segments]


class S4CorrectionAfterSpeech(Scenario):
    id = "S4"
    title = "correction after speech starts (barge-in)"
    description = "User asks for last week's traffic; 1.2 s into the answer barges in: \"use last quarter instead\"."
    expected = "Old answer stops quickly; new answer about last quarter; history holds only what was heard."
    pass_outcomes = ("corrected",)

    def planner(self, query: str, history: list[dict[str, Any]], run: Run) -> list[Any]:
        if _has(query, "quarter"):
            return self.traffic_plan(query, run, period="quarter")
        if _has(query, "traffic"):
            return [
                Think(run.jit(run.cond.brain_first_token_s)),
                Say(
                    "Last week the site had two thousand nine hundred visits. Most came from organic search, "
                    "with a small bump on Tuesday from the product launch email.",
                    token_s=run.cond.token_s,
                ),
            ]
        return self.short_ack_plan(run)

    async def script(self, run: Run) -> None:
        await run.say("what was our website traffic last week")
        await run.wait_for(lambda: run.audio_playing("answer"), timeout=15)
        await run.sleep(1.2)
        await run.say("use last quarter instead", role="barge_in", mark_start="barge_start", mark_end="request_end")

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        if not m.get("interrupted_event"):
            return "not_interrupted"
        heard_after = [t for t in _spoken_texts(run) if "quarter" in t]
        return "corrected" if heard_after else "interrupted_no_new_answer"


class S5RepeatedInterruptions(Scenario):
    id = "S5"
    title = "repeated interruptions then resumed request"
    description = "Pipeline summary request; user cuts in with \"wait\" 1 s into the answer, then \"actually hold on\" while the bot answers that, then \"okay go on, give me the pipeline summary\"."
    expected = "Each cut-in silences the bot; the final request gets the summary once."
    pass_outcomes = ("resumed_answered+*",)

    def planner(self, query: str, history: list[dict[str, Any]], run: Run) -> list[Any]:
        if _has(query, "pipeline", "summary"):
            return [
                Think(run.jit(run.cond.brain_first_token_s)),
                Tool("crm_pipeline_summary", run.jit(0.8)),
                Say(
                    "This week the pipeline is at one point two million across thirty four deals. "
                    "Six moved to proposal and two closed, both in the enterprise segment.",
                    token_s=run.cond.token_s,
                ),
            ]
        return self.short_ack_plan(run, "Sure, take your time.")

    async def script(self, run: Run) -> None:
        await run.say("give me a summary of this week's pipeline")
        await run.wait_for(lambda: run.audio_playing("answer"), timeout=15)
        await run.sleep(1.0)
        await run.say("wait", role="barge_in", mark_start="barge_start")
        await run.sleep(0.6)
        if not await run.wait_for(lambda: run.audio_playing(), timeout=2.5):
            run.notes["second_cut_in_had_nothing_to_cut"] = True
        await run.say("actually hold on", role="barge_in")
        await run.sleep(1.0)
        await run.say("okay go on, give me the pipeline summary", mark_end="request_end")

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        last = run.marks.get("request_end", 0.0)
        summary = _answer_heard_after(run, last)
        n_int = m.get("interrupt_events", 0)
        return f"{'resumed_answered' if summary else 'not_resumed'}+interrupts={n_int}"


class S6LateAudio(S4CorrectionAfterSpeech):
    id = "S6"
    title = "late TTS audio after cancellation"
    description = "As S4, but the TTS provider keeps emitting the cancelled context's audio for 300 ms after close."
    expected = "No frame of the cancelled reply is played after the interruption."
    pass_outcomes = ("late_audio_contained",)

    def conditions(self) -> Conditions:
        return Conditions(late_audio_s=0.3)

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        played = m.get("late_frames_played", 0) + m.get("misstamped_frames", 0)
        return "late_audio_played" if played else "late_audio_contained"


class S7SlowTool(Scenario):
    id = "S7"
    title = "slow tool (4 s)"
    description = "\"pull the pipeline report for this quarter\": one CRM tool call taking 4 s."
    expected = "Progress narration covers the wait; answer after the tool."
    pass_outcomes = ("answered*",)

    def planner(self, query: str, history: list[dict[str, Any]], run: Run) -> list[Any]:
        return [
            Think(run.jit(run.cond.brain_first_token_s)),
            Tool("crm_pipeline_report", run.jit(4.0, )),
            Say("The quarter's pipeline is one point eight million, with forty two open deals.", token_s=run.cond.token_s),
        ]

    async def script(self, run: Run) -> None:
        await run.say("pull the pipeline report for this quarter", mark_start="request_start", mark_end="request_end")

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        labels = [run.rec.segments[s].text for s in run.rec.segments if run.rec.segments[s].label == "progress"]
        still = any(t.lower().startswith("still") for t in labels)
        return "answered" + ("+still_running_notice" if still else "")


class S7bFailedTool(Scenario):
    id = "S7b"
    title = "failed tool"
    description = "\"what was our website traffic last month\": the analytics tool fails after 1.5 s."
    expected = "Failure narrated honestly; no invented numbers."
    pass_outcomes = ("failure_narrated", "failure_in_answer_only")

    def planner(self, query: str, history: list[dict[str, Any]], run: Run) -> list[Any]:
        return [
            Think(run.jit(run.cond.brain_first_token_s)),
            Tool("google_analytics_report", run.jit(1.5), fail=True),
            Say("I couldn't reach Google Analytics just now. Want me to try again in a minute?", token_s=run.cond.token_s),
        ]

    async def script(self, run: Run) -> None:
        await run.say("what was our website traffic last month", mark_start="request_start", mark_end="request_end")

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        progress = [run.rec.segments[s].text.lower() for s in run.rec.segments if run.rec.segments[s].label == "progress"]
        failure_narrated = any("couldn't" in t for t in progress)
        return "failure_narrated" if failure_narrated else "failure_in_answer_only"


class S8ApprovalWait(Scenario):
    id = "S8"
    title = "approval \"yes... wait\""
    description = "Bot drafts an email and asks to send; user says \"yes\", pauses ~0.5 s, says \"wait\". Flux may commit \"yes\" on the pause."
    expected = "No email is sent (the final intent is \"wait\")."
    pass_outcomes = ("no_send_attempted", "send_blocked_by_gate")
    no_write_expected = True

    def planner(self, query: str, history: list[dict[str, Any]], run: Run) -> list[Any]:
        q = _q(query)
        if _has(query, "wait", "hold", "stop", "don't"):
            return self.short_ack_plan(run, "Okay, I won't send it.")
        if q.startswith("yes") or q.startswith("go ahead"):
            return [
                Think(run.jit(0.5)),
                Tool("send_email", run.jit(1.2), write_action="gmail.send", pre_commit_s=0.4),
                Say("Done, it's on its way to Sarah.", token_s=run.cond.token_s),
            ]
        if _has(query, "email", "send"):
            return [
                Think(run.jit(run.cond.brain_first_token_s)),
                Say("I've drafted the follow-up to Sarah at Acme. Want me to send it now?", token_s=run.cond.token_s),
            ]
        return self.short_ack_plan(run)

    async def script(self, run: Run) -> None:
        await run.say("draft the follow-up email to Sarah at Acme")
        await run.wait_for(lambda: run.audio_received("answer"), timeout=15)
        await run.wait_for(lambda: run.playback_idle(), timeout=15)
        await run.sleep(0.4)
        await run.say("yes wait", pauses={0: 0.5}, commit_on_pause=True, mark_start="request_start", mark_end="request_end")

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        if m.get("writes_committed"):
            return "email_sent"
        if m.get("writes_blocked"):
            return "send_blocked_by_gate"
        return "no_send_attempted"


class S9DeepReasoning(Scenario):
    id = "S9"
    title = "complex reasoning turn (deep tier)"
    description = "Multi-part analysis request; brain thinks 2.5 s, runs two tools (1.5 s, 1.0 s), thinks 1.5 s, then answers."
    expected = "Early acknowledgement and progress narration; answer when ready."
    pass_outcomes = ("*answer*",)

    def planner(self, query: str, history: list[dict[str, Any]], run: Run) -> list[Any]:
        return [
            Think(run.jit(2.5)),
            Tool("analytics_conversion_report", run.jit(1.5)),
            Tool("crm_search_deals", run.jit(1.0)),
            Think(run.jit(1.5)),
            Say(
                "Conversion fell from three point one to two point four percent, almost all of it in paid social. "
                "Organic and email held steady. I'd pause the two weakest ad sets and move that budget to email nurture.",
                token_s=run.cond.token_s,
            ),
        ]

    async def script(self, run: Run) -> None:
        await run.say(
            "analyze why our conversion rate dropped last quarter and compare it across channels, then recommend a plan",
            mark_start="request_start",
            mark_end="request_end",
        )

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        labels = {run.rec.segments[s].label for s in run.rec.segments}
        return "+".join(sorted(labels)) or "silent"


class _RunningTask(Scenario):
    """A long task is running and narrating; the user says something to it."""

    utterance = ""
    task_query = "pull the pipeline report for this quarter"
    tool_s = 6.0

    def planner(self, query: str, history: list[dict[str, Any]], run: Run) -> list[Any]:
        if _has(query, "pipeline", "report") and not _has(query, "stop", "cancel", "keep"):
            return [
                Think(run.jit(run.cond.brain_first_token_s)),
                Tool("crm_pipeline_report", run.jit(self.tool_s)),
                Say("The quarter's pipeline is one point eight million, with forty two open deals.", token_s=run.cond.token_s),
            ]
        if _has(query, "keep"):
            return self.short_ack_plan(run, "Okay, I'll keep working on it quietly.")
        return self.short_ack_plan(run, "Okay, I've cancelled it.")

    async def script(self, run: Run) -> None:
        await run.say(self.task_query, mark_start="request_start", mark_end="request_end")
        await run.wait_for(lambda: run.audio_playing("progress"), timeout=15)
        await run.sleep(0.5)
        await run.say(self.utterance, role="barge_in", mark_start="barge_start")

    def _task_state(self, run: Run) -> str:
        task_calls = [c for c in _answering_calls(run) if _has(c.query, "pipeline", "report")]
        if any(c.completed for c in task_calls):
            report_heard = any("forty two open deals" in t for t in _spoken_texts(run))
            return "task_completed" + ("+report_spoken" if report_heard else "+report_not_spoken")
        return "task_cancelled"


class S10StopTalkingKeepWorking(_RunningTask):
    id = "S10"
    title = "\"stop talking, keep working\""
    utterance = "stop talking, keep working"
    description = "During a 6 s CRM task, while progress narration plays, the user says \"stop talking, keep working\"."
    expected = "Ideal: narration stops, the task keeps running and its result is delivered. (No dedicated path in current code.)"
    pass_outcomes = ("task_completed+report_spoken*",)

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        answered = any(_has(c.query, "keep") for c in run.rec.brain_calls)
        return self._task_state(run) + ("+answered_as_turn" if answered else "")


class S11CancelIt(_RunningTask):
    id = "S11"
    title = "\"cancel it\" during a running task"
    utterance = "cancel it"
    task_query = "yes, go ahead and move them all"
    tool_s = 5.0
    commit_after_s = 4.0
    no_write_expected = True
    seed_history = [
        ("user", "which Acme deals are still open"),
        ("assistant", "Twelve Acme deals are open. Want me to move all twelve to closed won?"),
    ]
    description = (
        "An approved CRM batch write is running (user: \"yes, go ahead and move them all\"; the provider call is made "
        "4 s into a 5 s tool call). 0.5 s into the progress narration the user says \"cancel it\"."
    )
    expected = "The task stops and the write is not committed. (Cancellation rides on barge-in + stop marker.)"
    pass_outcomes = ("task_cancelled", "task_cancelled+write_blocked*", "task_cancelled+answered_as_turn")

    def planner(self, query: str, history: list[dict[str, Any]], run: Run) -> list[Any]:
        if _has(query, "go ahead", "move") and not _has(query, "cancel"):
            return [
                Think(run.jit(run.cond.brain_first_token_s)),
                Tool("update_deal_stages", self.tool_s, write_action="hubspot.deals.update", pre_commit_s=self.commit_after_s),
                Say("Done, all twelve Acme deals are now closed won.", token_s=run.cond.token_s),
            ]
        return self.short_ack_plan(run, "Okay, I've cancelled it.")

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        task_calls = [c for c in _answering_calls(run) if _has(c.query, "go ahead", "move")]
        state = "task_completed" if any(c.completed for c in task_calls) else "task_cancelled"
        if m.get("writes_committed"):
            state += "+write_committed"
        elif m.get("writes_blocked"):
            state += "+write_blocked"
        answered = any(_has(c.query, "cancel") for c in run.rec.brain_calls)
        return state + ("+answered_as_turn" if answered else "")


class S12Reconnect(Scenario):
    id = "S12"
    title = "reconnect mid-reply (socket drop)"
    description = "1.5 s into the spoken traffic answer the socket drops; 1 s later a new socket opens on the same conversation and the user asks what was said last."
    expected = "Durable history (and the brain's view of it after reconnect) holds only what was heard."
    pass_outcomes = ("brain_saw_partial_reply*",)

    def planner(self, query: str, history: list[dict[str, Any]], run: Run) -> list[Any]:
        if _has(query, "traffic") and not _has(query, "cut"):
            return self.traffic_plan(query, run)
        return self.short_ack_plan(run, "I was going over last month's traffic numbers.")

    async def script(self, run: Run) -> None:
        await run.say("what was our website traffic last month", mark_start="request_start", mark_end="request_end")
        await run.wait_for(lambda: run.audio_playing("answer"), timeout=15)
        await run.sleep(1.5)
        run.mark("drop")
        await run.drop_socket()
        await run.sleep(1.0)
        await run.open_socket()
        await run.sleep(0.3)
        await run.say("sorry I got cut off, what were you saying")

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        follow = [c for c in run.rec.brain_calls if _has(c.query, "cut")]
        if not follow:
            return "no_followup_turn"
        prior = " ".join(str(h.get("content") or "") for h in follow[-1].history if h.get("role") == "assistant").lower()
        if "referrals dipped" in prior:
            return "brain_saw_full_unheard_reply"
        if "twelve thousand" in prior or "last month the site" in prior:
            # With voice_playback_grounded_history_v1 the heard part is stored
            # with a cut marker telling the model the rest was not heard.
            return "brain_saw_partial_reply_marked" if "[interrupted:" in prior else "brain_saw_partial_reply"
        return "brain_saw_no_reply"


# ---------------------------------------------------------------------------
# Flag interactions (production flag combination: interrupt intents, explain
# aside, answer-first, playback-grounded history, overlap ducking). Each runs
# under any profile; ``pass_outcomes`` encode the product's intended
# behaviour, so a profile without the flag shows what the flag buys.

PIPELINE_RESULT = "The quarter's pipeline is one point eight million, with forty two open deals."
WHY_ASIDE_ANSWER = (
    "It's pulling every open deal for the quarter from the CRM, and that report is slow. "
    "It should be done in a few seconds."
)
VISITS_EXPLANATION = "Visits counts every session on the site, so that is the total number of sessions, not people."


def _played_segments(run: Run) -> list[tuple[float, Any]]:
    """(first played time, segment) for every segment that was at least partly played, in play order."""
    first: dict[int, float] = {}
    for sock in run.sockets:
        for c in sock.browser.chunks:
            if c["played_end"] > c["start"]:
                first[c["seg"]] = min(first.get(c["seg"], c["start"]), c["start"])
    return [(t, run.rec.segments[s]) for s, t in sorted(first.items(), key=lambda kv: kv[1]) if s in run.rec.segments]


def _first_duck_after(run: Run, mark: str) -> dict[str, Any] | None:
    t = run.marks.get(mark)
    if t is None:
        return None
    ducks = sorted((d for s in run.sockets for d in s.browser.ducks if d["start"] >= t), key=lambda d: d["start"])
    return ducks[0] if ducks else None


def _assistant_history(call: Any) -> list[str]:
    return [str(h.get("content") or "").lower() for h in call.history if h.get("role") == "assistant"]


class S13ExplainDuringTask(Scenario):
    id = "S13"
    title = "\"why?\" during a running task (answer-first)"
    question = "why?"
    tool_s = 6.0
    description = (
        "\"pull the pipeline report for this quarter\" runs a 6 s CRM tool; 0.5 s into the first narration line "
        "(or 2.5 s after the request if nothing narrates) the user asks a bare \"why?\". Interacts with "
        "voice_interrupt_intents_v1 + voice_explain_aside_v1 + voice_answer_first_v1."
    )
    expected = (
        "The question is answered while the task keeps running; the task's result is then spoken exactly once, "
        "and no narration line plays after the result starts."
    )
    pass_outcomes = ("explained+result_spoken_once",)

    def planner(self, query: str, history: list[dict[str, Any]], run: Run) -> list[Any]:
        if _has(query, "why"):
            return [Think(run.jit(0.6)), Say(WHY_ASIDE_ANSWER, token_s=run.cond.token_s)]
        if _has(query, "pipeline", "report"):
            return [
                Think(run.jit(run.cond.brain_first_token_s)),
                Tool("crm_pipeline_report", run.jit(self.tool_s)),
                Say(PIPELINE_RESULT, token_s=run.cond.token_s),
            ]
        if _has(query, "how many"):
            return self.short_ack_plan(run, "Forty two open deals.")
        return self.short_ack_plan(run)

    async def script(self, run: Run) -> None:
        await run.say("pull the pipeline report for this quarter", mark_start="task_start", mark_end="task_end")
        if await run.wait_for(lambda: run.audio_playing(), timeout=2.5):
            await run.sleep(0.5)
        else:
            run.notes["nothing_playing_at_question"] = True
        await run.say(self.question, role="barge_in", mark_start="barge_start", mark_end="request_end")

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        played = _played_segments(run)
        explained = any("pulling every open deal" in seg.text.lower() for _t, seg in played)
        result_times = [t for t, seg in played if "forty two open deals" in seg.text.lower()]
        task_calls = [c for c in _answering_calls(run) if _has(c.query, "pipeline", "report") and not _has(c.query, "why")]
        parts = ["explained" if explained else "not_explained"]
        if not any(c.completed for c in task_calls):
            parts.append("task_cancelled")
        elif not result_times:
            parts.append("result_not_spoken")
        elif len(result_times) == 1:
            parts.append("result_spoken_once")
        else:
            parts.append(f"result_spoken_x{len(result_times)}")
        if result_times and any(seg.label in ("filler", "progress") and t > result_times[0] for t, seg in played):
            parts.append("narration_after_result")
        return "+".join(parts)


class S13bExplainDuringTaskPhrased(S13ExplainDuringTask):
    id = "S13b"
    title = "\"why is it taking so long\" during a running task"
    question = "why is it taking so long"
    description = "As S13, with a question the interrupt-intent classifier reads as an explanation request."


class S14ExplainAsideHistory(S13ExplainDuringTask):
    id = "S14"
    title = "explain aside + playback-grounded history"
    question = "why is it taking so long"
    description = (
        "As S13b; after everything is quiet the user asks \"okay, and how many open deals was that\". Checks what "
        "history stores (voice_playback_grounded_history_v1): the follow-up's brain history and the durable rows."
    )
    expected = (
        "History holds the aside and the task's result, both as heard and in the order heard; nothing unheard "
        "is stored; the follow-up sees both."
    )
    pass_outcomes = ("history_ok",)

    async def script(self, run: Run) -> None:
        await super().script(run)
        await run.settle(quiet_s=1.0, max_s=20.0)
        await run.say("okay, and how many open deals was that")

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        follow = [c for c in _answering_calls(run) if _has(c.query, "how many")]
        if not follow:
            return "no_followup_turn"
        prior = _assistant_history(follow[-1])
        aside_idx = [i for i, t in enumerate(prior) if "pulling every open deal" in t]
        result_idx = [i for i, t in enumerate(prior) if "forty two open deals" in t]
        problems = []
        if not aside_idx:
            problems.append("aside_missing")
        if not result_idx:
            problems.append("result_missing")
        elif len(result_idx) > 1:
            problems.append("result_stored_twice")
        if aside_idx and result_idx and aside_idx[0] > result_idx[0]:
            problems.append("order_differs_from_heard")
        users = [str(h.get("content") or "").lower() for h in follow[-1].history if h.get("role") == "user"]
        request_at = [i for i, t in enumerate(users) if "pipeline report" in t]
        question_at = [i for i, t in enumerate(users) if "why" in t]
        if request_at and question_at and request_at[0] > question_at[0]:
            # The task was asked first; history should say so.
            problems.append("request_stored_after_aside")
        if m.get("persisted_unheard_words"):
            problems.append("unheard_stored")
        if m.get("heard_unpersisted_words"):
            problems.append("heard_not_stored")
        run.notes["followup_assistant_history"] = [t[:160] for t in prior]
        return "+".join(problems) or "history_ok"


class S15ExplainCutAnswer(Scenario):
    id = "S15"
    title = "explain request cuts the answer (grounded history)"
    description = (
        "1.5 s into the spoken traffic answer the user asks \"wait, what does that mean\" (no task running: the "
        "explanation interrupts the answer). Interacts with voice_interrupt_intents_v1 + "
        "voice_playback_grounded_history_v1."
    )
    expected = (
        "The answer stops; the explanation is spoken; the explanation's brain history and the stored answer hold "
        "only what was heard."
    )
    pass_outcomes = ("explained+brain_saw_heard_only*+history_eq_heard",)

    def planner(self, query: str, history: list[dict[str, Any]], run: Run) -> list[Any]:
        if _has(query, "mean"):
            return [Think(run.jit(0.6)), Say(VISITS_EXPLANATION, token_s=run.cond.token_s)]
        if _has(query, "traffic"):
            return self.traffic_plan(query, run)
        return self.short_ack_plan(run)

    async def script(self, run: Run) -> None:
        await run.say("what was our website traffic last month", mark_start="task_start", mark_end="task_end")
        await run.wait_for(lambda: run.audio_playing("answer"), timeout=15)
        await run.sleep(1.5)
        await run.say("wait, what does that mean", role="barge_in", mark_start="barge_start", mark_end="request_end")

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        if not m.get("interrupted_event"):
            return "not_interrupted"
        played = _played_segments(run)
        parts = ["explained" if any("every session" in seg.text.lower() for _t, seg in played) else "not_explained"]
        calls = [c for c in _answering_calls(run) if _has(c.query, "mean")]
        if calls:
            prior = " ".join(_assistant_history(calls[-1]))
            if "referrals dipped" in prior:
                parts.append("brain_saw_unheard")
            elif "last month the site" in prior:
                parts.append("brain_saw_heard_only" + ("_marked" if "[interrupted:" in prior else ""))
            else:
                parts.append("brain_saw_no_answer")
        else:
            parts.append("no_explain_call")
        parts.append("history_eq_heard" if m.get("history_matches_heard") else "history_ne_heard")
        return "+".join(parts)


class S16BareStop(Scenario):
    id = "S16"
    title = "bare \"stop\" over the answer (ducking)"
    description = (
        "1.5 s into the spoken traffic answer the user says \"stop\". Interacts with voice_interrupt_intents_v1 "
        "(a bare stop is a full stop) + voice_overlap_duck_v1 (duck while the words are classified)."
    )
    expected = "The answer is cut and stays cut: never restored to full level, not restarted; at most a short acknowledgement."
    pass_outcomes = ("stopped", "stopped+ducked", "stopped+ack_spoken", "stopped+ducked+ack_spoken")

    def planner(self, query: str, history: list[dict[str, Any]], run: Run) -> list[Any]:
        if _has(query, "traffic"):
            return self.traffic_plan(query, run)
        return self.short_ack_plan(run, "Okay.")

    async def script(self, run: Run) -> None:
        await run.say("what was our website traffic last month", mark_start="task_start", mark_end="task_end")
        await run.wait_for(lambda: run.audio_playing("answer"), timeout=15)
        await run.sleep(1.5)
        await run.say("stop", role="barge_in", mark_start="barge_start", mark_end="request_end")

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        if not m.get("interrupted_event"):
            return "not_stopped"
        t = run.marks["barge_start"]
        old = run.mark_replies.get("barge_start", 0)
        parts = ["stopped"]
        duck = _first_duck_after(run, "barge_start")
        if duck is not None:
            parts.append("ducked")
            if duck["end_reason"] == "unduck":
                parts.append("restored_before_cut")
        after = [seg for st, seg in _played_segments(run) if st > t and seg.reply_truth > old]
        if any("last month the site" in seg.text.lower() for seg in after):
            parts.append("answer_restarted")
        elif sum(len(norm_words(seg.text)) for seg in after if seg.label == "answer") > 3:
            parts.append("new_reply_spoken")
        elif after:
            parts.append("ack_spoken")
        return "+".join(parts)


class S17BackchannelDucked(S2Backchannel):
    id = "S17"
    title = "backchannel \"Right, okay.\" (ducking)"
    backchannel = "Right, okay."
    description = (
        "As S2 with a two-word backchannel. Interacts with voice_interrupt_intents_v1 (BACKCHANNEL keeps the reply) "
        "+ voice_overlap_duck_v1 (duck while classifying, then unduck)."
    )
    expected = "Bot keeps speaking; if it ducked, the reply is restored (unduck); no new turn."
    pass_outcomes = ("kept_speaking", "kept_speaking+duck_restored")

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        base = super().outcome(run, m)
        duck = _first_duck_after(run, "backchannel_start")
        if duck is None:
            return base
        return base + ("+duck_restored" if duck["end_reason"] == "unduck" else f"+duck_ended_{duck['end_reason']}")


class S18CorrectionDucked(Scenario):
    id = "S18"
    title = "correction while ducked (\"no, I meant last month\")"
    description = (
        "User asks for last week's traffic; 1.2 s into the answer says \"no, I meant last month\". Interacts with "
        "voice_interrupt_intents_v1 (CORRECTION revises the request) + voice_overlap_duck_v1."
    )
    expected = "The old answer is cut (never restored to full level); the new answer is about last month; nothing about last week after the cut."
    pass_outcomes = ("corrected",)

    def planner(self, query: str, history: list[dict[str, Any]], run: Run) -> list[Any]:
        period = _period(query)
        if period == "week":
            return [
                Think(run.jit(run.cond.brain_first_token_s)),
                Say(
                    "Last week the site had two thousand nine hundred visits. Most came from organic search, "
                    "with a small bump on Tuesday from the product launch email.",
                    token_s=run.cond.token_s,
                ),
            ]
        if period:
            return self.traffic_plan(query, run, period=period)
        return self.short_ack_plan(run)

    async def script(self, run: Run) -> None:
        await run.say("what was our website traffic last week")
        await run.wait_for(lambda: run.audio_playing("answer"), timeout=15)
        await run.sleep(1.2)
        await run.say("no, I meant last month", role="barge_in", mark_start="barge_start", mark_end="request_end")

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        if not m.get("interrupted_event"):
            return "not_interrupted"
        t = run.marks["barge_start"]
        old = run.mark_replies.get("barge_start", 0)
        after = [seg for st, seg in _played_segments(run) if st > t and seg.reply_truth > old]
        parts = ["corrected" if any("last month the site" in seg.text.lower() for seg in after) else "no_new_answer"]
        if any("last week" in seg.text.lower() for seg in after):
            parts.append("spoke_last_week_after_cut")
        duck = _first_duck_after(run, "barge_start")
        if duck is not None and duck["end_reason"] == "unduck":
            parts.append("restored_before_cut")
        return "+".join(parts)


ALL_SCENARIOS: list[Scenario] = [
    S1LongPause(),
    S1bLongPauseCommitted(),
    S2Backchannel(),
    S2bBackchannelYeah(),
    S3CorrectionBeforeSpeech(),
    S4CorrectionAfterSpeech(),
    S5RepeatedInterruptions(),
    S6LateAudio(),
    S7SlowTool(),
    S7bFailedTool(),
    S8ApprovalWait(),
    S9DeepReasoning(),
    S10StopTalkingKeepWorking(),
    S11CancelIt(),
    S12Reconnect(),
    S13ExplainDuringTask(),
    S13bExplainDuringTaskPhrased(),
    S14ExplainAsideHistory(),
    S15ExplainCutAnswer(),
    S16BareStop(),
    S17BackchannelDucked(),
    S18CorrectionDucked(),
]


def get_scenarios(ids: list[str] | None = None) -> list[Scenario]:
    if not ids:
        return list(ALL_SCENARIOS)
    wanted = {i.strip().upper() for i in ids}
    return [s for s in ALL_SCENARIOS if s.id.upper() in wanted]
