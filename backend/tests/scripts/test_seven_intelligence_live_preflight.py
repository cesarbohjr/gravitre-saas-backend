import importlib.util
import io
import json
from pathlib import Path
import pytest

path=Path(__file__).resolve().parents[3]/'scripts/seven-intelligence-live-preflight.py'
spec=importlib.util.spec_from_file_location('seven_preflight',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_preflight_refuses_operator_or_unscoped_session(monkeypatch,tmp_path):
    monkeypatch.setenv('PLATFORM_LIVE_BEARER_TOKEN','secret-test-token')
    monkeypatch.setenv('PLATFORM_LIVE_ORG_ID','operator-org')
    with pytest.raises(SystemExit,match='Isolated'):
        module.execute(tmp_path/'report.json')

def test_preflight_keeps_credentials_and_unreviewed_config_out_of_evidence(monkeypatch,tmp_path):
    monkeypatch.setenv('PLATFORM_LIVE_BEARER_TOKEN','secret-test-token')
    monkeypatch.setenv('PLATFORM_LIVE_ORG_ID',module.ORG)
    monkeypatch.setenv('PLATFORM_LIVE_AUTH_MODE','smoke_org_short_lived')
    class Response(io.BytesIO):
        status=200
    def open_request(req,**kwargs):
        assert req.get_method()=='GET'
        if req.full_url.endswith('/api/connectors'):
            body={'connectors':[{'type':'hubspot','status':'active','config':{
                'api_key':'must-not-be-logged','cloned_from':'operator-connector','isolated_smoke':True}}]}
        elif req.full_url.endswith('/health'): body={'git_sha':'deployed-sha'}
        else: body={}
        return Response(json.dumps(body).encode())
    monkeypatch.setattr(module.urllib.request,'urlopen',open_request)
    output=tmp_path/'report.json'; module.execute(output)
    content=output.read_text()
    assert 'must-not-be-logged' not in content and 'secret-test-token' not in content
    report=json.loads(content)
    assert report['mutation'] is False
    assert report['connectors'][0]['shares_operator_install'] is True
    assert report['provider_fixtures_certified'] is False
