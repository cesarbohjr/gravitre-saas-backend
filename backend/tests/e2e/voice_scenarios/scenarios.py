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

    def conditions(self) -> Conditions:
        return Conditions()

    def planner(self, query: str, history: list[dict[str, Any]], run: Run) -> list[Any]:
        return [Think(run.jit(0.5)), Say("Okay.")]

    async def script(self, run: Run) -> None:
        raise NotImplementedError

    def outcome(self, run: Run, m: dict[str, Any]) -> str:
        return "ok"

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
]


def get_scenarios(ids: list[str] | None = None) -> list[Scenario]:
    if not ids:
        return list(ALL_SCENARIOS)
    wanted = {i.strip().upper() for i in ids}
    return [s for s in ALL_SCENARIOS if s.id.upper() in wanted]
