"""Fail-closed BE-21 confirmation contracts (no live provider writes)."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.operators import governed_recommendations as mod


class Chain:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []
    def update(self, values):
        self.values = values
        return self
    def eq(self, key, value):
        self.filters.append((key, value))
        return self
    def gt(self, key, value):
        self.filters.append((key, value))
        return self
    def select(self, columns):
        return self
    def execute(self):
        return SimpleNamespace(data=self.rows)


@pytest.mark.parametrize("rows", [[], [{"id": "one"}, {"id": "two"}]])
def test_atomic_claim_fails_closed_without_exactly_one_row(rows):
    chain = Chain(rows)
    client = SimpleNamespace(table=lambda name: chain)
    with pytest.raises(HTTPException) as exc:
        mod._single_claim(client, rec_id="x", org_id="org", operator_type="workflow-param-suggester",
                          status="claimed", user_id="owner")
    assert exc.value.status_code == 409
    assert ("status", "pending") in chain.filters
    assert ("created_by", "owner") in chain.filters
    assert any(k == "expires_at" for k, _ in chain.filters)


def test_atomic_claim_rejects_repeated_confirmation_by_status_predicate():
    chain = Chain([{"id": "rec", "recommendation": {"workflow_id": "w"}}])
    client = SimpleNamespace(table=lambda name: chain)
    result = mod._single_claim(client, rec_id="rec", org_id="org", operator_type="workflow-param-suggester",
                               status="claimed", user_id="owner")
    assert result["id"] == "rec"
    assert chain.values["status"] == "claimed"
    assert ("org_id", "org") in chain.filters


def test_operator_types_are_narrow_allowlist():
    assert mod._ALLOWED_TYPES == {"workflow-param-suggester"}


def test_service_only_schema_prevents_user_approval_forgery():
    from pathlib import Path
    migration = Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "20261022160000_be21_governed_recommendations.sql"
    sql = migration.read_text()
    assert "REVOKE ALL ON TABLE public.operator_recommendations FROM PUBLIC, anon, authenticated" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "CREATE POLICY" not in sql
    assert "org_members" not in sql


@pytest.mark.parametrize(
    "returned, expected_status",
    [
        ({"run_id": "run-pending", "status": "pending_approval"}, "pending_approval"),
        ({"run_id": "run-running", "status": "running"}, "running"),
        ({"run_id": "run-completed", "status": "completed"}, "running"),
    ],
)
def test_execution_acceptance_never_claims_provider_verified(monkeypatch, returned, expected_status):
    """Even canonical executor 'completed' cannot establish independent provider readback here."""
    recommendation = {
        "recommendation": {
            "workflow_id": "81c97e93-5726-434d-8106-cb6a0319cf84",
            "parameters": {},
            "environment": "production",
        }
    }
    monkeypatch.setattr(mod, "_single_claim", lambda *args, **kwargs: recommendation)
    monkeypatch.setattr(mod, "_execute_workflow_with_context", lambda **kwargs: returned)
    client = MagicMock()
    monkeypatch.setattr(mod, "shared_service_client", lambda *args: client)
    result = mod.confirm("workflow-param-suggester", mod.ConfirmationRequest(
        recommendation_id="a4e2ded9-d0b8-4bd4-b709-39c55f01bb6d", confirmed=True
    ), {"user_id": "owner"}, "org", "production", MagicMock())
    assert result["verified"] is False
    assert result["status"] == expected_status
    assert result["status"] != "executed"


def test_rejected_confirmation_never_runs_workflow(monkeypatch):
    monkeypatch.setattr(mod, "_single_claim", lambda *args, **kwargs: {"id": "rec"})
    dispatcher = MagicMock(side_effect=AssertionError("rejection must not dispatch"))
    monkeypatch.setattr(mod, "_execute_workflow_with_context", dispatcher)
    monkeypatch.setattr(mod, "shared_service_client", lambda *args: MagicMock())
    result = mod.confirm("workflow-param-suggester", mod.ConfirmationRequest(
        recommendation_id="a4e2ded9-d0b8-4bd4-b709-39c55f01bb6d", confirmed=False
    ), {"user_id": "owner"}, "org", "production", MagicMock())
    assert result == {
        "recommendation_id": "a4e2ded9-d0b8-4bd4-b709-39c55f01bb6d",
        "status": "rejected", "verified": False,
    }
    dispatcher.assert_not_called()


@pytest.mark.parametrize("dispatch", [
    {"status": "failed", "run_id": "failed-run"},
    {"status": "cancelled", "run_id": "cancelled-run"},
    {"status": "rejected", "run_id": "denied-run"},
    {"status": "running", "run_id": ""},
])
def test_failed_cancelled_or_unrecorded_dispatch_is_never_success(monkeypatch, dispatch):
    monkeypatch.setattr(mod, "_single_claim", lambda *args, **kwargs: {
        "recommendation": {
            "workflow_id": "81c97e93-5726-434d-8106-cb6a0319cf84",
            "parameters": {},
            "environment": "production",
        }
    })
    monkeypatch.setattr(mod, "_execute_workflow_with_context", lambda **kwargs: dispatch)
    monkeypatch.setattr(mod, "shared_service_client", lambda *args: MagicMock())
    with pytest.raises(HTTPException) as err:
        mod.confirm("workflow-param-suggester", mod.ConfirmationRequest(
            recommendation_id="a4e2ded9-d0b8-4bd4-b709-39c55f01bb6d", confirmed=True
        ), {"user_id": "owner"}, "org", "production", MagicMock())
    assert err.value.status_code in (409, 503)


def test_interrupted_or_unknown_execution_keeps_claim_for_manual_reconciliation(monkeypatch):
    monkeypatch.setattr(mod, "_single_claim", lambda *args, **kwargs: {
        "recommendation": {
            "workflow_id": "81c97e93-5726-434d-8106-cb6a0319cf84",
            "parameters": {}, "environment": "production",
        }
    })
    monkeypatch.setattr(mod, "_execute_workflow_with_context",
                        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("network interruption")))
    monkeypatch.setattr(mod, "shared_service_client", lambda *args: MagicMock())
    with pytest.raises(HTTPException) as err:
        mod.confirm("workflow-param-suggester", mod.ConfirmationRequest(
            recommendation_id="a4e2ded9-d0b8-4bd4-b709-39c55f01bb6d", confirmed=True
        ), {"user_id": "owner"}, "org", "production", MagicMock())
    assert err.value.status_code == 503
    assert "uncertain" in err.value.detail
