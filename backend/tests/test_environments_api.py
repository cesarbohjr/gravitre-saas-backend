"""Environments API: stage list with resource counts, create guard, delete."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.billing.service import DEFAULT_PLANS
from tests.support.build_insights import authenticate, chain_mock, clear_overrides, client, table_client

PROD_ID = "00000000-0000-0000-0000-00000000e001"
STAGING_ID = "00000000-0000-0000-0000-00000000e002"


@pytest.fixture(autouse=True)
def _reset_deps():
    yield
    clear_overrides()


def _count_chain(count: int) -> MagicMock:
    chain = chain_mock(data=[])
    chain.execute.return_value = SimpleNamespace(data=[], count=count, error=None)
    return chain


@patch("app.routers.environments.get_plan_for_org", return_value=DEFAULT_PLANS["node"])
@patch("app.routers.environments.create_client")
@patch("app.services.org_membership.ensure_default_production_environment")
def test_list_shapes_stages_with_counts(_ensure, mock_create, _plan):
    envs = [
        {"id": PROD_ID, "name": "production", "is_active": True, "created_at": "2026-10-01T00:00:00Z"},
        {"id": STAGING_ID, "name": "staging", "is_active": False, "created_at": "2026-10-02T00:00:00Z"},
    ]
    mock_create.return_value = table_client(
        {
            "environments": chain_mock(data=envs),
            "workflow_defs": _count_chain(3),
            "operators": _count_chain(2),
            "connectors": _count_chain(0),
            "rag_sources": _count_chain(5),
        }
    )
    authenticate()
    response = client.get("/api/environments")
    assert response.status_code == 200
    body = response.json()
    assert body["stages"] == ["development", "staging", "production"]
    names = [env["name"] for env in body["environments"]]
    assert names == ["staging", "production"]
    prod = body["environments"][1]
    assert prod["is_default"] is True
    assert prod["is_active"] is True
    assert prod["resources"] == {"workflows": 3, "agents": 2, "connectors": 0, "sources": 5}
    staging = body["environments"][0]
    assert staging["is_default"] is False
    assert staging["is_active"] is False
    assert body["environmentsLimit"] == DEFAULT_PLANS["node"].get("environments_limit")


@patch("app.routers.environments.get_plan_for_org", return_value=DEFAULT_PLANS["node"])
@patch("app.routers.environments.create_client")
@patch("app.services.org_membership.ensure_default_production_environment")
def test_list_reports_none_when_counts_fail(_ensure, mock_create, _plan):
    broken = chain_mock(data=[])
    broken.execute.side_effect = RuntimeError("column environment_id does not exist")
    mock_create.return_value = table_client(
        {
            "environments": chain_mock(data=[{"id": PROD_ID, "name": "default", "is_active": True}]),
            "workflow_defs": broken,
            "operators": broken,
            "connectors": broken,
            "rag_sources": broken,
        }
    )
    authenticate()
    env = client.get("/api/environments").json()["environments"][0]
    assert env["is_default"] is True  # legacy "default" plays the production role
    assert env["resources"] == {"workflows": None, "agents": None, "connectors": None, "sources": None}


@patch("app.routers.environments.write_audit_event")
@patch("app.routers.environments.create_client")
def test_create_rejects_existing_stage(mock_create, _audit):
    mock_create.return_value = table_client(
        {"environments": chain_mock(data=[{"id": PROD_ID, "name": "production"}])}
    )
    authenticate(as_admin=True)
    response = client.post("/api/environments", json={"name": "Production"})
    assert response.status_code == 409


@patch("app.routers.environments.write_audit_event")
@patch("app.routers.environments.create_client")
def test_delete_refuses_production(mock_create, _audit):
    mock_create.return_value = table_client(
        {"environments": chain_mock(data=[{"id": PROD_ID, "name": "production"}])}
    )
    authenticate(as_admin=True)
    response = client.delete(f"/api/environments/{PROD_ID}")
    assert response.status_code == 409
    _audit.assert_not_called()


@patch("app.routers.environments.write_audit_event")
@patch("app.routers.environments.create_client")
def test_delete_removes_staging_and_audits(mock_create, mock_audit):
    envs = chain_mock(data=[{"id": STAGING_ID, "name": "staging"}])
    mock_create.return_value = table_client({"environments": envs})
    authenticate(as_admin=True)
    response = client.delete(f"/api/environments/{STAGING_ID}")
    assert response.status_code == 200
    assert response.json() == {"id": STAGING_ID, "deleted": True}
    assert mock_audit.call_args.kwargs["action"] == "environment.deleted"


@patch("app.routers.environments.create_client")
def test_delete_requires_admin(mock_create):
    from fastapi import HTTPException

    from app.auth.dependencies import require_admin
    from app.main import app

    def _deny():
        raise HTTPException(status_code=403, detail="Admin role required")

    mock_create.return_value = table_client({"environments": chain_mock(data=[])})
    authenticate()
    app.dependency_overrides[require_admin] = _deny
    response = client.delete(f"/api/environments/{STAGING_ID}")
    assert response.status_code == 403
