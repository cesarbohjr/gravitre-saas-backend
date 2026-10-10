"""Keeps the offline voice scenario bench from rotting.

Runs every scenario once on the virtual clock (a few seconds of wall time in
total) and checks that the harness still drives the real pipeline end to end:
no harness error, audio reached the modelled browser, metrics and the report
render. It deliberately does NOT assert on outcomes or latencies: those are
what the bench measures, and they change when voice behaviour changes.

The bench modules are imported lazily inside a fixture that restores the
environment and the Settings cache afterwards, so importing them cannot leak
bench defaults into unrelated tests.
"""
from __future__ import annotations

import os
import socket
import time
from typing import Any, Iterator

import pytest

SCENARIO_IDS = ["S1", "S1b", "S2", "S2b", "S3", "S4", "S5", "S6", "S7", "S7b", "S8", "S9", "S10", "S11", "S12"]

_ENV_KEYS = (
    "APP_ENV",
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_JWT_SECRET",
    "OPENAI_API_KEY",
    "AI_MODERATION_ENABLED",
    "GRAVITRE_DROP_BACKGROUND_TASKS",
)


@pytest.fixture(scope="module")
def bench() -> Iterator[dict[str, Any]]:
    saved_env = {key: os.environ.get(key) for key in _ENV_KEYS}
    from app.config import get_settings
    from tests.e2e.voice_scenarios import harness, metrics, scenarios

    settings = harness.build_settings()
    try:
        yield {"harness": harness, "metrics": metrics, "scenarios": scenarios, "settings": settings, "results": {}}
    finally:
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


def test_scenario_list_is_current(bench: dict[str, Any]) -> None:
    assert [s.id for s in bench["scenarios"].ALL_SCENARIOS] == SCENARIO_IDS


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_scenario_runs_once(bench: dict[str, Any], scenario_id: str) -> None:
    real_time, real_connect = time.time, socket.socket.connect
    (scenario,) = bench["scenarios"].get_scenarios([scenario_id])
    result = bench["harness"].run_scenario(scenario, seed=1234, settings=bench["settings"])

    # The virtual clock and the network guard are scoped to the run.
    assert time.time is real_time
    assert socket.socket.connect is real_connect

    assert result.error is None, result.error
    chunks = [c for sock in result.run.sockets for c in sock.browser.chunks]
    assert chunks, "no audio reached the modelled browser"
    assert result.run.rec.brain_calls, "the scripted brain was never called"

    m = bench["metrics"].run_metrics(result)
    assert m["error"] is None
    assert m["first_any_played_ms"] is not None
    assert isinstance(m["outcome"], str) and not m["outcome"].startswith(("outcome_error", "run_error"))
    bench["results"][scenario_id] = m


def test_barge_in_sends_playback_report_when_grounded_history_is_on(bench: dict[str, Any]) -> None:
    """The modelled browser reports the cut reply's playback, as the web hook does."""
    from app.config import get_settings

    key = "VOICE_PLAYBACK_GROUNDED_HISTORY_V1"
    saved = os.environ.get(key)
    try:
        settings = bench["harness"].build_settings({key: "true"})
        (scenario,) = bench["scenarios"].get_scenarios(["S4"])
        result = bench["harness"].run_scenario(scenario, seed=1234, settings=settings)
        assert result.error is None, result.error
        reports = [r for sock in result.run.sockets for _, r in sock.browser.reports_sent]
        assert reports, "no playback.progress report at the barge-in"
        assert all(r["interrupted"] and r["played_ms"] <= r["received_ms"] for r in reports)
        m = bench["metrics"].run_metrics(result)
        assert m["error"] is None
        assert isinstance(m["history_matches_heard"], bool)
    finally:
        if saved is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = saved
        get_settings.cache_clear()
        bench["settings"] = bench["harness"].build_settings()


def test_report_renders(bench: dict[str, Any]) -> None:
    per_scenario = bench["results"]
    if not per_scenario:
        pytest.skip("scenario runs did not execute")
    metrics = bench["metrics"]
    by_id = {s.id: s for s in bench["scenarios"].ALL_SCENARIOS}
    results = {
        "meta": {"label": "pytest", "runs": 1, "seed": 1234, "overrides": {}, "wall_s": 0},
        "model_notes": [],
        "scenarios": {
            sid: {
                "title": by_id[sid].title,
                "description": by_id[sid].description,
                "expected": by_id[sid].expected,
                "notes": by_id[sid].notes,
                "conditions": by_id[sid].conditions().as_dict(),
                "aggregate": metrics.aggregate([m]),
                "runs": [m],
            }
            for sid, m in per_scenario.items()
        },
    }
    report = metrics.markdown_report(results)
    for sid in per_scenario:
        assert f"| {sid} " in report


# --- voice_confirmation_hold_v1 (S8 "yes... wait") ------------------------------
#
# Flux commits the bare "yes" on the pause and the brain used to start the
# approved send before the "wait" was heard. These assert on outcomes (unlike
# the smoke tests above) because they pin a safety fix: the listed seeds sent
# the email before it. A "yes" with no follow-up, or followed only by filler,
# must still send.

# Bench seeds (--seed 7, scenario S8) whose "yes" was committed and sent.
SENT_BEFORE_FIX = [61834, 69753, 77672, 125186, 148943]


def _scenario(bench: dict[str, Any], follow_up: str | None, *, pause_s: float = 0.5) -> Any:
    base = bench["scenarios"].S8ApprovalWait

    class _Variant(base):  # type: ignore[misc, valid-type]
        async def script(self, run: Any) -> None:
            await run.say("draft the follow-up email to Sarah at Acme")
            await run.wait_for(lambda: run.audio_received("answer"), timeout=15)
            await run.wait_for(lambda: run.playback_idle(), timeout=15)
            await run.sleep(0.4)
            if follow_up is None:
                utt = await run.say("yes", mark_start="request_start", mark_end="request_end")
            else:
                utt = await run.say(
                    f"yes {follow_up}",
                    pauses={0: pause_s},
                    commit_on_pause=True,
                    mark_start="request_start",
                    mark_end="request_end",
                )
            run.notes["yes_final_at"] = utt.final_at if follow_up is None else None

    return _Variant()


def _committed(result: Any) -> list[dict[str, Any]]:
    return [w for w in result.run.rec.writes if w["committed"]]


@pytest.mark.parametrize("seed", SENT_BEFORE_FIX)
def test_yes_then_wait_never_sends(bench: dict[str, Any], seed: int) -> None:
    (scenario,) = bench["scenarios"].get_scenarios(["S8"])
    result = bench["harness"].run_scenario(scenario, seed=seed, settings=bench["settings"])
    assert result.error is None, result.error
    assert _committed(result) == [], "the email went out although the user said wait"
    # The "wait" is answered, not dropped.
    assert any("won't send" in (c.full_content or "") for c in result.run.rec.brain_calls)


@pytest.mark.parametrize("seed", [7, 1234, 61834])
def test_yes_then_long_correction_never_sends(bench: dict[str, Any], seed: int) -> None:
    """The correction's words land after the grace window (wordless start held as noise)."""
    scenario = _scenario(bench, "wait change the subject line before you send it")
    result = bench["harness"].run_scenario(scenario, seed=seed, settings=bench["settings"])
    assert result.error is None, result.error
    assert _committed(result) == []
    queries = [c.query for c in result.run.rec.brain_calls]
    assert any("subject line" in q for q in queries), queries


@pytest.mark.parametrize("seed", [7, 1234, 61834, 77672])
def test_bare_yes_still_sends_once(bench: dict[str, Any], seed: int) -> None:
    scenario = _scenario(bench, None)
    result = bench["harness"].run_scenario(scenario, seed=seed, settings=bench["settings"])
    assert result.error is None, result.error
    committed = _committed(result)
    assert len(committed) == 1
    yes_final = result.run.notes["yes_final_at"]
    # Hold (600 ms) + scripted think (0.5 s +/- 25 %) + pre-commit (0.4 s).
    assert committed[0]["t"] - yes_final < 0.6 + 0.625 + 0.4 + 0.1


@pytest.mark.parametrize("seed", [7, 1234])
def test_yes_then_filler_still_sends(bench: dict[str, Any], seed: int) -> None:
    scenario = _scenario(bench, "um")
    result = bench["harness"].run_scenario(scenario, seed=seed, settings=bench["settings"])
    assert result.error is None, result.error
    assert len(_committed(result)) == 1
