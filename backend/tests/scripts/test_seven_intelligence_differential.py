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


@pytest.mark.asyncio
@pytest.mark.parametrize('pending',[False,True])
async def test_product_transport_uses_real_chat_shape_and_refuses_unexpected_actions(monkeypatch,pending):
    import json
    import httpx
    monkeypatch.setenv('PLATFORM_LIVE_ORG_ID','f07e57c0-1501-4000-8000-c04e57a00001')
    monkeypatch.setenv('PLATFORM_LIVE_AUTH_MODE','smoke_org_short_lived')
    monkeypatch.setenv('PLATFORM_LIVE_BEARER_TOKEN','fixture-session')
    paths=[]
    def handler(req):
        paths.append(req.url.path)
        if req.url.path=='/health': return httpx.Response(200,json={'git_sha':'deployed-sha'})
        if req.url.path=='/api/conversations': return httpx.Response(201,json={'id':'conversation-1'})
        if req.url.path=='/api/assistant/chat':
            request=json.loads(req.content)
            assert request['messages'][0]['role']=='user'
            events=[{'type':'text-delta','delta':json.dumps(decisions())},
                {'type':'data-intelligence','data':{'messageId':'message-1','model':'observed-test-model'}}]
            raw='\n\n'.join('data: '+json.dumps(event) for event in events)
            return httpx.Response(200,text=raw,headers={'x-request-id':'request-1'})
        if req.url.path.endswith('/state'):
            return httpx.Response(200,json={'task_state':{'pending_task':{'type':'connector_action'}} if pending else {}})
        raise AssertionError('Unexpected endpoint: '+str(req.url))
    client=module.ProductClient(transport=httpx.MockTransport(handler))
    try:
        result=await module.run_case(client,'ignored-direct-model','customer_support','predictive','candidate-sha')
    finally:
        await client.close()
    assert not any('execute' in path for path in paths)
    if pending:
        assert result['status']=='FAIL'
        assert result['error_class']=='ValueError'
    else:
        assert result['status']=='PASS_LIVE_DECISION'
        assert result['evidence_scope']=='live_product_synthetic_sources'
        assert result['request_id']=='request-1' and result['response_id']=='message-1'
        assert result['product_conversation_id']=='conversation-1'
        assert result['deployed_git_sha']=='deployed-sha'
