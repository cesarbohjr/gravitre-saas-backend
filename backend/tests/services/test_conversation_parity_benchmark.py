from app.services.conversation_parity_benchmark import SCENARIOS, lanes, validate_registry
from app.services.conversation_parity_scoring import TrialScore, aggregate, parity_gate


def test_registry_is_valid_and_covers_required_lanes():
    validate_registry()
    assert {"text", "memory", "cross_modal", "voice", "governance", "honesty", "recovery"} <= set(lanes())
    assert len(SCENARIOS) >= 14


def test_prompts_are_behavioral_not_exact_answer_keys():
    for scenario in SCENARIOS:
        assert scenario.invariants
        assert all(len(item) < 80 for item in scenario.invariants)


def test_provider_neutral_aggregate():
    rows = [
        TrialScore("T01", "gravitre", {"continuity": 4, "honesty": 5}, 3, 3),
        TrialScore("T01", "claude", {"continuity": 5, "honesty": 5}, 3, 3),
    ]
    report = aggregate(rows)
    assert report["providers"]["gravitre"]["invariant_rate"] == 1.0
    assert report["providers"]["claude"]["mean_dimension_score"] == 5.0


def test_parity_gate_compares_same_run_quality_instead_of_assumed_vendor_score():
    gravitre = {"invariant_rate": 0.94, "mean_dimension_score": 4.4}
    competitor = {"invariant_rate": 0.98, "mean_dimension_score": 4.7}
    assert parity_gate(gravitre, competitor)
    assert not parity_gate({"invariant_rate": 0.89, "mean_dimension_score": 5.0}, competitor)
