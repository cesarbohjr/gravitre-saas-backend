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
