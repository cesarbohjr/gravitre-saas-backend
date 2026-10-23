from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import httpx
import pytest
from app.services.managed_security_tools import MANAGED_SECURITY_TOOL_EXECUTORS
from app.services.tool_types import ToolAuthExpiredError, ToolValidationError


def ctx():
    return SimpleNamespace(client=MagicMock(),org_id='org-1',environment_name='production',connector_id=None,settings=SimpleNamespace())


def connector():
    return {'id':'c1','org_id':'org-1','environment':'production','type':'okta','status':'active',
            'config':{'auth_provider':'managed','managed_connection_id':'n1','managed_integration_id':'okta'}}


@pytest.mark.parametrize('action,params,endpoint,data,key',[
    ('okta.system_logs.list',{'limit':10},'/api/v1/logs',[{'id':'e1'}],'events'),
    ('okta.users.get',{'user_id':'user1'},'/api/v1/users/user1',{'id':'user1'},'user'),
    ('okta.groups.list',{},'/api/v1/groups',[{'id':'g1'}],'groups'),
    ('okta.apps.list',{},'/api/v1/apps',[{'id':'a1'}],'apps'),
    ('okta.users.factors.list',{'user_id':'user1'},'/api/v1/users/user1/factors',[{'id':'f1'}],'factors'),
])
@patch('app.services.managed_service_desk_tools.enforce_rate_limit')
@patch('app.services.managed_service_desk_tools.get_connector_by_type')
@patch('app.services.managed_security_tools.proxy_request')
def test_okta_reads_use_canonical_org_scoped_proxy(proxy,get_connector,rate,action,params,endpoint,data,key):
    get_connector.return_value = connector()
    proxy.return_value = httpx.Response(200,json=data,request=httpx.Request('GET','https://api.nango.dev/proxy'))
    result = MANAGED_SECURITY_TOOL_EXECUTORS[action](ctx(),params)
    assert result.success and result.data[key] == data
    assert proxy.call_args.kwargs['endpoint'] == endpoint
    assert proxy.call_args.kwargs['connection_id'] == 'n1'
    assert proxy.call_args.kwargs['integration_id'] == 'okta'
    assert proxy.call_args.kwargs['method'] == 'GET'


@patch('app.services.managed_service_desk_tools.enforce_rate_limit')
@patch('app.services.managed_service_desk_tools.get_connector_by_type')
@patch('app.services.managed_security_tools.proxy_request')
def test_okta_user_identifier_is_one_encoded_segment(proxy,get_connector,rate):
    get_connector.return_value = connector()
    proxy.return_value = httpx.Response(200,json={'id':'user1'},request=httpx.Request('GET','https://example'))
    MANAGED_SECURITY_TOOL_EXECUTORS['okta.users.get'](ctx(),{'user_id':'u1/../groups?admin=true'})
    assert proxy.call_args.kwargs['endpoint'] == '/api/v1/users/u1%2F..%2Fgroups%3Fadmin%3Dtrue'


@patch('app.services.managed_service_desk_tools.get_connector_by_type')
@patch('app.services.managed_security_tools.proxy_request')
def test_okta_rejects_foreign_tenant_before_proxy(proxy,get_connector):
    row = connector(); row['org_id'] = 'other'; get_connector.return_value = row
    with pytest.raises(ToolValidationError): MANAGED_SECURITY_TOOL_EXECUTORS['okta.groups.list'](ctx(),{})
    proxy.assert_not_called()


def test_okta_actions_have_registered_read_contracts():
    from app.connectors.action_catalog.registry import get_action_spec
    from app.services.tool_service import list_registered_actions
    for key in set(MANAGED_SECURITY_TOOL_EXECUTORS) - {"okta.users.suspend"}:
        spec = get_action_spec(key)
        assert spec and spec.kind == 'read'
        assert key in list_registered_actions()


@pytest.fixture(autouse=True)
def managed_remote_ownership(monkeypatch):
    monkeypatch.setattr("app.services.managed_service_desk_tools.scoped_connection", lambda *a, **kw: {"errors": []})


def test_containment_contract_requires_approval_and_has_exact_status_readback():
    from app.connectors.action_catalog.registry import get_action_spec
    from app.services.write_success_verification import resolve_success_verification
    from app.marketplace.marketplace3.security_operations import build_security_operations_outcome_pack_config
    spec = get_action_spec('okta.users.suspend')
    assert spec.kind == 'write' and spec.requires_approval
    assert spec.input_schema['properties']['status']['const'] == 'SUSPENDED'
    verification = resolve_success_verification(spec.id)
    assert verification.mode == 'follow_up_field_assert'
    assert verification.read_action == 'okta.users.get'
    assert verification.assert_field == 'status'
    play = next(p for p in build_security_operations_outcome_pack_config()['plays'] if p['key'] == 'containment-coordinator')
    types = [step['type'] for step in play['workflow_steps']]
    assert types[-2:] == ['approval', 'invoke_tool']
    assert play['workflow_steps'][-1]['config']['param_sources'] == {'user_id': '$target_user_id', 'status': 'SUSPENDED'}


@pytest.mark.parametrize('observed_id,status,expected', [('user1','SUSPENDED',True), ('user1','ACTIVE',False), ('foreign-user','SUSPENDED',False)])
@patch('app.services.tool_service.invoke_tool')
@patch('app.services.managed_service_desk_tools.enforce_rate_limit')
@patch('app.services.managed_service_desk_tools.get_connector_by_type')
@patch('app.services.managed_security_tools.proxy_request')
def test_containment_acceptance_is_not_success_without_matching_readback(proxy,get_connector,rate,read,observed_id,status,expected):
    from app.services.tool_types import NormalizedResult
    from app.services.field_assert_verify import verify_field_assert
    get_connector.return_value = connector()
    proxy.return_value = httpx.Response(204,request=httpx.Request('POST','https://provider.invalid'))
    params = {'user_id':'user1', 'status':'SUSPENDED'}
    result = MANAGED_SECURITY_TOOL_EXECUTORS['okta.users.suspend'](ctx(),params)
    assert result.success and result.data['accepted'] is True
    assert 'verified' not in result.data
    assert proxy.call_args.kwargs['method'] == 'POST'
    assert proxy.call_args.kwargs['endpoint'] == '/api/v1/users/user1/lifecycle/suspend'
    read.return_value = NormalizedResult(success=True,action='okta.users.get', data={'id':observed_id, 'user':{'id':observed_id,'status':status}})
    proof = verify_field_assert(invoke_action='okta.users.suspend', result_data=result.data, request_params=params,ctx=ctx(),settle=False)
    assert proof.verified is expected
