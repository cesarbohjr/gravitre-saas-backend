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
