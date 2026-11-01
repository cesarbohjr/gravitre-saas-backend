from pathlib import Path
import runpy

gate = runpy.run_path(str(Path(__file__).resolve().parents[2] / "native-workers/adapter_selection_gate.py"))["evaluate"]


def test_microbenchmark_pass_cannot_select_adapter_without_full_comparison():
    result = gate({"microbenchmark_passed": True})
    assert result["selection"] == "RETAIN_BROWSER_USE_COMPARISON_INCOMPLETE"
    assert set(result["comparative_gates"].values()) == {"BLOCKED"}
    assert result["production_certified"] is False


def test_all_evidence_needs_both_adapters_and_sha256():
    names = gate({"microbenchmark_passed": True})["comparative_gates"]
    evidence = {name: {"result": "PASS", "both_adapters": True, "evidence_sha256": "a" * 64} for name in names}
    assert gate({"microbenchmark_passed": True}, evidence)["selection"] == "ELIGIBLE_FOR_HUMAN_REVIEW"
    assert gate({"microbenchmark_passed": False}, evidence)["selection"] != "ELIGIBLE_FOR_HUMAN_REVIEW"
    evidence["gateway_enforcement"]["both_adapters"] = False
    assert gate({"microbenchmark_passed": True}, evidence)["comparative_gates"]["gateway_enforcement"] == "BLOCKED"
