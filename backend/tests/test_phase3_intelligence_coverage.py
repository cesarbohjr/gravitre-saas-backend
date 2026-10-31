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


def write_contract_junit(path, *, omit=None, failed=None, duplicate=False):
    import xml.etree.ElementTree as ET
    from app.operators.agent_prompts import AGENT_PERSONAS
    suite = ET.Element("testsuite")
    for capability in module.CAPABILITIES:
        for surface in module.SURFACES:
            for role in AGENT_PERSONAS:
                for channel in ("text", "voice"):
                    identity = (f"{capability}:{surface}", role, channel)
                    if identity == omit:
                        continue
                    case = ET.SubElement(suite, "testcase", name="fixture-validator-only")
                    props = ET.SubElement(case, "properties")
                    for key, value in {"phase3_cell": identity[0], "phase3_role": role, "phase3_channel": channel, "evidence_scope": "shared_adapter_contract"}.items():
                        ET.SubElement(props, "property", name=key, value=value)
                    if identity == failed:
                        ET.SubElement(case, "skipped")
    if duplicate:
        import copy
        suite.append(copy.deepcopy(suite[0]))
    ET.ElementTree(suite).write(path)


def test_capability_inventory_matches_real_router():
    from app.services.intelligence_router import CAPABILITY_NAMES
    assert tuple(module.CAPABILITIES) == tuple(CAPABILITY_NAMES)


def test_executed_complete_contract_matrix_stays_offline_not_certified(tmp_path):
    junit = tmp_path / "fixture.xml"
    write_contract_junit(junit)
    report = module.apply_junit_contracts(module.build(), junit)
    assert module.validate(report)["offline_pass"] == 56
    assert report["certification"] == "NOT_CERTIFIED"
    assert report["full_product_journeys_verified"] is False


@pytest.mark.parametrize("variant", ["missing", "skipped"])
def test_missing_role_or_skipped_channel_cannot_pass_cell(tmp_path, variant):
    from app.operators.agent_prompts import AGENT_PERSONAS
    identity = ("contextual:flows", next(iter(AGENT_PERSONAS)), "voice")
    junit = tmp_path / "fixture.xml"
    write_contract_junit(junit, omit=identity if variant == "missing" else None, failed=identity if variant == "skipped" else None)
    report = module.apply_junit_contracts(module.build(), junit)
    assert module.validate(report)["offline_pass"] == 55
    assert report["cells"][0]["status"] == ("NOT_TESTED" if variant == "missing" else "FAIL")


def test_duplicate_evidence_cannot_hide_missing_variants(tmp_path):
    junit = tmp_path / "fixture.xml"
    write_contract_junit(junit, duplicate=True)
    with pytest.raises(ValueError, match="duplicated"):
        module.apply_junit_contracts(module.build(), junit)
