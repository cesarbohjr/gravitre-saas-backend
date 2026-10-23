from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.auth.dependencies import require_admin
from app.config import get_settings
from app.marketplace.marketplace3.certification_routes import router
from app.marketplace.marketplace3.msp_service_desk import build_msp_service_desk_outcome_pack_config

@pytest.fixture
def client():
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "admin"}, "org")
    app.dependency_overrides[get_settings] = lambda: MagicMock()
    return TestClient(app)


@pytest.fixture(autouse=True)
def scenario_recorder():
    with patch("app.marketplace.marketplace3.scenario_runner.record_executed_scenarios", new_callable=AsyncMock, return_value={"checks": {}}):
        yield


def _asset(org="org"):
    return {"id": "pack", "org_id": org, "asset_type": "outcome_pack", "config": build_msp_service_desk_outcome_pack_config()}


def test_caller_cannot_submit_certification_evidence(client):
    response = client.post('/assets/pack/certification/run', json={"mode": "production", "evidence": {"passed": True}})
    assert response.status_code == 422


def test_foreign_asset_is_not_visible_or_certifiable(client):
    with patch('app.marketplace.marketplace3.certification_routes.shared_service_client'), patch('app.marketplace.marketplace3.certification_routes._fetch_asset', return_value=_asset("foreign")):
        assert client.get('/assets/pack/certification').status_code == 404
        assert client.post('/assets/pack/certification/run', json={"mode": "production"}).status_code == 404


def test_fixture_contract_never_persists_or_grants_publication(client):
    with patch('app.marketplace.marketplace3.certification_routes.shared_service_client'), patch('app.marketplace.marketplace3.certification_routes._fetch_asset', return_value=_asset()), patch('app.marketplace.marketplace3.certification_routes.certify_and_record_outcome_pack') as issue:
        result = client.post('/assets/pack/certification/run', json={"mode": "fixture"})
    assert result.status_code == 200
    assert result.json()['publishReady'] is False
    issue.assert_not_called()


def test_production_collection_uses_authenticated_actor_and_server_config(client):
    with patch('app.marketplace.marketplace3.certification_routes.shared_service_client'), patch('app.marketplace.marketplace3.certification_routes._fetch_asset', return_value=_asset()), patch('app.marketplace.marketplace3.certification_routes.certify_and_record_outcome_pack', return_value={"publishReady": False}) as issue:
        result = client.post('/assets/pack/certification/run', json={"mode": "production"})
    assert result.status_code == 200
    assert issue.call_args.kwargs['actor_id'] == 'admin'
    assert issue.call_args.kwargs['org_id'] == 'org'
    assert 'evidence' not in issue.call_args.kwargs


def test_non_admin_is_denied(client):
    def denied():
        raise HTTPException(403, 'Admin required')
    client.app.dependency_overrides[require_admin] = denied
    assert client.get('/assets/pack/certification').status_code == 403
    assert client.post('/assets/pack/certification/run', json={}).status_code == 403


def test_status_withholds_ready_after_skill_revocation(client):
    from app.marketplace.marketplace3.certification_store import OutcomePackCertificationError
    with patch('app.marketplace.marketplace3.certification_routes.shared_service_client'), patch('app.marketplace.marketplace3.certification_routes._fetch_asset', return_value=_asset()), patch('app.marketplace.marketplace3.certification_routes.get_outcome_pack_certification', return_value={"publishReady": True, "level": "production_verified", "report": {}}), patch('app.marketplace.marketplace3.certification_routes.assert_outcome_pack_publish_ready', side_effect=OutcomePackCertificationError("Skill approval revoked")):
        result = client.get('/assets/pack/certification')
    assert result.status_code == 200
    assert result.json()['publishReady'] is False
    assert result.json()['certification']['publishReady'] is False
    assert result.json()['certification']['report']['findings'][0]['message'] == 'Skill approval revoked'


@pytest.mark.parametrize("status,visibility", [("published", "internal"), ("draft", "public")])
def test_certification_preparation_cannot_bypass_public_install_or_publication(client, status, visibility):
    asset = {**_asset(), "status": status, "visibility": visibility}
    with patch('app.marketplace.marketplace3.certification_routes.shared_service_client'), patch('app.marketplace.marketplace3.certification_routes._fetch_asset', return_value=asset), patch('app.marketplace.service._install_outcome_pack') as install:
        assert client.post('/assets/pack/certification/install').status_code == 409
    install.assert_not_called()


def test_owner_admin_prepares_observe_primitives_without_publishing(client):
    asset = {**_asset(), "status": "draft", "visibility": "internal"}
    with patch('app.marketplace.marketplace3.certification_routes.shared_service_client'), patch('app.marketplace.marketplace3.certification_routes._fetch_asset', return_value=asset), patch('app.marketplace.service._check_plan_limits') as limits, patch('app.marketplace.service._find_active_connector_id', return_value='connector'), patch('app.marketplace.service._install_outcome_pack', return_value={"workflowIds": ["workflow"]}) as install:
        response = client.post('/assets/pack/certification/install')
    assert response.status_code == 200
    assert response.json()['operatingMode'] == 'OBSERVE'
    assert response.json()['publishReady'] is False
    assert install.call_args.kwargs['actor_id'] == 'admin'
    assert install.call_args.kwargs['environment_name'] == 'production'
    assert asset['status'] == 'draft'
    limits.assert_called_once()


def test_incomplete_draft_returns_actionable_conflict_instead_of_server_error(client):
    with patch('app.marketplace.marketplace3.certification_routes.shared_service_client'), patch('app.marketplace.marketplace3.certification_routes._fetch_asset', return_value={**_asset(), "config": {}}):
        assert client.get('/assets/pack/certification').status_code == 409
        assert client.post('/assets/pack/certification/install').status_code == 409



def test_blueprint_catalog_exposes_unique_definitions_without_certification(client):
    response = client.get('/outcome-pack-blueprints')
    assert response.status_code == 200
    rows = response.json()['blueprints']
    assert {'people-it-operations-3', 'executive-command-center-3', 'revenue-operations', 'security-operations'} <= {row['id'] for row in rows}
    assert all(row['publishReady'] is False and row['status'] == 'blueprint' for row in rows)


def test_blueprint_draft_uses_server_registry_and_authenticated_org(client):
    service = MagicMock()
    service.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    with patch('app.marketplace.marketplace3.certification_routes.shared_service_client', return_value=service), patch('app.marketplace.crud.create_org_asset', return_value={"asset": {"id": "new", "status": "draft", "visibility": "private"}}) as create:
        response = client.post('/outcome-pack-blueprints/revenue-operations/draft', json={"org_id": "foreign", "config": {"verified": True}})
    assert response.status_code == 200
    assert create.call_args.args[1] == 'org'
    assert create.call_args.kwargs['actor_id'] == 'admin'
    assert create.call_args.kwargs['config']['marketplace_version'] == '3.0'
    assert 'verified' not in create.call_args.kwargs['config']


def test_unknown_blueprint_never_touches_storage(client):
    with patch('app.marketplace.marketplace3.certification_routes.shared_service_client') as db:
        assert client.post('/outcome-pack-blueprints/unknown/draft').status_code == 404
    db.assert_not_called()


def test_non_admin_cannot_materialize_a_blueprint(client):
    def deny(): raise HTTPException(403, 'Admin required')
    client.app.dependency_overrides[require_admin] = deny
    assert client.get('/outcome-pack-blueprints').status_code == 403
    assert client.post('/outcome-pack-blueprints/revenue-operations/draft').status_code == 403
