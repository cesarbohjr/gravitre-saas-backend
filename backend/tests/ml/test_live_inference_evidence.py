"""Live evidence must not accept pointer-only, empty or wrong-version results."""
import importlib.util
import json
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("live_inference_evidence",
    Path(__file__).resolve().parents[3]/"scripts/verify-existing-model-inference.py")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)
CASE = {"model_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "version":2, "inputs":[{"feature":1}]}


def test_actual_evidence_refuses_wrong_versions_and_nonfunctional_predictions():
    good = {"model_id":CASE["model_id"],"version":2,"predictions":[0],"latency_ms":1.2}
    evidence.verify_result(good,CASE)
    for change in ({"version":1},{"predictions":[]},{"predictions":[{}]},
                   {"predictions":[float('nan')]},{"latency_ms":-1},{"model_id":"foreign"}):
        with pytest.raises(ValueError):
            evidence.verify_result({**good,**change},CASE)


def test_case_file_is_explicit_bounded_and_deduplicated(tmp_path):
    path = tmp_path/'private.json'
    path.write_text(json.dumps([CASE]))
    assert evidence.validated_cases(path)==[CASE]
    for cases in ([],[CASE,CASE],[{**CASE,'inputs':[{}]}],[{**CASE,'version':True}]):
        path.write_text(json.dumps(cases))
        with pytest.raises(ValueError):
            evidence.validated_cases(path)


def test_health_alone_never_becomes_inference_pass(tmp_path,monkeypatch):
    report = tmp_path/'report.json'
    monkeypatch.setattr('sys.argv',['verify','--expected-sha','a'*40,'--report',str(report)])
    monkeypatch.setattr(evidence,'request',lambda *args,**kwargs:{'status':'ok','git_sha':'a'*40})
    assert evidence.main()==2
    result = json.loads(report.read_text())
    assert result['health']=='pass' and result['inference']=='not_run'
    assert result['provider_execution']=='not_verified'


def test_redirect_does_not_forward_session():
    assert evidence.NoRedirect().redirect_request(None,None,302,'',{},'https://foreign.example') is None
