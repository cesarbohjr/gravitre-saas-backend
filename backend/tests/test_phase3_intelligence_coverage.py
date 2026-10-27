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


def write_record(directory, capability='contextual', surface='flows', scenario='customer_support', **changes):
    import json
    row = {'cell_id': f'{capability}:{surface}', 'scenario_id': scenario,
        'status': 'PASS_OFFLINE_CONTRACT', 'commit_sha': 'candidate-sha', 'seed': 1000,
        'test_selector': f'test_boundary[{capability}-{surface}-{scenario}]',
        'expected': 'observed-source', 'observed': 'observed-source',
        'write_attempts': 0, 'writes_committed': 0, 'approval_state': 'not_granted',
        'evidence_scope': 'production_boundary_with_synthetic_external_io', 'provider_readback': None}
    row.update(changes)
    path = directory / f'{capability}-{surface}-{scenario}.json'
    path.write_text(json.dumps(row))
    return path


def test_three_scenarios_required_before_cell_can_pass(tmp_path):
    write_record(tmp_path)
    report = module.build(tmp_path, 'candidate-sha')
    assert report['cells'][0]['status'] == 'NOT_TESTED'
    for scenario in module.SCENARIOS:
        write_record(tmp_path, scenario=scenario)
    report = module.build(tmp_path, 'candidate-sha')
    assert report['cells'][0]['status'] == 'PASS_OFFLINE_CONTRACT'
    assert len(report['cells'][0]['scenario_evidence']) == 3
    assert all(r['sha256'] for r in report['cells'][0]['scenario_evidence'])
    assert report['certification'] == 'NOT_CERTIFIED'


def test_stale_commit_cannot_be_reused(tmp_path):
    write_record(tmp_path)
    with pytest.raises(ValueError, match='Stale'):
        module.build(tmp_path, 'another-sha')


def test_renamed_duplicate_record_cannot_inflate_coverage(tmp_path):
    original = write_record(tmp_path)
    (tmp_path / 'duplicate.json').write_text(original.read_text())
    with pytest.raises(ValueError, match='Duplicate'):
        module.build(tmp_path, 'candidate-sha')


@pytest.mark.parametrize('changes', [
    {'writes_committed': 1, 'write_attempts': 1},
    {'observed': 'unexpected'},
    {'status': 'PASS_LIVE_VERIFIED'},
    {'writes_committed': True},
    {'write_attempts': -1},
])
def test_false_or_unsafe_evidence_is_rejected(tmp_path, changes):
    write_record(tmp_path, **changes)
    with pytest.raises(ValueError):
        module.build(tmp_path, 'candidate-sha')


def test_all_56_executed_offline_cells_are_still_not_live_certification(tmp_path):
    for capability in module.CAPABILITIES:
        for surface in module.SURFACES:
            for scenario in module.SCENARIOS:
                write_record(tmp_path, capability, surface, scenario)
    report = module.build(tmp_path, 'candidate-sha')
    assert module.validate(report) == {'total':56, 'not_tested':0, 'offline_pass':56, 'live_verified':0}
    assert report['certification'] == 'NOT_CERTIFIED'


def test_live_cell_requires_readback_independent_of_provider_acceptance(tmp_path):
    write_record(tmp_path, status='PASS_LIVE_VERIFIED', evidence_scope='live_provider_integration',
        provider_readback={'verified':True,'independent':False,'source_record_id':'record-1','request_id':'read-1'})
    with pytest.raises(ValueError, match='independent provider readback'):
        module.build(tmp_path, 'candidate-sha')
