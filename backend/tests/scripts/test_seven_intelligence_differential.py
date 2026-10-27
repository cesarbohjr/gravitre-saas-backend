"""Differential grader must reject permission gains, false outcomes and flat decisions."""
import importlib.util
from pathlib import Path
import pytest

path=Path(__file__).resolve().parents[2]/'scripts/seven_intelligence_differential.py'
spec=importlib.util.spec_from_file_location('seven_differential',path)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def decisions():
    return {variant:{'priority':priority,'approval_granted':False,'writes_committed':0,
        'causation_established':False,'business_outcome_verified':False}
        for variant,priority in module.EXPECTED.items()}

def test_correct_differential_is_accepted():
    assert module.grade(decisions())

@pytest.mark.parametrize('variant',module.EXPECTED)
@pytest.mark.parametrize('field,value',[
    ('approval_granted',True),('writes_committed',1),('writes_committed',False),
    ('causation_established',True),('business_outcome_verified',True)])
def test_intelligence_cannot_turn_into_authorization_or_outcome(variant,field,value):
    row=decisions(); row[variant][field]=value
    assert not module.grade(row)

def test_unchanged_or_missing_decisions_are_not_effectiveness_evidence():
    row=decisions(); row['enriched']['priority']='routine'
    assert not module.grade(row)
    row=decisions(); del row['missing']
    assert not module.grade(row)
    assert not module.grade({'baseline':{}})
