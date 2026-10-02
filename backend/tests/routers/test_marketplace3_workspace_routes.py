from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app
from app.auth.dependencies import get_current_user, require_platform_admin, get_org_context
from app.config import Settings, get_settings
from app.marketplace.marketplace3.portfolio_readiness import _outcome_assets

@pytest.fixture(autouse=True)
def setup():
    app.dependency_overrides[get_current_user] = lambda: {'user_id': 'member'}
    app.dependency_overrides[require_platform_admin] = lambda: {'user_id': 'admin'}
    app.dependency_overrides[get_org_context] = lambda: 'member-org'
    app.dependency_overrides[get_settings] = lambda: Settings(app_env='dev', supabase_url='https://test.supabase.co', supabase_anon_key='test', supabase_service_role_key='test', supabase_jwt_secret='test')
    yield
    app.dependency_overrides.clear()


def test_workspace_uses_validated_org_context(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr('app.routers.marketplace.create_client', lambda *_: db)
    resolve = MagicMock(return_value={'contract': {}, 'measurements': []})
    monkeypatch.setattr('app.marketplace.marketplace3.workspace.department_workspace', resolve)
    response = TestClient(app).get('/api/marketplace/assets/revenue-operations-3/workspace?org_id=untrusted-org')
    assert response.status_code == 200
    resolve.assert_called_once_with(db, 'member-org', 'revenue-operations-3')


def test_workspace_requires_org_context(monkeypatch):
    app.dependency_overrides[get_org_context] = lambda: None
    resolve = MagicMock()
    monkeypatch.setattr('app.marketplace.marketplace3.workspace.department_workspace', resolve)
    assert TestClient(app).get('/api/marketplace/assets/revenue-operations-3/workspace').status_code == 403
    resolve.assert_not_called()


def test_blueprint_requires_admin(monkeypatch):
    def deny(): raise HTTPException(status_code=403, detail='Platform admin required')
    app.dependency_overrides[require_platform_admin] = deny
    fetch = MagicMock()
    monkeypatch.setattr('app.routers.marketplace.fetch_marketplace_asset', fetch)
    assert TestClient(app).get('/api/marketplace/platform/assets/revenue-operations-3/marketplace3/blueprint').status_code == 403
    fetch.assert_not_called()


def test_blueprint_never_supplies_tenant_results(monkeypatch):
    a = _outcome_assets()[2]
    monkeypatch.setattr('app.routers.marketplace.create_client', lambda *_: MagicMock())
    monkeypatch.setattr('app.routers.marketplace.fetch_marketplace_asset', lambda *_: {'id':a.slug,'slug':a.slug,'title':a.title,'asset_type':'outcome_pack','config':a.config})
    response = TestClient(app).get(f'/api/marketplace/platform/assets/{a.slug}/marketplace3/blueprint')
    assert response.status_code == 200
    assert response.json()['contract']['dashboard'] == a.config['dashboard']
    assert response.json()['measurements'] == []
    assert 'install' not in response.json()
