"""MKT-9.4: Marketplace asset version list + rollback."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_environment_context, get_org_context, require_admin
from app.config import Settings, get_settings
from app.main import app
from app.marketplace.schemas import MarketplaceValidationError
from app.marketplace.versions import MarketplaceVersionError, list_asset_versions, rollback_asset_version

client = TestClient(app)

ASSET_ID = "11111111-1111-1111-1111-111111111111"
ORG_ID = "org-1"


def _settings() -> Settings:
    return Settings(
        app_env="dev",
        supabase_url="https://test.supabase.co",
        supabase_anon_key="anon-test",
        supabase_service_role_key="service-role-test",
        supabase_jwt_secret="jwt-secret-test",
    )


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _authenticate_admin(org_id: str = ORG_ID) -> None:
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: org_id
    app.dependency_overrides[get_settings] = lambda: _settings()
    app.dependency_overrides[get_environment_context] = lambda: "production"
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "user-1"}, org_id)


def _table(select_data: list | None = None) -> MagicMock:
    mock = MagicMock()
    mock.select.return_value = mock
    mock.eq.return_value = mock
    mock.limit.return_value = mock
    mock.order.return_value = mock
    mock.update.return_value = mock
    mock.execute.return_value = MagicMock(data=select_data or [])
    return mock


def _org_asset(*, current_version: int = 3) -> dict:
    return {
        "id": ASSET_ID,
        "slug": "custom-agent",
        "org_id": ORG_ID,
        "asset_type": "ai_agent",
        "current_version": current_version,
        "config": {"name": "Current"},
        "required_connectors": [],
        "install_variables": [],
    }


def _version_row(version_number: int, *, name: str) -> dict:
    return {
        "asset_id": ASSET_ID,
        "version_number": version_number,
        "config": {"name": name, "purpose": "Restored"},
        "required_connectors": [],
        "required_permissions": [],
        "install_variables": [],
        "change_summary": f"v{version_number}",
        "published_at": "2026-06-01T00:00:00Z",
    }


@patch("app.marketplace.versions.write_audit_event")
@patch("app.marketplace.versions.validate_asset_payload")
def test_rollback_asset_version_restores_snapshot(mock_validate, mock_audit):
    mock_validate.return_value = {
        "config": {"name": "V2 Agent", "purpose": "Restored"},
        "required_connectors": [],
        "install_variables": [],
    }
    asset = _org_asset(current_version=3)
    assets = _table([asset])
    versions = _table([_version_row(2, name="V2 Agent")])
    assets.update.return_value = assets
    assets.execute.side_effect = [
        MagicMock(data=[asset]),
        MagicMock(data=[]),
    ]
    versions.execute.return_value = MagicMock(data=[_version_row(2, name="V2 Agent")])

    supabase = MagicMock()

    def table(name):
        if name == "marketplace_assets":
            return assets
        if name == "marketplace_asset_versions":
            return versions
        return _table([])

    supabase.table.side_effect = table

    result = rollback_asset_version(
        supabase,
        ORG_ID,
        "custom-agent",
        version_number=2,
        actor_id="user-1",
    )

    assert result["rolledBack"] is True
    assert result["previousVersion"] == 3
    assert result["currentVersion"] == 2
    update_payload = assets.update.call_args.args[0]
    assert update_payload["current_version"] == 2
    assert update_payload["config"]["name"] == "V2 Agent"
    mock_audit.assert_called_once()


def test_rollback_rejects_catalog_asset_without_org():
    asset = {**_org_asset(), "org_id": None}
    assets = _table([asset])
    client_mock = MagicMock()
    client_mock.table.return_value = assets

    with pytest.raises(MarketplaceVersionError) as exc:
        rollback_asset_version(
            client_mock,
            ORG_ID,
            ASSET_ID,
            version_number=1,
            actor_id="user-1",
        )
    assert exc.value.code == "FORBIDDEN"


def test_rollback_rejects_already_current_version():
    asset = _org_asset(current_version=2)
    assets = _table([asset])
    client_mock = MagicMock()
    client_mock.table.return_value = assets

    with pytest.raises(MarketplaceVersionError) as exc:
        rollback_asset_version(
            client_mock,
            ORG_ID,
            ASSET_ID,
            version_number=2,
            actor_id="user-1",
        )
    assert exc.value.code == "ALREADY_CURRENT"


@patch("app.marketplace.versions.validate_asset_payload")
def test_rollback_rejects_invalid_restored_config(mock_validate):
    mock_validate.side_effect = MarketplaceValidationError(
        "invalid config",
        errors=["forbidden_secret:config.api_key"],
    )
    asset = _org_asset(current_version=3)
    assets = _table([asset])
    versions = _table([_version_row(1, name="Bad")])
    client_mock = MagicMock()

    def table(name):
        if name == "marketplace_assets":
            return assets
        if name == "marketplace_asset_versions":
            return versions
        return _table([])

    client_mock.table.side_effect = table

    with pytest.raises(MarketplaceVersionError) as exc:
        rollback_asset_version(
            client_mock,
            ORG_ID,
            ASSET_ID,
            version_number=1,
            actor_id="user-1",
        )
    assert exc.value.code == "VALIDATION_ERROR"


def test_list_asset_versions_marks_current():
    asset = _org_asset(current_version=2)
    assets = _table([asset])
    versions = _table(
        [
            {"version_number": 2, "change_summary": "Latest", "published_at": "t2", "published_by": "u1"},
            {"version_number": 1, "change_summary": "Initial", "published_at": "t1", "published_by": "u1"},
        ]
    )
    client_mock = MagicMock()

    def table(name):
        if name == "marketplace_assets":
            return assets
        if name == "marketplace_asset_versions":
            return versions
        return _table([])

    client_mock.table.side_effect = table

    result = list_asset_versions(client_mock, ORG_ID, "custom-agent")
    assert result["currentVersion"] == 2
    assert result["versions"][0]["isCurrent"] is True
    assert result["versions"][1]["isCurrent"] is False


def test_list_versions_route_requires_org():
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1", "email": "u@example.com"}
    app.dependency_overrides[get_org_context] = lambda: None
    app.dependency_overrides[get_settings] = lambda: _settings()
    response = client.get(f"/api/marketplace/assets/{ASSET_ID}/versions")
    assert response.status_code == 403


def test_list_versions_route_returns_history(monkeypatch):
    _authenticate_admin()
    sample = {
        "assetId": ASSET_ID,
        "slug": "custom-agent",
        "currentVersion": 2,
        "versions": [{"versionNumber": 2, "isCurrent": True}],
    }
    monkeypatch.setattr(
        "app.routers.marketplace.list_asset_versions",
        lambda *_a, **_k: sample,
    )
    response = client.get(f"/api/marketplace/assets/{ASSET_ID}/versions")
    assert response.status_code == 200
    assert response.json()["currentVersion"] == 2


def test_rollback_route_returns_payload(monkeypatch):
    _authenticate_admin()
    sample = {
        "rolledBack": True,
        "assetId": ASSET_ID,
        "slug": "custom-agent",
        "previousVersion": 3,
        "currentVersion": 2,
        "restoredFromVersion": 2,
    }
    monkeypatch.setattr(
        "app.routers.marketplace.rollback_asset_version",
        lambda *_a, **_k: sample,
    )
    response = client.post(
        f"/api/marketplace/assets/{ASSET_ID}/rollback",
        json={"version": 2},
    )
    assert response.status_code == 200
    assert response.json()["currentVersion"] == 2
