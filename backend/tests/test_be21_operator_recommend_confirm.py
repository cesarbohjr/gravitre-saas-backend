"""Tests for BE-21: POST /api/operators/:type/recommend and :type/confirm.

Covers:
- recommend returns a recommendation_id and audit event
- unknown operator type → 422
- confirm happy path (confirmed=True) → status executed
- confirm rejection (confirmed=False) → status rejected
- confirm with wrong recommendation_id (wrong org) → 404
- confirm already-processed recommendation → 400
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_supabase_client(
    recommendation_id: str = "rec-1",
    existing_rec: dict | None = None,
    insert_raises: bool = False,
    select_raises: bool = False,
    update_raises: bool = False,
) -> MagicMock:
    """Build a minimal MagicMock supabase client for operator_recommendations."""
    client = MagicMock()

    # table("operator_recommendations").insert(...).execute()
    insert_result = MagicMock()
    insert_result.data = [
        {
            "id": recommendation_id,
            "org_id": "org-1",
            "operator_type": "draft-assistant",
            "status": "pending",
            "expires_at": "2099-01-01T00:00:00+00:00",
        }
    ]

    def _insert(*args, **kwargs):
        if insert_raises:
            raise RuntimeError("db error")
        return MagicMock(execute=MagicMock(return_value=insert_result))

    # table("operator_recommendations").select(...).eq(...).eq(...).eq(...).limit(...).execute()
    select_result = MagicMock()
    select_result.data = [existing_rec] if existing_rec else []

    def _select(*args, **kwargs):
        if select_raises:
            raise RuntimeError("db select error")
        eq_mock = MagicMock()
        eq_mock.eq.return_value = eq_mock
        eq_mock.limit.return_value = MagicMock(execute=MagicMock(return_value=select_result))
        return eq_mock

    # table("operator_recommendations").update(...).eq(...).eq(...).execute()
    update_result = MagicMock()
    update_result.data = [{"id": recommendation_id}]

    def _update(*args, **kwargs):
        if update_raises:
            raise RuntimeError("db update error")
        eq_mock = MagicMock()
        eq_mock.eq.return_value = eq_mock
        eq_mock.execute.return_value = update_result
        return eq_mock

    # table("audit_events").insert(...).execute()  — used by write_audit_event
    audit_result = MagicMock()
    audit_result.data = [{"id": "audit-1"}]
    audit_chain = MagicMock(execute=MagicMock(return_value=audit_result))

    def _table(name: str):
        tbl = MagicMock()
        tbl.insert.side_effect = _insert
        tbl.select.side_effect = _select
        tbl.update.side_effect = _update
        return tbl

    client.table.side_effect = _table
    return client


def _make_app() -> FastAPI:
    from app.operators.router import router
    from app.auth.dependencies import get_current_user, get_org_context
    from app.config import get_settings

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user-1"}
    app.dependency_overrides[get_org_context] = lambda: "org-1"
    app.dependency_overrides[get_settings] = lambda: MagicMock()
    return app


# ---------------------------------------------------------------------------
# recommend endpoint
# ---------------------------------------------------------------------------


def test_recommend_happy_path() -> None:
    """POST /{operator_type}/recommend returns recommendation_id and rationale."""
    app = _make_app()
    with (
        patch("app.operators.router.shared_service_client") as mk_client,
        patch("app.operators.router.write_audit_event") as _mk_audit,
    ):
        mk_client.return_value = _make_supabase_client(recommendation_id="rec-abc")
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post(
            "/api/operators/draft-assistant/recommend",
            json={"context": {"entity_id": "e-1"}, "prompt": "suggest a draft"},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["recommendation_id"] == "rec-abc"
    assert data["operator_type"] == "draft-assistant"
    assert "action" in data
    assert "rationale" in data


def test_recommend_unknown_type_returns_422() -> None:
    """Unknown operator type → 422 with informative message."""
    app = _make_app()
    with patch("app.operators.router.shared_service_client") as mk_client:
        mk_client.return_value = _make_supabase_client()
        client = TestClient(app)
        resp = client.post(
            "/api/operators/nonexistent-type/recommend",
            json={"context": {}},
        )
    assert resp.status_code == 422
    assert "nonexistent-type" in resp.json()["detail"]


def test_recommend_db_failure_returns_500() -> None:
    """DB insert failure → 500."""
    app = _make_app()
    with (
        patch("app.operators.router.shared_service_client") as mk_client,
        patch("app.operators.router.write_audit_event"),
    ):
        mk_client.return_value = _make_supabase_client(insert_raises=True)
        client = TestClient(app)
        resp = client.post(
            "/api/operators/draft-assistant/recommend",
            json={"context": {}},
        )
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# confirm endpoint
# ---------------------------------------------------------------------------


def test_confirm_happy_path_confirmed() -> None:
    """confirmed=True → status 'executed' and result payload."""
    existing_rec = {
        "id": "rec-1",
        "org_id": "org-1",
        "operator_type": "draft-assistant",
        "status": "pending",
        "recommendation": {"action": "draft-assistant.suggest", "payload": {}, "rationale": "r"},
        "expires_at": "2099-01-01T00:00:00+00:00",
    }
    app = _make_app()
    with (
        patch("app.operators.router.shared_service_client") as mk_client,
        patch("app.operators.router.write_audit_event"),
    ):
        mk_client.return_value = _make_supabase_client(existing_rec=existing_rec)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post(
            "/api/operators/draft-assistant/confirm",
            json={"recommendation_id": "rec-1", "confirmed": True},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "executed"
    assert data["result"]["executed"] is True
    assert data["recommendation_id"] == "rec-1"


def test_confirm_rejection() -> None:
    """confirmed=False → status 'rejected' and no result."""
    existing_rec = {
        "id": "rec-2",
        "org_id": "org-1",
        "operator_type": "draft-assistant",
        "status": "pending",
        "recommendation": {"action": "draft-assistant.suggest"},
        "expires_at": "2099-01-01T00:00:00+00:00",
    }
    app = _make_app()
    with (
        patch("app.operators.router.shared_service_client") as mk_client,
        patch("app.operators.router.write_audit_event"),
    ):
        mk_client.return_value = _make_supabase_client(recommendation_id="rec-2", existing_rec=existing_rec)
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.post(
            "/api/operators/draft-assistant/confirm",
            json={"recommendation_id": "rec-2", "confirmed": False},
        )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["result"] is None


def test_confirm_not_found_returns_404() -> None:
    """No matching recommendation → 404."""
    app = _make_app()
    with (
        patch("app.operators.router.shared_service_client") as mk_client,
        patch("app.operators.router.write_audit_event"),
    ):
        # existing_rec=None → empty rows
        mk_client.return_value = _make_supabase_client(existing_rec=None)
        client = TestClient(app)
        resp = client.post(
            "/api/operators/draft-assistant/confirm",
            json={"recommendation_id": "rec-missing", "confirmed": True},
        )
    assert resp.status_code == 404


def test_confirm_already_processed_returns_400() -> None:
    """Recommendation already 'executed' → 400."""
    existing_rec = {
        "id": "rec-3",
        "org_id": "org-1",
        "operator_type": "draft-assistant",
        "status": "executed",  # already processed
        "recommendation": {"action": "draft-assistant.suggest"},
        "expires_at": "2099-01-01T00:00:00+00:00",
    }
    app = _make_app()
    with (
        patch("app.operators.router.shared_service_client") as mk_client,
        patch("app.operators.router.write_audit_event"),
    ):
        mk_client.return_value = _make_supabase_client(recommendation_id="rec-3", existing_rec=existing_rec)
        client = TestClient(app)
        resp = client.post(
            "/api/operators/draft-assistant/confirm",
            json={"recommendation_id": "rec-3", "confirmed": True},
        )
    assert resp.status_code == 400
    assert "executed" in resp.json()["detail"]


def test_confirm_unknown_operator_type_returns_422() -> None:
    """Unknown operator type on confirm → 422."""
    app = _make_app()
    with patch("app.operators.router.shared_service_client"):
        client = TestClient(app)
        resp = client.post(
            "/api/operators/mystery-type/confirm",
            json={"recommendation_id": "rec-1", "confirmed": True},
        )
    assert resp.status_code == 422


def test_confirm_expired_recommendation_returns_400() -> None:
    """Expired recommendation (expires_at in the past) → 400."""
    existing_rec = {
        "id": "rec-4",
        "org_id": "org-1",
        "operator_type": "draft-assistant",
        "status": "pending",
        "recommendation": {"action": "draft-assistant.suggest"},
        "expires_at": "2000-01-01T00:00:00+00:00",  # expired
    }
    app = _make_app()
    with (
        patch("app.operators.router.shared_service_client") as mk_client,
        patch("app.operators.router.write_audit_event"),
    ):
        mk_client.return_value = _make_supabase_client(recommendation_id="rec-4", existing_rec=existing_rec)
        client = TestClient(app)
        resp = client.post(
            "/api/operators/draft-assistant/confirm",
            json={"recommendation_id": "rec-4", "confirmed": True},
        )
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()
