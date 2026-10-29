from dataclasses import asdict
from unittest.mock import Mock
from fastapi.testclient import TestClient
import pytest
from app.services.native_runtime.api import create_app
from app.services.native_runtime.control import IntakeSigner
from app.services.tool_types import ToolContext
from app.services.write_authority import WriteAuthority
from tests.native_runtime.test_runtime import setup,S,ORG,AGENT,ACTOR
from tests.native_runtime.test_journal import journal


def invoke(setup,operation,payload,*,actor=ACTOR,authority=None,changed=None):
    runtime,claims,db,runner=setup;signer=IntakeSigner('s'*32)
    ctx=ToolContext(runtime.settings,db,ORG,actor,agent_id=AGENT,run_id=S.run_id)
    token=signer.sign(ctx,operation,payload,authority=authority)
    client=TestClient(create_app(runtime,Mock(),signer))
    return client.post('/v1/invoke',json={'operation':operation,'payload':payload if changed is None else changed},headers={'Authorization':'Bearer '+token})


def test_private_api_signature_scope_and_explicit_approval(setup):
    payload={'task':'Review software'}
    assert invoke(setup,'run_openhands',payload).status_code==403
    assert invoke(setup,'run_openhands',payload,authority=WriteAuthority('policy','auto')).status_code==403
    result=invoke(setup,'run_openhands',payload,authority=WriteAuthority('human','one'))
    assert result.status_code==200 and result.json()['state']=='queued'
    assert invoke(setup,'run_openhands',payload,authority=WriteAuthority('human','one')).json()['job_id']==result.json()['job_id']
    assert invoke(setup,'run_openhands',payload,authority=WriteAuthority('human','one'),changed={'task':'Changed after approval'}).status_code==403
    id=result.json()['job_id']
    status=invoke(setup,'native_job_status',{'job_id':id})
    assert status.status_code==200 and 'payload' not in status.json()
    assert invoke(setup,'native_job_status',{'job_id':id},actor='someone-else').status_code==403
    assert invoke(setup,'cancel_native_job',{'job_id':id}).json()['cancelled'] is True


def test_worker_never_exposes_error_bodies_or_credentials(setup):
    runtime,claims,db,runner=setup
    runtime.route_for=Mock(side_effect=RuntimeError('SECRET bearer credential'))
    response=invoke(setup,'run_openhands',{'task':'test'},authority=WriteAuthority('human','one'))
    assert response.status_code==403 and 'SECRET' not in response.text and 'bearer credential' not in response.text


def test_actual_native_catalog_and_planner_schema_share_write_authority():
    from app.connectors.action_catalog.registry import get_action_spec
    from app.connectors.action_catalog.f1_write_slice import requires_write_approval_always
    from app.services.tool_service import list_registered_actions
    from app.services.tool_registry import _build_agent_tool_specs
    from app.services.native_runtime.specs import DEFINITIONS
    specs=_build_agent_tool_specs();registered=set(list_registered_actions())
    for operation,definition in DEFINITIONS.items():
        action='assistant.'+operation
        assert action in registered
        assert get_action_spec(action).input_schema==definition[1]
        assert specs['platform_'+operation].parameters==definition[1]
        if operation in {'run_openhands','run_browser_use','approve_native_action','export_evaluation_metrics'}:
            assert requires_write_approval_always(action)
            assert get_action_spec(action).requires_approval is True


def test_registry_never_caches_native_status_before_authorization(setup,monkeypatch):
    import asyncio
    from app.services.tool_registry import ToolRegistry
    from app.services.tool_types import NormalizedResult
    runtime,claims,db,runner=setup
    ctx=ToolContext(runtime.settings,db,ORG,ACTOR,agent_id=AGENT,run_id=S.run_id)
    registry=ToolRegistry()
    cached=Mock(return_value={'success':True,'result':{'state':'completed'}})
    monkeypatch.setattr('app.services.read_action_result_cache.get_cached_read_result',cached)
    invoke=Mock(return_value=NormalizedResult(True,'assistant.native_job_status',data={'state':'running'}))
    monkeypatch.setattr('app.services.tool_service.invoke_tool',invoke)
    monkeypatch.setattr('app.services.tool_registry.invoke_tool',invoke)
    async def check():
        for _ in range(2):
            result=await registry.execute_invoke_action(ctx=ctx,invoke_action='assistant.native_job_status',args={'job_id':'job','run_id':S.run_id})
            assert result['result']['state']=='running'
        for _ in range(2):
            result=await registry.execute_tool(ctx=ctx,tool_name='platform_native_job_status',args={'job_id':'job','run_id':S.run_id})
            assert result['result']['state']=='running'
    asyncio.run(check())
    assert invoke.call_count==4 and not cached.called


def test_registry_does_not_verify_queue_acceptance_as_execution(setup):
    import asyncio
    from app.services.tool_registry import _settle_write_payload
    runtime,claims,db,runner=setup
    ctx=ToolContext(runtime.settings,db,ORG,ACTOR,agent_id=AGENT,run_id=S.run_id)
    result=asyncio.run(_settle_write_payload(ctx,tool='platform_run_openhands',action='assistant.run_openhands',params={},payload={'success':True,'result':{'state':'queued'}},verify=True))
    assert result['success'] and result['outcome_verified'] is False
    assert result['verification']['status']=='pending'


def test_native_planner_readiness_uses_worker_configuration_not_fake_oauth(monkeypatch):
    from types import SimpleNamespace
    from app.services.tool_registry import ToolRegistry
    registry=ToolRegistry()
    monkeypatch.setattr('app.services.tool_registry.get_settings',lambda:SimpleNamespace(native_worker_url=''))
    assert not any(t['function']['name']=='platform_run_openhands' for t in registry.get_tools_for_agent([],[]))
    monkeypatch.setattr('app.services.tool_registry.get_settings',lambda:SimpleNamespace(native_worker_url='https://private-worker.example'))
    assert any(t['function']['name']=='platform_run_openhands' for t in registry.get_tools_for_agent(['platform_run_openhands'],[]))


def test_canonical_ledger_metadata_does_not_become_worker_task_input(setup,monkeypatch):
    from types import SimpleNamespace
    from app.services.native_runtime import tools
    runtime,claims,db,runner=setup
    settings=SimpleNamespace(native_worker_url='https://worker.example',native_worker_signing_key='s'*32)
    ctx=ToolContext(settings,db,ORG,ACTOR,agent_id=AGENT,run_id=S.run_id)
    monkeypatch.setattr(tools,'require_access',lambda *_:None)
    monkeypatch.setattr(tools,'require_approval',lambda **_:WriteAuthority('human','approved'))
    response=Mock(status_code=200);response.json.return_value={'state':'queued'}
    client=Mock();client.__enter__=Mock(return_value=client);client.__exit__=Mock(return_value=False);client.post.return_value=response
    monkeypatch.setattr(tools.httpx,'Client',lambda **_:client)
    result=tools.invoke_native(ctx,'run_openhands',{'task':'draft','_gravitre_idempotency_key':'canonical-ledger-key'})
    assert result.success
    assert client.post.call_args.kwargs['json']['payload']=={'task':'draft'}
