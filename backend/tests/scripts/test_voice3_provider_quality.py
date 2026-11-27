import math
import struct
import sys
from pathlib import Path
import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import voice3_provider_quality as m
from voice3_acoustic_eval import certification_blockers

VOICE = "A"*20
PCM = b"".join(struct.pack("<h",round(10000*math.sin(2*math.pi*180*i/16000))) for i in range(8000))

@pytest.mark.parametrize("protocol,path", [("flash","/v1/text-to-speech/"+VOICE),
                                            ("dialogue","/v1/text-to-dialogue")])
def test_provider_protocol_and_audio(protocol,path):
    import json
    def handler(req):
        body = json.loads(req.content)
        assert req.url.path == path
        assert req.url.params["output_format"] == "pcm_16000"
        assert body["model_id"] == m.MODELS[protocol]
        if protocol == "dialogue":
            assert body["inputs"][0]["voice_id"] == VOICE
        return httpx.Response(200,headers={"content-type":"audio/pcm"},content=PCM)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        _, result = m.synthesize(client,"fixture",VOICE,protocol,"test")
    assert result["integrity_failures"] == []

def test_invalid_content_type_rejected():
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json={"error":"bad"}))) as client:
        with pytest.raises(ValueError):
            m.synthesize(client,"fixture",VOICE,"dialogue","test")

def test_missing_provider_and_human_gates_block_certification():
    def handler(req):
        return httpx.Response(200,headers={"content-type":"audio/pcm"},content=PCM)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = m.evaluate_pair(client,{"ELEVENLABS_API_KEY":"fixture"},VOICE,VOICE)
    assert result["gates"]["v3_dialogue"] == "PASS"
    assert "intelligibility" in certification_blockers(result["gates"])
    assert "physical_mobile" in certification_blockers(result["gates"])
    assert "paired_quality" in certification_blockers(result["gates"])

def test_failed_dialogue_does_not_pass():
    def handler(req):
        if req.url.path.endswith("text-to-dialogue"):
            return httpx.Response(403)
        return httpx.Response(200,headers={"content-type":"audio/pcm"},content=PCM)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = m.evaluate_pair(client,{"ELEVENLABS_API_KEY":"fixture"},VOICE,VOICE)
    assert result["gates"]["v3_dialogue"] == "FAIL"

def test_envelope_uses_independent_baseline_range_and_fails_missing():
    base = dict(pitch_median_hz=180,pitch_iqr_hz=20,duration_ms=1000,max_internal_pause_ms=100)
    takes = [base,{**base,"pitch_median_hz":185},{**base,"pitch_median_hz":175}]
    assert m.acoustic_envelope(takes,base)["status"] == "WITHIN_OBSERVED_ENVELOPE"
    assert m.acoustic_envelope(takes,{**base,"pitch_median_hz":220})["status"] == "OUTSIDE_OBSERVED_ENVELOPE"
    assert m.acoustic_envelope(takes,{})["status"] == "NOT RUN"
    assert m.acoustic_envelope(takes[:1],base)["status"] == "NOT RUN"

@pytest.mark.parametrize("value,status", [(0,"PASS"),(.1,"FAIL"),(None,"NOT RUN"),(float("nan"),"NOT RUN")])
def test_comparative_wer_rejects_regression_even_below_absolute_limit(value,status):
    row = {"baseline_takes":[{"wer":0} for _ in range(3)],"candidate_flash":{"wer":value}}
    assert m.comparative_wer([row],"candidate_flash")["status"] == status

def test_baseline_takes_are_independent_even_for_retained_voice():
    calls = []
    def handler(req):
        calls.append(req.url.path)
        return httpx.Response(200,headers={"content-type":"audio/pcm"},content=PCM)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = m.evaluate_pair(client,{"ELEVENLABS_API_KEY":"fixture"},VOICE,VOICE)
    assert calls.count("/v1/text-to-speech/"+VOICE) == len(m.FIXTURES)*4
    assert all(len(r["baseline_takes"]) == 3 for r in result["fixtures"])
    assert result["subjective_review"]["status"] == "NOT RUN"
