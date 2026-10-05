from types import SimpleNamespace
from unittest.mock import MagicMock
import json
from pathlib import Path
import pytest
from app.connectors.managed_health import managed_auth_status
from app.connectors.nango_registry import NANGO_CONNECTOR_REGISTRY


def settings(**kw):
    return SimpleNamespace(nango_secret_key=kw.get('secret','secret'), nango_webhook_signing_key='signing', nango_api_base_url='https://api.nango.dev')


def client(row):
    c = MagicMock()
    q = c.table.return_value
    for method in ('select','eq','is_','limit'):
        getattr(q, method).return_value = q
    q.execute.return_value.data = [row] if row else []
    return c


def test_frontend_catalog_matches_canonical_registry():
    frontend = json.loads((Path(__file__).parents[3] / 'apps/web/lib/managed-connectors.json').read_text())
    assert {(r['vendorKey'],r['integrationId']) for r in frontend} == {(r.vendor,r.integration_id) for r in NANGO_CONNECTOR_REGISTRY.values()}


@pytest.mark.parametrize('status,config,expected', [
    ('active',{'auth_provider':'managed','managed_connection_id':'n1','managed_integration_id':'freshservice'},'connected'),
    ('pending_auth',{'auth_provider':'managed','managed_connection_id':'n1','managed_integration_id':'freshservice'},'pending_auth'),
    ('error',{'auth_provider':'managed','managed_connection_id':'n1','managed_integration_id':'freshservice'},'auth_expired'),
    ('active',{'auth_provider':'managed','managed_connection_id':'n1','managed_integration_id':'okta'},'misconfigured'),
    ('active',{'auth_provider':'managed','managed_integration_id':'freshservice'},'pending_auth'),
    ('active',{},'pending_auth'),
])
def test_managed_health_is_scoped_and_fails_closed(status,config,expected):
    c = client({'vendor':'freshservice','status':status,'config':config})
    assert managed_auth_status(c,'org1','c1',settings(),environment_name='production') == expected
    calls = c.table.return_value.eq.call_args_list
    assert any(call.args == ('org_id','org1') for call in calls)
    assert any(call.args == ('environment','production') for call in calls)


def test_missing_secret_is_not_connected():
    assert managed_auth_status(client(None),'org1','c1',settings(secret=''),environment_name='production') == 'misconfigured'


@pytest.mark.parametrize('remote_status,body,expected', [
    (200,{'connection_id':'n1','provider_config_key':'freshservice','errors':[]},'connected'),
    (200,{'connection_id':'n1','provider_config_key':'okta','errors':[]},'auth_expired'),
    (200,{'connection_id':'n1','provider_config_key':'freshservice','errors':[{'type':'auth'}]},'auth_expired'),
    (200,{},'auth_expired'),
    (404,{},'auth_expired'),
    (424,{},'auth_expired'),
    (503,{},'misconfigured'),
])
def test_remote_health_uses_current_api_and_rejects_invalid_metadata(monkeypatch,remote_status,body,expected):
    import httpx
    captured = {}
    def get(self,url,**kwargs):
        captured.update(url=url,**kwargs)
        return httpx.Response(remote_status,json=body,request=httpx.Request('GET',url))
    monkeypatch.setattr(httpx.Client,'get',get)
    c = client({'vendor':'freshservice','status':'active','config':{'auth_provider':'managed','managed_connection_id':'n1','managed_integration_id':'freshservice'}})
    assert managed_auth_status(c,'o1','c1',settings(),environment_name='production',validate_remote=True) == expected
    assert captured['url'] == 'https://api.nango.dev/connections/n1'
    assert captured['params']['provider_config_key'] == 'freshservice'


def test_managed_types_migration_covers_registry():
    migration = (Path(__file__).parents[3] / 'supabase/migrations/20261001233000_add_nango_long_tail_connector_types.sql').read_text()
    for vendor in NANGO_CONNECTOR_REGISTRY:
        assert "'" + vendor + "'" in migration
