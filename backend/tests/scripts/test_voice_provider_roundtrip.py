import importlib.util
from pathlib import Path
import json
import httpx
import pytest

path = Path(__file__).resolve().parents[3] / 'scripts/verify-voice-provider-roundtrip.py'
spec = importlib.util.spec_from_file_location('provider_roundtrip', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_missing_provider_setup_returns_not_run_without_requests():
    result = module.run_provider_checks({})
    assert result['status'] == 'NOT RUN'
    assert result['cases'] == []
    assert result['physical_acceptance'] == 'NOT RUN'


@pytest.mark.parametrize('cancel_transcript', ['Cancel it. Do not send anything.', 'Cancel it do not send anything', 'Cancel it, do not send anything', 'Do not send anything', 'Don’t send anything'])
def test_synthetic_provider_protocol_and_commit_gate_roundtrip(cancel_transcript):
    calls = []
    transcripts = iter(['Yes, wait. Hold on.', cancel_transcript])
    def request(req):
        calls.append(req)
        if req.url.host == 'api.elevenlabs.io':
            assert json.loads(req.content)['text'] in {phrase for _,phrase in module.CASES}
            return httpx.Response(200,content=b'synthetic-test-audio')
        assert req.url.host == 'api.deepgram.com'
        assert req.url.params['smart_format'] == 'true'
        return httpx.Response(200,json={'metadata':{'request_id':'proof'},'results':{'channels':[{'alternatives':[{'transcript':next(transcripts)}]}]}})
    result = module.run_provider_checks({'DEEPGRAM_API_KEY':'test-stt','ELEVENLABS_API_KEY':'test-tts','ELEVENLABS_VOICE_ID':'test-voice'}, transport=httpx.MockTransport(request))
    assert result['status'] == 'PASS'
    assert len(calls) == 4
    assert all(row['business_write_executors_called'] == 0 for row in result['cases'])
    assert result['physical_acceptance'] == 'NOT RUN'
    assert [r['stt_diagnostics']['decision'] for r in result['cases']] == ['hold_commit', 'reject']
    assert all(r['stt_diagnostics']['invoke_allowed'] is False for r in result['cases'])
    assert all(r['stt_diagnostics']['transcript_present'] is True for r in result['cases'])
    serialized = json.dumps(result)
    assert 'Yes, wait. Hold on.' not in serialized
    assert 'Cancel it. Do not send anything.' not in serialized


@pytest.mark.asyncio
@pytest.mark.parametrize('trial',range(20))
async def test_twenty_cancelled_turns_reach_no_business_write_commit(trial):
    assert await module.prove_commit_block('Yes, wait. Hold on.')

