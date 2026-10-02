from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.auth.dependencies import get_org_context, require_admin, require_platform_admin
from app.config import Settings, get_settings
from app.main import app
from app.marketplace.marketplace3.certification import OutcomePackCertification


client = TestClient(app)
ORG_ID = "22222222-2222-2222-2222-222222222222"


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


def _deny() -> None:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def _asset() -> dict:
    return {
        "id": "11111111-1111-1111-1111-111111111111",
        "org_id": ORG_ID,
        "asset_type": "outcome_pack",
        "status": "draft",
        "current_version": 1,
        "config": {},
    }


def test_certification_summary_requires_org_admin() -> None:
    app.dependency_overrides[require_admin] = _deny
    app.dependency_overrides[get_settings] = _settings
    response = client.get("/api/marketplace/assets/test-pack/certification")
    assert response.status_code == 403


def test_platform_runtime_evidence_requires_platform_admin() -> None:
    app.dependency_overrides[require_platform_admin] = _deny
    app.dependency_overrides[get_settings] = _settings
    response = client.post(
        "/api/marketplace/platform/assets/test-pack/certification/runtime-evidence",
        json={
            "provider": "freshservice",
            "environment": "production",
            "evidenceRef": "workflow_run:smoke-1",
            "verifiedActions": ["freshservice.tickets.get"],
        },
    )
    assert response.status_code == 403


def test_org_admin_certification_summary_hides_raw_evidence_refs(monkeypatch) -> None:
    app.dependency_overrides[require_admin] = lambda: ({"user_id": "admin-1"}, ORG_ID)
    app.dependency_overrides[get_settings] = _settings
    monkeypatch.setattr("app.routers.marketplace.create_client", lambda *_a, **_k: MagicMock())
    monkeypatch.setattr("app.routers.marketplace.fetch_marketplace_asset", lambda *_a, **_k: _asset())
    monkeypatch.setattr(
        "app.routers.marketplace.certification_report_for_asset",
        lambda *_a, **_k: OutcomePackCertification(
            level="production_verified",
            publish_ready=True,
            findings=[],
            play_count=8,
            runtime_actions=["freshservice.tickets.get"],
            verified_skills=[],
            unresolved_skill_requirements=[],
        ),
    )
    monkeypatch.setattr(
        "app.routers.marketplace.list_runtime_evidence",
        lambda *_a, **_k: {
            "freshservice": {
                "environment": "production",
                "evidence_ref": "secret-proof-reference",
                "verified_actions": ["freshservice.tickets.get"],
            }
        },
    )

    response = client.get("/api/marketplace/assets/test-pack/certification")
    assert response.status_code == 200
    body = response.json()
    assert body["certification"]["level"] == "production_verified"
    assert body["runtimeEvidence"]["freshservice"]["hasEvidence"] is True
    assert "evidence_ref" not in body["runtimeEvidence"]["freshservice"]
    assert "secret-proof-reference" not in response.text


def test_platform_admin_can_record_runtime_evidence(monkeypatch) -> None:
    app.dependency_overrides[require_platform_admin] = lambda: {"user_id": "platform-1"}
    app.dependency_overrides[get_org_context] = lambda: ORG_ID
    app.dependency_overrides[get_settings] = _settings
    monkeypatch.setattr("app.routers.marketplace.create_client", lambda *_a, **_k: MagicMock())
    monkeypatch.setattr("app.routers.marketplace.fetch_marketplace_asset", lambda *_a, **_k: _asset())
    monkeypatch.setattr(
        "app.routers.marketplace.record_runtime_evidence",
        lambda *_a, **_k: {
            "evidence": {"id": "evidence-1"},
            "certification": {"level": "production_verified", "publishReady": True},
        },
    )
    monkeypatch.setattr("app.routers.marketplace.write_audit_event", lambda *_a, **_k: None)

    response = client.post(
        "/api/marketplace/platform/assets/test-pack/certification/runtime-evidence",
        json={
            "provider": "freshservice",
            "environment": "production",
            "evidenceRef": "workflow_run:smoke-1",
            "verifiedActions": ["freshservice.tickets.get"],
        },
    )
    assert response.status_code == 200
    assert response.json()["certification"]["level"] == "production_verified"
