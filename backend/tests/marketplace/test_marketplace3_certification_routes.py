from unittest.mock import MagicMock, patch
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
