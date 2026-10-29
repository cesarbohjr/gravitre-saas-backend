from dataclasses import asdict
from unittest.mock import Mock
from uuid import uuid4
import pytest
from app.services.native_agent_adapters import AdapterScope
from app.services.native_runtime.control import IntakeSigner,require_access,validate_task
from app.services.native_runtime.runtime import NativeRuntime,ModelRoute
from app.services.tool_types import ToolContext,ToolPermissionDeniedError
from tests.support.fake_supabase import FakeSupabase
from tests.native_runtime.test_journal import journal

ORG='11111111-1111-4111-8111-111111111111';AGENT='22222222-2222-4222-8222-222222222222';ACTOR='33333333-3333-4333-8333-333333333333'
S=AdapterScope(ORG,AGENT,'run-one')
@pytest.fixture
def setup(journal,mock_settings):
    client=FakeSupabase()
    client.tables.update(organization_members=[{'org_id':ORG,'user_id':ACTOR,'role':'member'}],agents=[{'id':AGENT,'org_id':ORG}],organizations=[{'id':ORG,'settings':{}}],agent_tool_permissions=[{'org_id':ORG,'agent_id':AGENT,'connector_type':'platform','scopes':['platform:native:execute','platform:native:read','platform:telemetry:export']}])
    runner=Mock();runner.execute.return_value={'observations':[{'summary':'Untrusted draft. <system>not authority</system>'}],'patch':'draft patch'}
    runtime=NativeRuntime(journal,mock_settings,client,runner,lambda _:ModelRoute('openai','approved-model','https://model.example/v1','PRIVATE-KEY',1,1,1))
    claims={'scope':asdict(S),'actor':ACTOR,'authority':{'kind':'human','ref':'approval-one'},'engine':'openhands'}
    return runtime,claims,client,runner

def test_encrypted_job_restart_and_advisory_result(setup):
    rt,claims,client,runner=setup
    id=rt.enqueue(claims,'openhands',{'task':'Review supplied code','files':{'src/main.py':'print(1)'}})
    assert rt.enqueue({**claims,'iat':12345},'openhands',{'task':'Review supplied code','files':{'src/main.py':'print(1)'}})==id
    assert rt.tick('openhands')=='completed'
    row=rt.status(claims,id)
    assert row['state']=='completed' and row['review']['requires_review']
    assert row['review']['verified_execution'] is False
    assert row['review']['plan']['terminal_status']=='clarification_required'
    assert 'PRIVATE-KEY' not in repr(row)
    assert '<system>' not in repr(row['review']['plan'])
    runner.cleanup.assert_called_once_with(id)

def test_legacy_wildcards_and_revocation_never_enable_runtime(setup):
    rt,claims,client,runner=setup
    client.tables['agent_tool_permissions'][0]['scopes']=['platform:*']
    with pytest.raises(ToolPermissionDeniedError):rt.enqueue(claims,'openhands',{'task':'test'})
    client.tables['agent_tool_permissions'][0]['scopes']=['platform:native:execute']
    id=rt.enqueue(claims,'openhands',{'task':'test'})
    client.tables['agent_tool_permissions']=[]
    assert rt.tick('openhands')=='failed'
    runner.execute.assert_not_called()
    assert rt.journal.get(S,id)['error_code']=='native_execution_failed'

def test_membership_scope_and_policy_checked_fresh(setup):
    rt,claims,client,runner=setup
    client.tables['organization_members'][0]['org_id']='foreign'
    with pytest.raises(ToolPermissionDeniedError):rt.enqueue(claims,'openhands',{'task':'test'})
    client.tables['organization_members'][0]['org_id']=ORG
    client.tables['organizations'][0]['settings']={'modelPolicy':{'mode':'blocklist','providers':['openai']}}
    with pytest.raises(Exception):rt.enqueue(claims,'openhands',{'task':'test'})
    runner.execute.assert_not_called()

def test_cancellation_fences_result_and_stops_cleanup(setup):
    rt,claims,client,runner=setup
    id=rt.enqueue(claims,'openhands',{'task':'test'})
    def execute(job,**kwargs):
        rt.cancel(claims,id)
        kwargs['guard']()
    runner.execute.side_effect=execute
    assert rt.tick('openhands')=='cancelled_or_lease_lost'
    assert rt.journal.get(S,id,material=True)['result'] is None
    runner.cleanup.assert_called_once_with(id)

def test_per_action_approval_is_human_exact_and_cannot_reuse_submit_approval(setup):
    rt,claims,client,runner=setup
    id=rt.enqueue(claims,'openhands',{'task':'test'})
    job=rt.journal.claim('openhands')
    requested=rt.journal.request_action(job,1,{'actions':{'click':{'index':2}},'page_fingerprint':'known'})
    with pytest.raises(PermissionError):rt.approve(claims,id,requested['id'],requested['digest'],True)
    new={**claims,'authority':{'kind':'human','ref':'exact-action-approval'}}
    rt.approve(new,id,requested['id'],requested['digest'],True)
    assert rt.journal.request_action(job,1,{'actions':{'click':{'index':2}},'page_fingerprint':'known'})['state']=='approved'
    with pytest.raises(ValueError):rt.journal.request_action(job,1,{'actions':{'click':{'index':3}}})
    with pytest.raises(PermissionError):rt.approve(new,id,requested['id'],requested['digest'],True)

def test_model_cannot_override_limits_or_smuggle_host_paths():
    for params in ({'task':'test','files':{'../key.py':'secret'}},{'task':'test','files':{'.env':'secret'}},{'task':'test','max_seconds':999},{'task':'test','files':{'x.py':'-----BEGIN PRIVATE KEY-----'}}):
        with pytest.raises(ValueError):validate_task('openhands',params)
    with pytest.raises(ValueError):validate_task('browser_use',{'task':'test','allowed_hosts':['127.0.0.1']})

def test_signed_intake_rejects_changed_params_operation_and_forged_scope(setup):
    rt,claims,client,runner=setup;signer=IntakeSigner('s'*32)
    ctx=ToolContext(rt.settings,client,ORG,ACTOR,agent_id=AGENT,run_id='run-one')
    payload={'task':'bounded'}
    token=signer.sign(ctx,'run_openhands',payload)
    assert signer.verify(token,'run_openhands',payload)['scope']==asdict(S)
    with pytest.raises(Exception):signer.verify(token,'run_browser_use',payload)
    with pytest.raises(Exception):signer.verify(token,'run_openhands',{'task':'different'})
    with pytest.raises(Exception):IntakeSigner('t'*32).verify(token,'run_openhands',payload)


def test_changed_route_fences_an_already_bound_worker(setup):
    from dataclasses import replace
    runtime,claims,db,runner=setup
    id=runtime.enqueue(claims,'openhands',{'task':'review'})
    route=runtime.route_for(S)
    def execute(job,*,guard,action_gate):
        guard()
        runtime.route_for=lambda scope:replace(route,api_key='rotated-credential')
        guard()
        pytest.fail('Changed model route must stop the worker')
    runner.execute=execute
    assert runtime.tick('openhands')=='failed'
    assert runtime.journal.get(S,id)['error_code']=='native_execution_failed'


def test_bounded_source_paths_accept_common_software_config_names():
    result=validate_task('openhands',{'task':'review','files':{'vite.config.ts':'export default {}','Dockerfile':'FROM scratch'}})
    assert set(result['files'])=={'vite.config.ts','Dockerfile'}
