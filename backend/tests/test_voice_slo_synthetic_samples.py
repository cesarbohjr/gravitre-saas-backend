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


# --- live cases: refusal-style (guard-withheld) and interrupt -------------


def test_case_prompts_are_safe_and_the_refusal_style_one_is_flagged() -> None:
    from app.services.ai_guardrails import detect_prompt_injection

    probe.assert_safe_prompts([probe.GUARD_WITHHELD_PROMPT, probe.INTERRUPT_PROMPT])
    assert detect_prompt_injection(probe.GUARD_WITHHELD_PROMPT)[0] is True
    assert detect_prompt_injection(probe.INTERRUPT_PROMPT)[0] is False


def _live(**over) -> dict:
    base = {
        "http_status": 200,
        "safety_gate": None,
        "safety_gate_index": None,
        "early_ack_index": None,
        "early_ack_count": 0,
        "plan_sentence_text_count": 1,
        "plan_sentence_audio_count": 1,
        "interrupt": None,
    }
    base.update(over)
    return base


def test_ack_gate_accepts_flag_off_and_ack_after_allowed_verdict() -> None:
    assert probe.judge_ack_gate(_live()) == []
    after = _live(
        safety_gate={"verdict": "allowed", "early_ack": True},
        safety_gate_index=2,
        early_ack_index=3,
        early_ack_count=1,
    )
    assert probe.judge_ack_gate(after) == []


def test_ack_gate_flags_ack_before_or_without_a_verdict() -> None:
    before = _live(
        safety_gate={"verdict": "allowed"}, safety_gate_index=5, early_ack_index=3, early_ack_count=1
    )
    assert "early acknowledgement before the safety verdict" in probe.judge_ack_gate(before)
    missing = _live(early_ack_index=3, early_ack_count=1)
    assert "early acknowledgement before the safety verdict" in probe.judge_ack_gate(missing)
    refused = _live(
        safety_gate={"verdict": "refused"}, safety_gate_index=1, early_ack_index=3, early_ack_count=1
    )
    assert probe.judge_ack_gate(refused) == ["early acknowledgement after a 'refused' verdict"]


def test_ack_gate_flags_duplicate_speech() -> None:
    problems = probe.judge_ack_gate(_live(plan_sentence_text_count=2, plan_sentence_audio_count=2))
    assert "plan sentence appears twice in the text" in problems
    assert "plan sentence spoken twice" in problems


def test_guard_withheld_case_fails_if_the_ack_came_out() -> None:
    withheld = _live(
        safety_gate={"verdict": "allowed", "early_ack": False, "withheld": "injection_suspected"},
        safety_gate_index=1,
    )
    assert probe.judge_guard_withheld(withheld) == []
    leaked = _live(
        safety_gate={"verdict": "allowed", "early_ack": True},
        safety_gate_index=1,
        early_ack_index=2,
        early_ack_count=1,
    )
    assert "early acknowledgement spoken on a guard-withheld turn" in probe.judge_guard_withheld(leaked)


def test_interrupt_case_requires_observed_cancellation() -> None:
    ok = _live(interrupt={"cancel_sent_ms": 420, "cancel_http_status": 200, "cancel_observed": True})
    assert probe.judge_interrupt(ok) == []
    not_seen = _live(interrupt={"cancel_sent_ms": 420, "cancel_http_status": 200, "cancel_observed": False})
    assert probe.judge_interrupt(not_seen) == ["cancellation not observed in the stream"]
    no_audio = _live(interrupt={"cancel_sent_ms": None})
    assert probe.judge_interrupt(no_audio) == ["no audio arrived, so no barge-in was sent"]
    rejected = _live(interrupt={"cancel_sent_ms": 420, "cancel_http_status": 401, "cancel_observed": False})
    assert probe.judge_interrupt(rejected) == ["cancel endpoint returned 401"]


def test_judge_cases_labels_problems() -> None:
    turns = [_live(), _live(plan_sentence_audio_count=2)]
    cases = {
        "guard_withheld": _live(early_ack_index=1, early_ack_count=1),
        "interrupt": _live(interrupt={"cancel_sent_ms": 1, "cancel_http_status": 200, "cancel_observed": True}),
    }
    gate_problems, case_problems, results = probe.judge_cases(turns, cases)
    assert gate_problems == ["turn 2: plan sentence spoken twice"]
    assert any(p.startswith("guard_withheld: ") for p in case_problems)
    assert results["interrupt"]["problems"] == []
