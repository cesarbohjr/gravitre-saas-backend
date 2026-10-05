from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock
import hashlib, hmac, json
import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from app.routers import managed_connector_auth as routes
from app.auth.dependencies import require_admin, require_org_member, get_environment_context
from app.config import get_settings


class Query:
    def __init__(self, store): self.store, self.filters, self.change, self.new = store, [], None, None
    def select(self, *args): return self
    def eq(self, key, value): self.filters.append((key,value)); return self
    def is_(self, key, value): self.filters.append((key,None)); return self
    def limit(self, *args): return self
    def update(self, value): self.change = value; return self
    def insert(self, value): self.new = value; return self
    def execute(self):
        if self.new:
            row = {**self.new, 'id':'new-connector', 'deleted_at':None}; self.store.append(row)
            return SimpleNamespace(data=[deepcopy(row)])
        rows = [row for row in self.store if all((row.get("config",{}).get(k.split("->>")[1]) if "->>" in k else row.get(k))==v for k,v in self.filters)]
        if self.change:
            for row in rows: row.update(deepcopy(self.change))
        return SimpleNamespace(data=deepcopy(rows))


def row(**kwargs):
    return {'id':'c1','org_id':'o1','vendor':'freshservice','type':'freshservice','name':'desk',
            'status':'active','environment':'production','deleted_at':None,
            'config':{'auth_provider':'managed','managed_integration_id':'freshservice',
                      'managed_connection_id':'n1','instance_url':'https://example.freshservice.com'},**kwargs}


@pytest.fixture
def flow(monkeypatch):
    store = [row()]
    settings = SimpleNamespace(nango_secret_key='secret',nango_webhook_signing_key='signing',
                               supabase_url='https://example.supabase.co',supabase_service_role_key='service')
    client = SimpleNamespace(table=lambda _: Query(store))
    monkeypatch.setattr(routes,'create_client',lambda *a: client)
    session = MagicMock(return_value={'token':'short-lived','expires_at':'tomorrow'})
    monkeypatch.setattr(routes,'create_connect_session',session)
    monkeypatch.setattr(routes,'write_audit_event',lambda *a,**kw: None)
    app = FastAPI(); app.include_router(routes.router)
    app.dependency_overrides[require_admin] = lambda: ({'user_id':'u1'},'o1')
    app.dependency_overrides[require_org_member] = lambda: ({'user_id':'u1'},'o1','admin')
    app.dependency_overrides[get_environment_context] = lambda: 'production'
    app.dependency_overrides[get_settings] = lambda: settings
    return app,store,settings,session


async def post_webhook(client,payload):
    raw = json.dumps(payload).encode()
    signature = hmac.new(b'signing',raw,hashlib.sha256).hexdigest()
    return await client.post('/api/connectors/managed-auth/webhook/nango',content=raw,
                             headers={'X-Nango-Hmac-Sha256':signature})


@pytest.mark.asyncio
async def test_reconnect_preserves_config_and_requires_current_webhook(flow):
    app,store,_,session = flow
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        response = await client.post('/api/connectors/managed-auth/freshservice/session',json={'name':'desk','connectorId':'c1'})
        assert response.status_code == 200
        attempt = response.json()['attemptId']
        assert session.call_args.kwargs['connection_id'] == 'n1'
        assert store[0]['config']['instance_url'] == 'https://example.freshservice.com'
        assert store[0]['config']['managed_connection_id'] == 'n1'
        assert store[0]['status'] == 'active'
        status = (await client.get('/api/connectors/managed-auth/c1/status')).json()
        assert status.get('confirmedAttemptId') != attempt
        payload = {'type':'auth','success':True,'operation':'override','connectionId':'n1','providerConfigKey':'freshservice',
                   'tags':{'organization_id':'o1','connector_id':'c1','auth_attempt_id':'stale'}}
        assert (await post_webhook(client,payload)).status_code == 409
        payload['tags']['auth_attempt_id'] = attempt
        assert (await post_webhook(client,payload)).status_code == 200
        status = (await client.get('/api/connectors/managed-auth/c1/status')).json()
        assert status['connected'] and status['confirmedAttemptId'] == attempt
        assert 'connectionId' not in status and 'sessionToken' not in status


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value',[('org_id','o2'),('environment','staging'),('vendor','okta')])
async def test_reconnect_and_status_cannot_cross_scope(flow,field,value):
    app,store,_,session = flow; store[0][field] = value
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        response = await client.post('/api/connectors/managed-auth/freshservice/session',json={'name':'desk','connectorId':'c1'})
        assert response.status_code in {400,404}
        if field != 'vendor':
            assert (await client.get('/api/connectors/managed-auth/c1/status')).status_code == 404
    session.assert_not_called()


@pytest.mark.asyncio
async def test_missing_signing_key_blocks_session_before_mutation(flow):
    app,store,settings,session = flow; settings.nango_webhook_signing_key = ''
    before = deepcopy(store)
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        response = await client.post('/api/connectors/managed-auth/freshservice/session',json={'name':'desk','connectorId':'c1'})
        assert response.status_code == 503
    assert store == before; session.assert_not_called()


@pytest.mark.asyncio
async def test_new_session_never_reuses_staging_row(flow):
    app,store,_,session = flow; store[0]['environment'] = 'staging'
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        response = await client.post('/api/connectors/managed-auth/freshservice/session',json={'name':'desk'})
        assert response.status_code == 200
        assert response.json()['connectorId'] != 'c1'
    assert store[0]['environment'] == 'staging'
    assert store[1]['environment'] == 'production'
    assert session.call_args.kwargs['connection_id'] is None


@pytest.mark.asyncio
async def test_signed_webhook_cannot_activate_native_or_wrong_integration(flow):
    app,store,_,_ = flow
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        payload = {'type':'auth','success':True,'operation':'creation','connectionId':'n2','providerConfigKey':'okta',
                   'tags':{'organization_id':'o1','connector_id':'c1'}}
        assert (await post_webhook(client,payload)).status_code == 400
        store[0]['config']['auth_provider'] = 'native'
        payload['providerConfigKey'] = 'freshservice'
        assert (await post_webhook(client,payload)).status_code == 400
        assert (await post_webhook(client,[])).status_code == 400


@pytest.mark.asyncio
async def test_catalog_exposes_only_registered_action_support(flow):
    app,_,_,_ = flow
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
        result = (await client.get('/api/connectors/managed-auth/catalog')).json()
    assert result['configured']
    providers = {r['vendor']:r for r in result['connectors']}
    assert len(providers) == 47
    assert len(providers['freshservice']['actions']) == 4
    assert len(providers['okta']['actions']) == 5
    assert providers['halo_psa']['support'] == 'authorization_only'
