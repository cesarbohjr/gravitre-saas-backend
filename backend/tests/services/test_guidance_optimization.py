"""Fixed baseline, measured promotion gates, shared activation and rollback."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import pytest
from app.services.guidance_optimization import active_guidance, digest, validate_candidate
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location("guidance_optimizer",ROOT/"scripts/guidance_optimization/optimize.py")
opt=importlib.util.module_from_spec(spec); spec.loader.exec_module(opt)

def candidate():
    payload={"schema":1,"data_scope":"fixed_synthetic_only","optimizer":"DSPy.LabeledFewShot","dspy_version":"3.2.1","corpus_sha256":opt.CORPUS_SHA256,"demos":[{k:opt.corpus()["train"][0][k] for k in ("user","assistant")}]}
    return {**payload,"version":"dspy-"+digest(payload)[:16]}

def report(c):
    rows=[]
    for split in ("validation","holdout"):
        for case in opt.corpus()[split]:
            for channel in ("text","voice"):
                for version in ("native-v1",c["version"]):
                    rows.append({"version":version,"case_id":case["id"],"split":split,"channel":channel,"score":int(version!="native-v1"),"security_violation":False,"response_sha256":"a"*64})
    return {"evidence_mode":"provider","corpus_sha256":opt.CORPUS_SHA256,"candidate_sha256":digest(c),"selected":c["version"],"generation_model":"test-provenance","judge_model":"test-provenance","rows":rows}

def test_release_and_rollback_change_shared_guidance(tmp_path,monkeypatch):
    from app.services import guidance_optimization as guidance
    from app.services.conversational_behavior import conversational_behavior_section
    monkeypatch.setattr(guidance,"active_guidance",lambda:active_guidance(tmp_path))
    (tmp_path/"active.json").write_text('{"active":"native-v1"}')
    baseline=conversational_behavior_section(); c=candidate()
    opt.release(tmp_path,expected="native-v1",candidate=c,report=report(c),reviewer="engineering-review")
    assert c["demos"][0]["assistant"] in conversational_behavior_section()
    with pytest.raises(ValueError,match="stale"):
        opt.release(tmp_path,expected="native-v1",candidate=c,report=report(c),reviewer="review")
    opt.release(tmp_path,expected=c["version"],candidate=None,report=None,reviewer="review")
    assert conversational_behavior_section()==baseline

@pytest.mark.parametrize("mutation",[
    lambda r:r.update(evidence_mode="fixture"),lambda r:r.update(corpus_sha256="b"*64),
    lambda r:r.update(candidate_sha256="b"*64),lambda r:r["rows"].pop(),
    lambda r:r["rows"].append(deepcopy(r["rows"][0])),lambda r:r["rows"][1].update(security_violation=True),
    lambda r:r["rows"][1].update(score=-1),lambda r:r.update(generation_model=""),
    lambda r:[row.update(score=1) for row in r["rows"]],lambda r:r["rows"][1].update(score=0),
])
def test_invalid_missing_or_non_improving_evidence_cannot_promote(tmp_path,mutation):
    c=candidate(); r=report(c); r["rows"][0]["score"]=1; mutation(r)
    assert not opt.eligible(r,c)
    (tmp_path/"active.json").write_text('{"active":"native-v1"}')
    with pytest.raises(ValueError,match="evaluation_gate"):
        opt.release(tmp_path,expected="native-v1",candidate=c,report=r,reviewer="review")
    assert active_guidance(tmp_path)==""

def test_tampered_unknown_and_path_traversal_guidance_fail_closed(tmp_path):
    for version in ("../secrets","unknown","dspy-"+"a"*16):
        (tmp_path/"active.json").write_text(json.dumps({"schema":1,"active":version}))
        assert active_guidance(tmp_path)==""
    c=candidate(); validate_candidate(c); c["demos"][0]["assistant"]="changed"
    with pytest.raises(ValueError,match="hash"):
        validate_candidate(c)

def test_original_baseline_and_new_sealed_corpus_are_untouched():
    import sys
    sys.path.insert(0,str(ROOT/"scripts/social_intelligence"))
    from build_bundle import CASES
    assert digest(CASES)=="a41ab1f73ebeff9cc857b1513e0ae5c437b8b25da5d79ee8925f4fba9676c68b"
    data=opt.corpus()
    assert len(data["train"])==6 and len(data["holdout"])==4
    assert {r["user"] for r in data["train"]}.isdisjoint({r["user"] for r in data["validation"]+data["holdout"]})

@pytest.mark.parametrize("spoken",[False,True],ids=["text","voice"])
def test_actual_classical_and_unified_prompt_builders_follow_release_and_rollback(tmp_path,monkeypatch,mock_settings,spoken):
    from app.services import guidance_optimization as guidance
    from app.operators.agent_intelligence import AgentIntelligence
    from app.services.module_d_unified_voice_spec import build_module_d_unified_system_prompt
    monkeypatch.setattr(guidance,"active_guidance",lambda:active_guidance(tmp_path))
    (tmp_path/"active.json").write_text('{"active":"native-v1"}')
    engine=object.__new__(AgentIntelligence);engine.settings=mock_settings
    agent={"id":"synthetic-agent","role":"MARKETING","name":"Marketing Analyst"}
    def prompts():
        return [engine._build_system_prompt("agent",agent,[],"",spoken_mode=spoken,spoken_settings=mock_settings),
                build_module_d_unified_system_prompt(agent=agent,spoken_mode=spoken)]
    assert all("Reviewed conversational examples" not in p for p in prompts())
    c=candidate();opt.release(tmp_path,expected="native-v1",candidate=c,report=report(c),reviewer="review")
    assert all("Reviewed conversational examples" in p and c["demos"][0]["assistant"] in p for p in prompts())
    opt.release(tmp_path,expected=c["version"],candidate=None,report=None,reviewer="review")
    assert all("Reviewed conversational examples" not in p for p in prompts())


def test_unknown_dependency_advisories_are_not_silently_accepted():
    spec=importlib.util.spec_from_file_location("guidance_audit",ROOT/"scripts/guidance_optimization/audit.py")
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    finding={"dependencies":[{"name":"diskcache","version":"5.6.3","vulns":[{"id":"PYSEC-2026-2447"}]}]}
    assert audit.unexpected(finding)==[]
    finding["dependencies"][0]["vulns"].append({"id":"NEW-ADVISORY"})
    assert audit.unexpected(finding)==[("diskcache","5.6.3","NEW-ADVISORY")]
