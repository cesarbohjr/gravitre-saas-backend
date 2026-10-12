"""Voice SLO window check verdicts and the live probe's safety guards."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


check = _load("check_voice_slo_alerts", "check-voice-slo-alerts.py")
probe = _load("verify_voice_slo_two_metric_live", "verify-voice-slo-two-metric-live.py")

SMOKE_ORG = probe.DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID
OPERATOR_ORG = "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea"


def _scope(a: list[int], b: list[int], label: str = "all_orgs", min_samples: int = 3) -> dict:
    return check.summarize(a, b, label=label, min_samples=min_samples)


# --- window check ---------------------------------------------------------


def test_targets_match_voice_slo_standard() -> None:
    from app.services import voice_slo

    assert check.TARGETS == {
        "metric_a": {"p50": voice_slo.METRIC_A_P50_MS, "p95": voice_slo.METRIC_A_P95_MS},
        "metric_b": {"p50": voice_slo.METRIC_B_P50_MS, "p95": voice_slo.METRIC_B_P95_MS},
    }


def test_zero_samples_is_no_data_not_pass() -> None:
    verdict, alerts, short = check.evaluate(_scope([], []))
    assert verdict == "NO_DATA"
    assert alerts == []
    assert short == ["metric_a", "metric_b"]


def test_below_min_samples_in_one_metric_is_no_data() -> None:
    verdict, _, short = check.evaluate(_scope([200, 210, 220], [1500, 1600]))
    assert verdict == "NO_DATA"
    assert short == ["metric_b"]


def test_enough_samples_within_targets_is_pass() -> None:
    verdict, alerts, short = check.evaluate(_scope([200, 250, 300], [1500, 1800, 2400]))
    assert (verdict, alerts, short) == ("PASS", [], [])


def test_breach_is_alert() -> None:
    verdict, alerts, _ = check.evaluate(_scope([600, 700, 900], [1500, 1800, 2400]))
    assert verdict == "ALERT"
    assert "voice_slo_metric_a_p50>500ms" in alerts
    assert "voice_slo_metric_a_p95>800ms" in alerts


def test_breach_with_too_few_samples_does_not_alert() -> None:
    verdict, alerts, _ = check.evaluate(_scope([9000], [90000]))
    assert verdict == "NO_DATA"
    assert alerts == []


def test_scoped_short_is_no_data_even_if_all_orgs_has_samples() -> None:
    all_orgs = _scope([200, 250, 300], [1500, 1800, 2400])
    scoped = _scope([200], [], label=f"org:{SMOKE_ORG}")
    verdict, _, short = check.evaluate(all_orgs, scoped)
    assert verdict == "NO_DATA"
    assert short == ["metric_a", "metric_b"]


def test_scoped_pass_still_alerts_on_all_org_breach() -> None:
    all_orgs = _scope([900, 950, 1000, 200], [1500, 1800, 2400])
    scoped = _scope([200, 250, 300], [1500, 1800, 2400], label=f"org:{SMOKE_ORG}")
    verdict, alerts, _ = check.evaluate(all_orgs, scoped)
    assert verdict == "ALERT"
    assert any(a.startswith("voice_slo_metric_a_") and "[" not in a for a in alerts)


def test_scoped_breach_alerts_and_is_labelled() -> None:
    all_orgs = _scope([200, 250, 300], [1500, 1800, 2400])
    scoped = _scope([200, 250, 300], [9000, 9500, 9900], label=f"org:{SMOKE_ORG}")
    verdict, alerts, _ = check.evaluate(all_orgs, scoped)
    assert verdict == "ALERT"
    assert f"voice_slo_metric_b_p50>5000ms[org:{SMOKE_ORG}]" in alerts


def test_report_reports_all_orgs_and_judged_scope() -> None:
    all_orgs = _scope([200, 250, 300, 260], [1500, 1800, 2400, 2000])
    scoped = _scope([200, 250, 300], [1500, 1800, 2400], label=f"org:{SMOKE_ORG}")
    report = check.build_report(all_orgs, scoped, window_hours=24, min_samples=3)
    assert report["verdict"] == "PASS"
    assert report["judged_scope"] == f"org:{SMOKE_ORG}"
    assert report["metric_a"]["sample_count"] == 3
    assert report["all_orgs"]["metric_a"]["sample_count"] == 4
    assert report["blended_voice_latency"] is None


def test_samples_ms_reads_metadata_and_drops_non_numbers() -> None:
    rows = [
        {"metadata": {"ms": 210}},
        {"metadata": '{"ms": 320.7}'},
        {"metadata": {"ms": None}},
        {"metadata": {"ms": True}},
        {"metadata": "not json"},
        {"metadata": None},
    ]
    assert check.samples_ms(rows) == [210, 320]


# --- live probe guards ----------------------------------------------------


def test_probe_prompts_are_plan_without_execute_and_no_outbound() -> None:
    probe.assert_safe_prompts(probe.OPERATOR_PROMPTS)


@pytest.mark.parametrize(
    "prompt",
    [
        "Create three Google Ads campaigns now.",
        "Email my HubSpot contacts the plan. Don't execute.",
        "Send a message to the team and show the complete plan before you execute anything.",
    ],
)
def test_probe_refuses_unsafe_prompts(prompt: str) -> None:
    with pytest.raises(probe.ConversationWriteBlockedError):
        probe.assert_safe_prompts([prompt])


def test_probe_only_runs_on_isolated_smoke_org() -> None:
    probe.assert_isolated_org(SMOKE_ORG, None, "")
    with pytest.raises(probe.ConversationWriteBlockedError):
        probe.assert_isolated_org(OPERATOR_ORG)
    with pytest.raises(probe.ConversationWriteBlockedError):
        probe.assert_isolated_org(SMOKE_ORG, "11111111-2222-4333-8444-555555555555")


def _turn(**over) -> dict:
    base = {"http_status": 200, "stream_error": None, "voice_error": None, "metric_b_ms": 1800}
    base.update(over)
    return base


def test_samples_generated_requires_every_turn_to_complete() -> None:
    assert probe.samples_generated([_turn(), _turn()]) == (True, [])
    ok, problems = probe.samples_generated([_turn(), _turn(metric_b_ms=None)])
    assert not ok and "no voice.turn.complete" in problems[0]
    assert probe.samples_generated([_turn(http_status=401)])[0] is False
    assert probe.samples_generated([_turn(stream_error="ReadTimeout")])[0] is False
    assert probe.samples_generated([_turn(voice_error="unauthorized")])[0] is False
    assert probe.samples_generated([]) == (False, ["no turns ran"])
