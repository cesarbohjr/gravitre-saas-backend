"""No false-positive certification for untested intelligence integrations."""
import importlib.util
from pathlib import Path
import pytest

script = Path(__file__).resolve().parents[1] / "scripts" / "phase3_intelligence_coverage.py"
spec = importlib.util.spec_from_file_location("phase3_coverage", script)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def test_complete_matrix_is_explicitly_uncertified():
    report = module.build()
    assert module.validate(report) == {"total": 56, "not_tested": 56, "offline_pass": 0, "live_verified": 0}
    assert report["certification"] == "NOT_CERTIFIED"

def test_unbacked_pass_is_rejected():
    report = module.build()
    report["cells"][0]["status"] = "PASS_OFFLINE_CONTRACT"
    with pytest.raises(ValueError, match="PASS requires"):
        module.validate(report)

def test_false_live_certification_is_rejected():
    report = module.build()
    report["certification"] = "CERTIFIED"
    with pytest.raises(ValueError, match="Cannot certify"):
        module.validate(report)

def test_duplicate_matrix_cell_is_rejected():
    report = module.build()
    report["cells"][1] = dict(report["cells"][0])
    with pytest.raises(ValueError, match="56 unique"):
        module.validate(report)
