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
