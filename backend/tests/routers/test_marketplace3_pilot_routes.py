from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.auth.dependencies import get_current_user, require_platform_admin, get_environment_context
from app.config import Settings, get_settings

ORG = "00000000-0000-0000-0000-000000000001"
URL = "/api/marketplace/platform/assets/msp-service-desk-3/marketplace3/install-pilot"


@pytest.fixture(autouse=True)
def setup():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "platform-1"}
    app.dependency_overrides[require_platform_admin] = lambda: {"user_id": "platform-1"}
    app.dependency_overrides[get_environment_context] = lambda: "production"
    app.dependency_overrides[get_settings] = lambda: Settings(app_env="dev", supabase_url="https://test.supabase.co", supabase_anon_key="test", supabase_service_role_key="test", supabase_jwt_secret="test")
    yield
    app.dependency_overrides.clear()


def test_pilot_route_requires_platform_admin(monkeypatch):
    def deny():
        raise HTTPException(status_code=403, detail="Platform admin required")
    app.dependency_overrides[require_platform_admin] = deny
    install = MagicMock()
    monkeypatch.setattr("app.routers.marketplace.install_asset", install)
    response = TestClient(app).post(URL, json={"orgId": ORG})
    assert response.status_code == 403
    install.assert_not_called()


def test_pilot_route_uses_explicit_tenant_and_guarded_install(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr("app.routers.marketplace.create_client", lambda *_a: db)
    install = MagicMock(return_value={"installed": True, "entities": {"pilot": True}})
    monkeypatch.setattr("app.routers.marketplace.install_asset", install)
    response = TestClient(app).post(URL, json={"orgId": ORG, "installVariables": {}})
    assert response.status_code == 200
    assert response.json()["entities"]["pilot"] is True
    assert install.call_args.args == (db, ORG, "msp-service-desk-3")
    assert install.call_args.kwargs["_draft_pilot"] is True
    assert install.call_args.kwargs["actor_id"] == "platform-1"
    assert install.call_args.kwargs["environment_name"] == "production"


@pytest.mark.parametrize("body", [{}, {"orgId": "invalid"}, {"orgId": ORG, "force": True}])
def test_pilot_requires_tenant_and_rejects_force(body, monkeypatch):
    install = MagicMock()
    monkeypatch.setattr("app.routers.marketplace.install_asset", install)
    response = TestClient(app).post(URL, json=body)
    assert response.status_code == 422
    install.assert_not_called()


def test_portfolio_readiness_uses_live_client_and_requires_admin(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr("app.routers.marketplace.create_client", lambda *_a: db)
    report = MagicMock(return_value={"source": "deployed_catalog", "packCount": 8})
    monkeypatch.setattr("app.routers.marketplace.portfolio_readiness_report", report)
    url = "/api/marketplace/platform/marketplace3/portfolio-readiness"
    response = TestClient(app).get(url)
    assert response.status_code == 200
    report.assert_called_once_with(db)
    def deny():
        raise HTTPException(status_code=403, detail="Platform admin required")
    app.dependency_overrides[require_platform_admin] = deny
    assert TestClient(app).get(url).status_code == 403
    assert report.call_count == 1
