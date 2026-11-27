import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/"scripts"))
import voice3_pipecat_probe as m

def event(reply, at, context):
    return {"reply":reply,"at":at,"context":context,"rate":24000,"channels":1,"bytes":960}

def test_candidate_ids_exact_sha_and_unique():
    manifest={"source_sha":"head","activation_authorized":False,"mapping":[{"candidate_id":"A"*20}]}
    assert m.candidate_ids(manifest,"head")==["A"*20]
    with pytest.raises(ValueError):
        m.candidate_ids(manifest,"other")
    with pytest.raises(ValueError):
        m.candidate_ids({**manifest,"mapping":manifest["mapping"]*2},"head")

def test_pcm_accounting_and_recovery():
    events=[event(1,1.1,"old"),event(2,2.2,"new")]
    r=m.summarize(events,1,1.5,2,True)
    assert r["sink_status"]=="PASS"
    assert r["first_audio_ms"]==100
    assert r["recovery_first_audio_ms"]==200
    assert r["recovery_pcm_frames"]==480

@pytest.mark.parametrize("extra",[event(1,1.6,"old"),event(None,2.3,"unknown")])
def test_stale_or_unattributed_audio_fails(extra):
    r=m.summarize([event(1,1.1,"old"),extra,event(2,2.2,"new")],1,1.5,2,True)
    assert r["sink_status"]=="FAIL"
    assert r["stale_pcm_frames"]==480

def test_reused_context_or_missing_stop_fails():
    events=[event(1,1.1,"old"),event(2,2.2,"old")]
    assert m.summarize(events,1,1.5,2,True)["sink_status"]=="FAIL"
    assert m.summarize([events[0],event(2,2.2,"new")],1,1.5,2,False)["sink_status"]=="FAIL"


def good_row(voice="A"*20,model=m.MODEL):
    return dict(voice_id=voice,model=model,fixture_version=m.FIXTURE_VERSION,status="PASS",
                sink_status="PASS",error_count=0,active_context_at_cut=True,cancel_hook_reported=True,
                cancel_context_matches=True,cancel_session_kept=True,recovery_all_contexts_stopped=True,
                recovery_end_observed=True,recovery_wer=0,first_audio_ms=100,recovery_first_audio_ms=120,cancel_hook_ms=10)

@pytest.mark.parametrize("field",["cancel_hook_reported","cancel_context_matches","cancel_session_kept","recovery_all_contexts_stopped","recovery_end_observed"])
def test_cancellation_and_completion_evidence_mandatory(field):
    assert m.evaluate_status({**good_row(),field:False})=="FAIL"

def test_recovery_transcript_must_be_complete():
    assert m.evaluate_status(good_row())=="PASS"
    assert m.evaluate_status({**good_row(),"recovery_wer":.1})=="FAIL"
    assert m.evaluate_status({**good_row(),"recovery_wer":None})=="NOT RUN"

def test_latency_comparison_not_certification():
    result=m.compare_latency(good_row(),{**good_row(),"first_audio_ms":150})
    assert result["delta_ms"]["first_audio_ms"]==50
    assert result["performance_gate"]=="NOT RUN"

def test_consolidation_rejects_stale_and_incomplete_evidence():
    from voice3_certification import consolidate
    voice="A"*20
    proposal={"source_sha":"head","activation_authorized":False,"mapping":[{"preset":"a","candidate_id":voice}]}
    probe={"source_sha":"head","activation_authorized":False,"model":m.MODEL,"fixture_version":m.FIXTURE_VERSION,
           "rows":[{"voice_id":voice,"status":"PASS","flash_trials":[{**good_row(voice,m.FLASH),"trial":i} for i in range(m.TRIALS)],"dialogue_trials":[{**good_row(),"trial":i} for i in range(m.TRIALS)]}]}
    result=consolidate(proposal,probe,"head")
    assert result["rows"][0]["gates"]["interruption"]=="NOT RUN"
    assert result["status"]=="BLOCKED"
    assert not result["certifiable_ids"]
    with pytest.raises(ValueError):
        consolidate(proposal,{**probe,"source_sha":"old"},"head")
    with pytest.raises(ValueError):
        consolidate(proposal,{**probe,"rows":[]},"head")

def test_nearest_rank_p95_and_invalid_samples():
    assert m.distribution([10,20,100]) == {"count":3,"p50":20,"p95":100,"max":100}
    assert m.distribution([10,float("nan")]) is None
    assert m.distribution([True]) is None

def test_cadence_reports_virtual_starvation_not_physical_gap():
    r=m.cadence([event(1,1,"old"),event(1,1.05,"old")])
    assert r["virtual_zero_reserve_deficit_ms"] == pytest.approx(30)
    assert r["virtual_starvation_events"]==1
    assert r["status"]=="MEASURED"

def test_trial_distribution_requires_all_three():
    a=[good_row() for _ in range(3)]
    b=[{**good_row(),"first_audio_ms":v} for v in (90,110,200)]
    r=m.trial_summary(a,b)
    assert r["metrics"]["first_audio_ms"]["p95_delta"]==100
    assert r["performance_gate"]=="NOT RUN"
    assert m.trial_summary(a,b[:2])["status"]=="NOT RUN"
