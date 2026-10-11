"""Per-run metrics and per-scenario aggregation (P50/P95) for the voice bench.

Conventions (all times in milliseconds from a scenario mark):

- "played" is the modelled browser speaker (jitter lead, reply-id drops,
  flush on ``speech.interrupted``); "sent" is arrival at the client socket.
- A reply "answers" a mark when its ``reply_truth`` (the server's
  ``VoicePipelineSession.reply_id`` when the text reached the TTS) is greater
  than the reply id at the mark.
- Audio labels: ``filler`` = deep-turn acknowledgement, ``progress`` = tool
  narration (start / still running / completed), ``answer`` = everything else
  the brain streamed.
"""
from __future__ import annotations

import difflib
import math
from collections import Counter
from typing import Any

from app.services.pipecat_voice.voice_reply_playback import (
    NOTHING_HEARD_MARKER,
    TRUNCATION_MARKER,
)
from tests.e2e.voice_scenarios.fakes import BrowserPlaybackModel, norm_words


def _stored_words(content: str) -> list[str]:
    """Words of a stored assistant message, without the cut markers
    (voice_playback_grounded_history_v1), which are notes to the model, not speech."""
    for marker in (TRUNCATION_MARKER, NOTHING_HEARD_MARKER):
        content = content.replace(marker, " ")
    return norm_words(content)


def _ms(value: float | None) -> float | None:
    return None if value is None else round(value * 1000.0, 1)


def _all_chunks(run: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for sock in run.sockets:
        kept.extend(dict(c, socket=sock.index) for c in sock.browser.chunks)
        dropped.extend(dict(c, socket=sock.index) for c in sock.browser.dropped)
    return kept, dropped


def _messages(run: Any) -> list[tuple[float, dict[str, Any]]]:
    out: list[tuple[float, dict[str, Any]]] = []
    for sock in run.sockets:
        out.extend(sock.browser.messages)
    out.sort(key=lambda item: item[0])
    return out


def _heard_words(run: Any, chunks: list[dict[str, Any]], labels: set[str]) -> list[str]:
    """Words of each segment in proportion to how much of its audio was played.

    A word counts as heard only once all of its audio has played (whole words,
    rounded down). The server stores heard text by the same rule
    (voice_reply_playback.ReplyPlayback.char_offset_for_played_ms), so the
    history = heard column compares like with like.
    """
    played_s: dict[int, float] = {}
    first_play: dict[int, float] = {}
    for c in chunks:
        dur = max(0.0, c["played_end"] - c["start"])
        if dur <= 0:
            continue
        played_s[c["seg"]] = played_s.get(c["seg"], 0.0) + dur
        first_play[c["seg"]] = min(first_play.get(c["seg"], c["start"]), c["start"])
    words: list[str] = []
    for seg_id in sorted(first_play, key=lambda s: first_play[s]):
        seg = run.rec.segments.get(seg_id)
        if seg is None or seg.label not in labels:
            continue
        seg_words = norm_words(seg.text)
        total = seg.words * run.cond.tts_word_audio_s
        frac = 1.0 if total <= 0 else min(1.0, played_s[seg_id] / total + 1e-6)
        words.extend(seg_words[: int(math.floor(frac * len(seg_words) + 1e-6))])
    return words


def _duplicate_lines(run: Any, chunks: list[dict[str, Any]]) -> int:
    """Segments (two words or more) played whose words repeat an earlier played segment's."""
    seen: set[tuple[str, ...]] = set()
    dupes = 0
    order: dict[int, float] = {}
    for c in chunks:
        if c["played_end"] > c["start"]:
            order[c["seg"]] = min(order.get(c["seg"], c["start"]), c["start"])
    for seg_id in sorted(order, key=lambda s: order[s]):
        seg = run.rec.segments.get(seg_id)
        key = tuple(norm_words(seg.text)) if seg is not None else ()
        if len(key) < 2:
            continue
        if key in seen:
            dupes += 1
        seen.add(key)
    return dupes


def _matched(a: list[str], b: list[str]) -> int:
    return sum(block.size for block in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_matching_blocks())


def _duck_metrics(run: Any, played: list[dict[str, Any]], m: dict[str, Any]) -> None:
    """voice_overlap_duck_v1. Keys are added only when the server sent a duck,
    so runs without the flag produce exactly the metrics they always did.

    - barge_to_ducked_ms: from the overlap's start (barge_start, or
      backchannel_start) until the old reply is no longer heard at full level:
      the duck's gain ramp has finished, or its audio has stopped, whichever is
      first.
    - ducked_ms: how long that duck lasted (until unduck, interrupt or a newer
      reply).
    - duck_restored: the duck ended with speech.unduck (the reply went on).
    """
    ducks = [d for sock in run.sockets for d in sock.browser.ducks]
    if not ducks:
        return
    name = "barge_start" if "barge_start" in run.marks else "backchannel_start"
    t0 = run.marks.get(name)
    if t0 is None:
        return
    old = run.mark_replies.get(name, 0)
    after = sorted((d for d in ducks if d["start"] >= t0), key=lambda d: d["start"])
    old_played = [
        c["played_end"] for c in played
        if c["reply_truth"] is not None and c["reply_truth"] <= old and c["played_end"] > t0
    ]
    candidates = [max(old_played) if old_played else t0]
    if after:
        candidates.append(after[0]["start"] + BrowserPlaybackModel.DUCK_RAMP_S)
    m["barge_to_ducked_ms"] = _ms(min(candidates) - t0)
    if after:
        duck = after[0]
        end = duck["end"] if duck["end"] is not None else run.now
        m["ducked_ms"] = _ms(end - duck["start"])
        m["duck_restored"] = duck["end_reason"] == "unduck"


def run_metrics(result: Any) -> dict[str, Any]:
    run = result.run
    scenario = run.scenario
    kept, dropped = _all_chunks(run)
    played = [c for c in kept if c["played_end"] > c["start"]]
    msgs = _messages(run)
    m: dict[str, Any] = {"seed": result.seed, "error": result.error}

    end = run.marks.get("request_end")
    end_reply = run.mark_replies.get("request_end", 0)
    if end is not None:
        mine = [c for c in played if (c["reply_truth"] or 0) > end_reply]
        sent = [c for c in kept + dropped if (c["reply_truth"] or 0) > end_reply]

        def first(chs: list[dict[str, Any]], labels: set[str], key: str) -> float | None:
            ts = [c[key] for c in chs if c["label"] in labels]
            return (min(ts) - end) if ts else None

        m["first_any_played_ms"] = _ms(first(mine, {"filler", "progress", "answer"}, "start"))
        m["first_filler_played_ms"] = _ms(first(mine, {"filler", "progress"}, "start"))
        m["first_answer_played_ms"] = _ms(first(mine, {"answer"}, "start"))
        m["first_answer_sent_ms"] = _ms(first(sent, {"answer"}, "recv"))
        # Total talk time from the measured request on (played audio), and
        # the part of it that was acknowledgement / tool narration.
        m["talk_ms"] = _ms(sum(c["played_end"] - c["start"] for c in mine))
        m["non_answer_talk_ms"] = _ms(
            sum(c["played_end"] - c["start"] for c in mine if c["label"] in ("filler", "progress"))
        )
        completes = [t for t, msg in msgs if msg.get("type") == "assistant_turn.complete" and t >= end]
        m["completion_ms"] = _ms((max(completes) - end) if completes else None)
        # Filler / progress talk heard before the first answer audio (all of
        # it when no answer was heard): the wait the user sat through.
        answer_starts = [c["start"] for c in mine if c["label"] == "answer"]
        first_answer = min(answer_starts) if answer_starts else None
        m["filler_before_answer_ms"] = _ms(
            sum(
                min(c["played_end"], first_answer if first_answer is not None else c["played_end"]) - c["start"]
                for c in mine
                if c["label"] in ("filler", "progress") and (first_answer is None or c["start"] < first_answer)
            )
        )
        # Voice-quality proxies for the measured response, answer kept apart
        # from filler: words heard of each, and lines heard more than once.
        m["answer_words_heard"] = len(_heard_words(run, mine, {"answer"}))
        m["filler_words_heard"] = len(_heard_words(run, mine, {"filler", "progress"}))
        m["duplicate_lines"] = _duplicate_lines(run, mine)

    barge = run.marks.get("barge_start")
    if barge is not None:
        old = run.mark_replies.get("barge_start", 0)
        old_all = [c for c in kept + dropped if c["reply_truth"] is not None and c["reply_truth"] <= old]
        old_sent_after = [c["recv"] for c in old_all if c["recv"] >= barge]
        old_played_after = [c["played_end"] for c in played if c["reply_truth"] is not None and c["reply_truth"] <= old and c["played_end"] > barge]
        m["interrupt_to_last_sent_ms"] = _ms((max(old_sent_after) - barge) if old_sent_after else 0.0)
        m["interrupt_to_silence_ms"] = _ms((max(old_played_after) - barge) if old_played_after else 0.0)
        interrupts = [t for t, msg in msgs if msg.get("type") == "speech.interrupted" and t >= barge]
        m["interrupted_event"] = bool(interrupts)
        if interrupts:
            t_int = interrupts[0]
            late = [c for c in old_all if c["recv"] > t_int]
            m["late_frames_received"] = len(late)
            m["late_frames_played"] = sum(1 for c in late if c in kept and c["played_end"] > c["start"])
        else:
            m["late_frames_received"] = 0
            m["late_frames_played"] = 0
    _duck_metrics(run, played, m)
    # Barge-in to "no longer heard at full level": the duck when there was
    # one, otherwise the full stop.
    if "barge_to_ducked_ms" in m and barge is not None:
        m["barge_to_quiet_ms"] = m["barge_to_ducked_ms"]
    elif "interrupt_to_silence_ms" in m:
        m["barge_to_quiet_ms"] = m["interrupt_to_silence_ms"]
    # Frames stamped with a newer reply id than the reply they belong to: the
    # browser's reply-id drop cannot catch these.
    m["misstamped_frames"] = sum(
        1 for c in kept + dropped if isinstance(c["reply_stamp"], int) and c["reply_truth"] is not None and c["reply_stamp"] > c["reply_truth"]
    )
    m["provider_frames_after_close"] = run.rec.provider_chunks_after_close
    m["provider_frames_after_close_accepted"] = run.rec.provider_chunks_after_close_accepted

    req_start = run.marks.get("request_start")
    if req_start is not None and end is not None:
        start_reply = run.mark_replies.get("request_start", 0)
        over = [
            c for c in played
            if (c["reply_truth"] or 0) > start_reply and c["start"] < end and c["played_end"] > req_start
        ]
        m["premature_response"] = bool(over)
        m["premature_audio_ms"] = _ms(sum(min(c["played_end"], end) - c["start"] for c in over))

    allowed_after = getattr(scenario, "write_allowed_after", None)
    forbidden = 0
    for w in run.rec.writes:
        if not w["committed"]:
            continue
        if getattr(scenario, "no_write_expected", False):
            forbidden += 1
        elif allowed_after and (allowed_after not in run.marks or w["t"] < run.marks[allowed_after]):
            forbidden += 1
        elif w["speculative"]:
            forbidden += 1
    m["premature_actions"] = forbidden
    m["writes_committed"] = sum(1 for w in run.rec.writes if w["committed"])
    m["writes_blocked"] = sum(1 for w in run.rec.writes if not w["committed"])

    rows = run.db.tables.get("conversation_messages", [])[run.seed_rows :]
    persisted = [w for row in rows if row.get("role") == "assistant" for w in _stored_words(str(row.get("content") or ""))]
    heard_all = _heard_words(run, kept, {"filler", "progress", "answer"})
    heard_answer = _heard_words(run, kept, {"answer"})
    unheard_persisted = len(persisted) - _matched(persisted, heard_all)
    heard_unpersisted = len(heard_answer) - _matched(heard_answer, persisted)
    m["persisted_unheard_words"] = unheard_persisted
    m["heard_unpersisted_words"] = heard_unpersisted
    m["history_matches_heard"] = unheard_persisted == 0 and heard_unpersisted == 0
    # Answer words heard that the transcript never displayed (the client
    # shows every assistant_text delta, narration included): speech the user
    # cannot read back.
    displayed = norm_words(
        "".join(str(msg.get("delta") or "") for _t, msg in msgs if msg.get("type") == "assistant_text")
    )
    m["spoken_not_displayed_words"] = len(heard_answer) - _matched(heard_answer, displayed)

    runs = run.rec.spec_runs
    adopted = [r for r in runs if r.get("adopted")]
    wasted = 0.0
    for r in runs:
        call = r.get("call")
        if r.get("adopted") or call is None:
            continue
        wasted += (call.ended_at if call.ended_at is not None else run.now) - call.started_at
    m["spec_started"] = len(runs)
    m["spec_adopted"] = len(adopted)
    m["spec_discarded"] = len(runs) - len(adopted)
    m["spec_wasted_brain_s"] = round(wasted, 3)
    m["brain_calls"] = len(run.rec.brain_calls)
    # Brain work that kept running after a barge-in interrupted the turn it
    # served (e.g. an adopted speculative run that nothing cancels).
    t_ints = [t for t, msg in msgs if msg.get("type") == "speech.interrupted"]
    after_s = 0.0
    orphans = 0
    for call in run.rec.brain_calls:
        end_t = call.ended_at if call.ended_at is not None else run.now
        hits = [t for t in t_ints if call.started_at < t < end_t]
        if hits:
            after_s += end_t - hits[0]
            if call.completed and end_t - hits[0] > 0.05:
                orphans += 1
    m["brain_s_after_interrupt"] = round(after_s, 3)
    m["brain_calls_completed_after_interrupt"] = orphans
    m["interrupt_events"] = sum(1 for _t, msg in msgs if msg.get("type") == "speech.interrupted")
    try:
        m["outcome"] = scenario.outcome(run, m)
    except Exception as exc:  # noqa: BLE001
        m["outcome"] = f"outcome_error:{exc.__class__.__name__}"
    if result.error:
        m["outcome"] = "run_error"
    # Accuracy: did the run meet the scenario's expected outcome (None: ungraded).
    grade = getattr(scenario, "passed", None)
    if not callable(grade):
        m["passed"] = None
    elif result.error:
        m["passed"] = False
    else:
        try:
            m["passed"] = grade(run, m)
        except Exception:  # noqa: BLE001 - a grading bug counts as a failure
            m["passed"] = False
    m["virtual_s"] = round(run.now, 3)
    m["stuck_thread_jumps"] = run.clock.stuck_thread_jumps
    if run.notes:
        m["notes"] = dict(run.notes)
    return m


TIMING_KEYS = (
    "first_any_played_ms",
    "first_filler_played_ms",
    "first_answer_played_ms",
    "first_answer_sent_ms",
    "talk_ms",
    "non_answer_talk_ms",
    "filler_before_answer_ms",
    "completion_ms",
    "interrupt_to_last_sent_ms",
    "interrupt_to_silence_ms",
    "barge_to_quiet_ms",
    "premature_audio_ms",
)
COUNT_KEYS = (
    "late_frames_received",
    "late_frames_played",
    "misstamped_frames",
    "provider_frames_after_close",
    "provider_frames_after_close_accepted",
    "premature_actions",
    "writes_committed",
    "writes_blocked",
    "persisted_unheard_words",
    "heard_unpersisted_words",
    "spec_started",
    "spec_adopted",
    "spec_discarded",
    "spec_wasted_brain_s",
    "brain_calls",
    "brain_s_after_interrupt",
    "brain_calls_completed_after_interrupt",
    "interrupt_events",
    "answer_words_heard",
    "filler_words_heard",
    "duplicate_lines",
    "spoken_not_displayed_words",
)
BOOL_KEYS = ("premature_response", "history_matches_heard", "interrupted_event")
# voice_overlap_duck_v1: aggregated only when some run has them.
DUCK_TIMING_KEYS = ("barge_to_ducked_ms", "ducked_ms")
DUCK_BOOL_KEYS = ("duck_restored",)


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return round(vals[lo] + (vals[hi] - vals[lo]) * (pos - lo), 1)


def aggregate(per_run: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {"runs": len(per_run), "errors": sum(1 for r in per_run if r.get("error"))}
    for key in TIMING_KEYS:
        vals = [r[key] for r in per_run if isinstance(r.get(key), (int, float))]
        out[key] = {"n": len(vals), "p50": percentile(vals, 0.5), "p95": percentile(vals, 0.95)}
    for key in COUNT_KEYS:
        vals = [r[key] for r in per_run if isinstance(r.get(key), (int, float))]
        out[key] = {"n": len(vals), "total": round(sum(vals), 3), "mean": round(sum(vals) / len(vals), 3) if vals else None}
    for key in BOOL_KEYS:
        vals = [bool(r[key]) for r in per_run if key in r]
        out[key] = {"n": len(vals), "true": sum(vals), "rate": round(sum(vals) / len(vals), 3) if vals else None}
    for key in DUCK_TIMING_KEYS:
        vals = [r[key] for r in per_run if isinstance(r.get(key), (int, float))]
        if vals:
            out[key] = {"n": len(vals), "p50": percentile(vals, 0.5), "p95": percentile(vals, 0.95)}
    for key in DUCK_BOOL_KEYS:
        vals = [bool(r[key]) for r in per_run if key in r]
        if vals:
            out[key] = {"n": len(vals), "true": sum(vals), "rate": round(sum(vals) / len(vals), 3)}
    graded = [bool(r["passed"]) for r in per_run if r.get("passed") is not None]
    out["accuracy"] = {
        "n": len(graded),
        "pass": sum(graded),
        "rate": round(sum(graded) / len(graded), 3) if graded else None,
    }
    out["outcomes"] = dict(Counter(str(r.get("outcome")) for r in per_run))
    return out


def _cell(stat: dict[str, Any]) -> str:
    if not stat or not stat.get("n"):
        return "–"
    return f"{_fmt(stat['p50'])} / {_fmt(stat['p95'])} (n={stat['n']})"


def _fmt(v: Any) -> str:
    if v is None:
        return "–"
    return f"{int(round(v))}"


def _rate(stat: dict[str, Any]) -> str:
    if not stat or not stat.get("n"):
        return "–"
    return f"{stat['true']}/{stat['n']}"


def _mean(stat: dict[str, Any]) -> str:
    if not stat or not stat.get("n") or stat.get("mean") is None:
        return "–"
    return f"{stat['mean']:.1f}"


def _total(stat: dict[str, Any]) -> str:
    if not stat or not stat.get("n"):
        return "–"
    return f"{stat['total']:g}"


def _accuracy(stat: dict[str, Any] | None) -> str:
    if not stat or not stat.get("n"):
        return "–"
    return f"{stat['pass']}/{stat['n']}"


def _profile_lines(meta: dict[str, Any]) -> list[str]:
    profile = meta.get("profile") or {}
    if not profile and not meta.get("effective_flags"):
        return []
    lines = ["## Conditions", ""]
    if profile:
        lines.append(f"- Profile: **{profile.get('name')}** ({profile.get('status') or 'no status'}). {profile.get('source') or ''}".rstrip())
        if profile.get("verify_with"):
            lines.append(f"- Verify with: {profile['verify_with']}")
    cleared = meta.get("cleared_env") or []
    if cleared:
        lines.append(f"- VOICE_* variables cleared from the calling shell: {', '.join(cleared)}")
    flags = meta.get("effective_flags") or {}
    if flags:
        on = sorted(k for k, v in flags.items() if v)
        lines.append(f"- Voice flags on as resolved by Settings ({len(on)}): {', '.join(on) or 'none'}")
    settings = meta.get("effective_settings") or {}
    if settings:
        lines.append("- Voice settings: " + ", ".join(f"{k}={v}" for k, v in settings.items()))
    if meta.get("app_tree"):
        lines.append(f"- backend/app tree: {meta['app_tree']} (identical tree hash = identical product code)")
    lines.append(
        f"- Runs per scenario: {meta.get('runs')}; seed base {meta.get('seed')}; "
        "per-run seeds are listed in results.json; per-scenario delay conditions are listed at the end."
    )
    return lines + [""]


def _headline_lines(results: dict[str, Any]) -> list[str]:
    scenarios = results["scenarios"]
    graded = [sc["aggregate"].get("accuracy") or {} for sc in scenarios.values()]
    n = sum(g.get("n", 0) for g in graded)
    ok = sum(g.get("pass", 0) for g in graded)
    lines = [
        "## Headline",
        "",
        f"Accuracy over all graded runs: **{ok}/{n}**"
        + (f" ({ok / n:.0%})" if n else "")
        + ". A run passes when its outcome meets the scenario's expected outcome (see Scenario conditions).",
        "",
        (
            "First useful audible response = first ANSWER audio played (never filler or progress narration). "
            "Barge-in → quiet = speech onset of the barge-in until the old reply is ducked or, without a duck, "
            "stopped; barge-in → silence = until it stops. Quality columns are means per run (duplicate lines and "
            "words spoken but not displayed are totals); answer words and filler words are counted separately."
        ),
        "",
        "| Scenario | accuracy | first useful audible (answer) | first audio (any) | filler heard before answer | barge-in → quiet (duck or stop) | barge-in → silence | completion | answer words heard | filler words heard | duplicate lines | spoken, not displayed (words) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for sid, sc in scenarios.items():
        a = sc["aggregate"]
        lines.append(
            f"| {sid} {sc['title']} | {_accuracy(a.get('accuracy'))} | {_cell(a.get('first_answer_played_ms', {}))} | "
            f"{_cell(a.get('first_any_played_ms', {}))} | {_cell(a.get('filler_before_answer_ms', {}))} | "
            f"{_cell(a.get('barge_to_quiet_ms', {}))} | {_cell(a.get('interrupt_to_silence_ms', {}))} | "
            f"{_cell(a.get('completion_ms', {}))} | {_mean(a.get('answer_words_heard', {}))} | "
            f"{_mean(a.get('filler_words_heard', {}))} | {_total(a.get('duplicate_lines', {}))} | "
            f"{_total(a.get('spoken_not_displayed_words', {}))} |"
        )
    failing = {
        sid: sc["aggregate"]["outcomes"]
        for sid, sc in scenarios.items()
        if (sc["aggregate"].get("accuracy") or {}).get("n") and sc["aggregate"]["accuracy"]["pass"] < sc["aggregate"]["accuracy"]["n"]
    }
    if failing:
        lines += ["", "Scenarios with failing runs (outcome: count):", ""]
        for sid, outcomes in failing.items():
            lines.append(f"- **{sid}**: " + ", ".join(f"{k} {v}" for k, v in sorted(outcomes.items(), key=lambda kv: -kv[1])))
    return lines + [""]


def markdown_report(results: dict[str, Any]) -> str:
    meta = results["meta"]
    lines = [
        f"# Voice scenario bench: {meta.get('label') or 'unlabelled'}",
        "",
        f"Runs per scenario: {meta['runs']} · seed base: {meta['seed']} · git: {meta.get('git') or 'unknown'} · "
        f"wall time: {meta.get('wall_s')} s · settings overrides: {meta.get('overrides') or 'none'}",
        "",
        "Times are milliseconds, shown as P50 / P95 (n = runs where the event happened). "
        "\"played\" is the modelled browser speaker; \"sent\" is arrival at the client socket. "
        "First-audio and completion are measured from the user's acoustic end of speech of the measured request.",
        "",
    ]
    lines += _profile_lines(meta)
    lines += _headline_lines(results)
    lines += [
        "## Latency",
        "",
        "| Scenario | first audio (any) | first filler/progress | first answer (played) | first answer (sent) | talk time (filler/progress part) | task completion |",
        "|---|---|---|---|---|---|---|",
    ]
    for sid, sc in results["scenarios"].items():
        a = sc["aggregate"]
        lines.append(
            f"| {sid} {sc['title']} | {_cell(a['first_any_played_ms'])} | {_cell(a['first_filler_played_ms'])} | "
            f"{_cell(a['first_answer_played_ms'])} | {_cell(a['first_answer_sent_ms'])} | "
            f"{_cell(a['talk_ms'])} ({_cell(a['non_answer_talk_ms'])}) | {_cell(a['completion_ms'])} |"
        )
    lines += [
        "",
        "## Interruption, correctness and speculation",
        "",
        "| Scenario | barge-in → last old frame sent | barge-in → silence (played) | late old frames recv / played | mis-stamped frames | premature response | premature actions | history = heard | brain s after interrupt (orphan runs) | spec started / adopted / wasted s | outcome |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for sid, sc in results["scenarios"].items():
        a = sc["aggregate"]
        late = (
            f"{a['late_frames_received']['total']} / {a['late_frames_played']['total']}"
            if a["late_frames_received"]["n"]
            else "–"
        )
        spec = f"{a['spec_started']['total']} / {a['spec_adopted']['total']} / {a['spec_wasted_brain_s']['total']}"
        outcomes = ", ".join(f"{k} {v}" for k, v in sorted(a["outcomes"].items(), key=lambda kv: -kv[1]))
        orphan = f"{a['brain_s_after_interrupt']['total']} ({a['brain_calls_completed_after_interrupt']['total']})"
        lines.append(
            f"| {sid} | {_cell(a['interrupt_to_last_sent_ms'])} | {_cell(a['interrupt_to_silence_ms'])} | {late} | "
            f"{a['misstamped_frames']['total']} | {_rate(a['premature_response'])} | {a['premature_actions']['total']} | "
            f"{_rate(a['history_matches_heard'])} | {orphan} | {spec} | {outcomes} |"
        )
    ducked = {sid: sc for sid, sc in results["scenarios"].items() if "barge_to_ducked_ms" in sc["aggregate"]}
    if ducked:
        lines += [
            "",
            "## Overlap ducking (voice_overlap_duck_v1)",
            "",
            "\"ducked (played)\" is the time from the overlap's start until the old reply is no longer heard at full "
            "level: the duck ramp has finished, or its audio has stopped, whichever comes first. Ducked audio still "
            "counts as heard.",
            "",
            "| Scenario | barge-in → ducked (played) | barge-in → silence (played) | ducked for | duck restored | outcome |",
            "|---|---|---|---|---|---|",
        ]
        for sid, sc in ducked.items():
            a = sc["aggregate"]
            outcomes = ", ".join(f"{k} {v}" for k, v in sorted(a["outcomes"].items(), key=lambda kv: -kv[1]))
            lines.append(
                f"| {sid} | {_cell(a['barge_to_ducked_ms'])} | {_cell(a['interrupt_to_silence_ms'])} | "
                f"{_cell(a.get('ducked_ms', {}))} | {_rate(a.get('duck_restored', {}))} | {outcomes} |"
            )
    lines += ["", "## Scenario conditions", ""]
    for sid, sc in results["scenarios"].items():
        cond = ", ".join(f"{k}={v}" for k, v in sc["conditions"].items())
        passes = sc.get("pass_outcomes")
        graded = f" Passes when the outcome is: {', '.join(passes)}." if passes else (" Graded by the scenario's own rule." if sc.get("graded") else "")
        lines.append(
            f"- **{sid} {sc['title']}**: {sc['description']} Expected: {sc['expected']}{graded} "
            f"Conditions: {cond}. {sc.get('notes') or ''}".rstrip()
        )
    lines += ["", "## What the harness models, and what it does not", ""]
    lines += [f"- {line}" for line in results.get("model_notes", [])]
    return "\n".join(lines) + "\n"
