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
