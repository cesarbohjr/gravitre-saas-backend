"""The smoke plan fixture only ever touches the isolated smoke org's own billing row."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
_spec = importlib.util.spec_from_file_location(
    "isolated_conversation_org", REPO / "scripts" / "isolated_conversation_org.py"
)
iso = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(iso)

SMOKE_ORG = iso.DEFAULT_ISOLATED_CONVERSATION_TEST_ORG_ID


class _Query:
    def __init__(self, db: _FakeDb, table: str) -> None:
        self.db, self.table, self.op, self.payload = db, table, "select", None

    def select(self, *_a: Any) -> _Query:
        return self

    def eq(self, *_a: Any) -> _Query:
        return self

    def limit(self, *_a: Any) -> _Query:
        return self

    def update(self, payload: dict) -> _Query:
        self.op, self.payload = "update", payload
        return self

    def insert(self, payload: dict) -> _Query:
        self.op, self.payload = "insert", payload
        return self

    def execute(self) -> Any:
        if self.op != "select":
            self.db.writes.append((self.table, self.op, self.payload))
            return type("R", (), {"data": [self.payload]})()
        return type("R", (), {"data": list(self.db.rows.get(self.table, []))})()


class _FakeDb:
    def __init__(self, rows: dict[str, list[dict]]) -> None:
        self.rows = rows
        self.writes: list[tuple[str, str, dict]] = []

    def table(self, name: str) -> _Query:
        return _Query(self, name)


def _marked_org() -> dict[str, list[dict]]:
    return {"organizations": [{"settings": {"isolated_conversation_test_org": True}}]}


@pytest.fixture(autouse=True)
def _default_org(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ISOLATED_CONVERSATION_TEST_ORG_ID", raising=False)


def test_refuses_any_org_other_than_the_isolated_smoke_org() -> None:
    db = _FakeDb(_marked_org())
    with pytest.raises(iso.ConversationWriteBlockedError):
        iso.ensure_isolated_smoke_plan(db, "cbbf993b-b22f-41ce-964b-1fc25e0dd9ea")
    assert db.writes == []


def test_refuses_an_org_not_marked_as_the_smoke_fixture() -> None:
    db = _FakeDb({"organizations": [{"settings": {}}]})
    with pytest.raises(iso.ConversationWriteBlockedError):
        iso.ensure_isolated_smoke_plan(db, SMOKE_ORG)
    assert db.writes == []


def test_refuses_a_row_with_a_stripe_subscription() -> None:
    rows = _marked_org() | {
        "org_billing": [{"plan_code": "node", "stripe_subscription_id": "sub_123"}]
    }
    db = _FakeDb(rows)
    with pytest.raises(iso.ConversationWriteBlockedError):
        iso.ensure_isolated_smoke_plan(db, SMOKE_ORG)
    assert db.writes == []


def test_creates_the_control_row_when_missing_and_is_a_no_op_once_set() -> None:
    db = _FakeDb(_marked_org())
    assert iso.ensure_isolated_smoke_plan(db, SMOKE_ORG) == "control"
    assert db.writes == [
        (
            "org_billing",
            "insert",
            {"org_id": SMOKE_ORG, "plan_code": "control", "billing_status": "active"},
        )
    ]

    db = _FakeDb(
        _marked_org()
        | {"org_billing": [{"plan_code": "control", "billing_status": "active"}]}
    )
    iso.ensure_isolated_smoke_plan(db, SMOKE_ORG)
    assert db.writes == []


def test_upgrades_an_existing_default_plan_row() -> None:
    db = _FakeDb(
        _marked_org()
        | {"org_billing": [{"plan_code": "node", "billing_status": "trialing"}]}
    )
    iso.ensure_isolated_smoke_plan(db, SMOKE_ORG)
    assert db.writes == [
        ("org_billing", "update", {"plan_code": "control", "billing_status": "active"})
    ]
