"""Release-blocking remediation ledger invariants; independent of live providers."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from runpy import run_path

import pytest

ROOT = Path(__file__).resolve().parents[3]
module = run_path(str(ROOT / "backend/scripts/master_qa_remediation_guard.py"), run_name="__remediation_test__")
evaluate = module["evaluate"]
RemediationError = module["RemediationError"]

@pytest.fixture
def data():
    original = json.loads((ROOT / "docs/delivery/master-qa-tranche27-findings-evidence-matrix.json").read_text())
    ledger = json.loads((ROOT / "docs/delivery/master-qa-remediation-register.v2.json").read_text())
    return original, ledger

def test_all_audit_findings_have_source_probes_owner_lane_and_no_false_certification(data):
    original, ledger = data
    outcome = evaluate(ROOT, original=original, register=ledger)
    assert outcome["findings"] == 43
    assert outcome["closure_count"] == 0
    assert outcome["blocked_p0"] > 0
    assert not outcome["release_authorized"]
    assert all(r["qa_lane"] != "UNMAPPED" for r in ledger["records"])
    assert all(not r["retirement_authorized"] for r in ledger["records"])

def test_original_audit_finding_cannot_disappear(data):
    original, ledger = data
    ledger["records"].pop()
    ledger["finding_count"] -= 1
    with pytest.raises(RemediationError, match="finding coverage mismatch"):
        evaluate(ROOT, original=original, register=ledger)

def test_fake_pass_without_exact_sha_and_negative_observation_is_rejected(data):
    original, ledger = data
    r = ledger["records"][0]
    r["fix_verified"] = True
    r["synthetic_status"] = "PASS"
    with pytest.raises(RemediationError, match="PASS without exact implementing SHA"):
        evaluate(ROOT, original=original, register=ledger)

def test_wrong_ci_sha_or_missing_provider_readback_never_certifies(data):
    original, ledger = data
    r = next(x for x in ledger["records"] if x["finding_id"] == "ECO-005")
    r.update({
        "fix_verified": True,
        "implemented_commit": "a" * 40,
        "synthetic_status": "PASS",
        "negative_test_verified": True,
        "downstream_effect_verified": True,
        "source_to_runtime_trace": True,
        "rollback_verified": True,
        "owner_approval": True,
    })
    r["evidence"].update({"ci_run_url": "https://github.com/org/repo/actions/runs/1",
                          "executed_sha": "b" * 40})
    with pytest.raises(RemediationError) as err:
        evaluate(ROOT, original=original, register=ledger)
    assert "same-SHA CI" in str(err.value)
    assert "provider PASS" in str(err.value)

def test_no_premature_legacy_retirement(data):
    original, ledger = data
    r = next(x for x in ledger["records"] if x["finding_id"] == "DEC-002")
    r["retirement_authorized"] = True
    with pytest.raises(RemediationError, match="unsafe retirement authorization"):
        evaluate(ROOT, original=original, register=ledger)

def test_voice_implementation_cannot_be_silently_transferred_from_610(data):
    original, ledger = data
    r = next(x for x in ledger["records"] if x["finding_id"] == "ECO-004")
    r["implementation_owner"] = "PR611-cross-platform"
    with pytest.raises(RemediationError, match="Voice 3.0 implementation belongs"):
        evaluate(ROOT, original=original, register=ledger)

def test_missing_owner_and_source_are_hard_failures(data):
    original, ledger = data
    r = ledger["records"][0]
    r["owner"] = ""
    r["source_probe"]["path"] = "not-a-real-file.py"
    with pytest.raises(RemediationError) as err:
        evaluate(ROOT, original=original, register=ledger)
    assert "missing accountable owner" in str(err.value)
    assert "source probe missing" in str(err.value)

def test_p0_release_cannot_be_green_with_unresolved_finding(data):
    original, ledger = data
    ledger["global_release_authorized"] = True
    with pytest.raises(RemediationError, match="global release authorized with unresolved P0"):
        evaluate(ROOT, original=original, register=ledger)
