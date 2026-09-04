from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from app.services.work_object_service import (
    infer_work_object_department,
    infer_work_object_type,
    record_execution_work_object,
)


class _Table:
    def __init__(self, name: str, store: dict[str, list[dict[str, Any]]]) -> None:
        self.name = name
        self.store = store
        self._payload: dict[str, Any] | None = None
        self._filters: list[tuple[str, Any, str]] = []
        self._limit: int | None = None
        self._order_key: str | None = None
        self._order_desc = False

    def select(self, *_cols: str) -> "_Table":
        return self

    def insert(self, payload: dict[str, Any]) -> "_Table":
        self._payload = dict(payload)
        return self

    def update(self, payload: dict[str, Any]) -> "_Table":
        self._payload = dict(payload)
        return self

    def eq(self, key: str, value: Any) -> "_Table":
        self._filters.append((key, value, "eq"))
        return self

    def neq(self, key: str, value: Any) -> "_Table":
        self._filters.append((key, value, "neq"))
        return self

    def order(self, key: str, desc: bool = False) -> "_Table":
        self._order_key = key
        self._order_desc = desc
        return self

    def limit(self, value: int) -> "_Table":
        self._limit = value
        return self

    def execute(self) -> MagicMock:
        rows = list(self.store.get(self.name, []))
        if self._payload is not None:
            if self.name == "work_objects" and any(
                op == "eq" and key == "id" for key, _value, op in self._filters
            ):
                filtered = self._filtered_rows(rows)
                if filtered:
                    target_id = filtered[0]["id"]
                    updated = []
                    for row in rows:
                        if row.get("id") == target_id:
                            next_row = dict(row)
                            next_row.update(self._payload)
                            updated.append(next_row)
                        else:
                            updated.append(row)
                    self.store[self.name] = updated
                    out = filtered[0].copy()
                    out.update(self._payload)
                    result = MagicMock()
                    result.data = [out]
                    return result
            payload = dict(self._payload)
            payload.setdefault("id", f"{self.name}-{len(rows) + 1}")
            self.store.setdefault(self.name, []).append(payload)
            result = MagicMock()
            result.data = [payload]
            return result
        filtered = self._filtered_rows(rows)
        if self._order_key:
            filtered.sort(key=lambda row: str(row.get(self._order_key) or ""), reverse=self._order_desc)
        if self._limit is not None:
            filtered = filtered[: self._limit]
        result = MagicMock()
        result.data = filtered
        return result

    def _filtered_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        filtered = rows
        for key, value, op in self._filters:
            if op == "eq":
                filtered = [row for row in filtered if row.get(key) == value]
            else:
                filtered = [row for row in filtered if row.get(key) != value]
        return filtered


class _Client:
    def __init__(self) -> None:
        self.store: dict[str, list[dict[str, Any]]] = {
            "work_objects": [],
            "work_object_events": [],
        }

    def table(self, name: str) -> _Table:
        return _Table(name, self.store)


def test_infer_work_object_type_and_department() -> None:
    assert infer_work_object_type(entity_type="deal", invoke_action=None) == "opportunity"
    assert infer_work_object_type(entity_type="ticket", invoke_action=None) == "ticket"
    assert infer_work_object_type(entity_type=None, invoke_action="github.create_pull_request") == "issue_pr"
    assert infer_work_object_department("campaign") == "marketing"
    assert infer_work_object_department("vulnerability") == "security"


def test_record_execution_work_object_creates_and_appends_events() -> None:
    client = _Client()
    first = record_execution_work_object(
        client,
        org_id="org-1",
        run_id="run-1",
        terminal_status="completed",
        metadata={
            "invoke_action": "hubspot.create_deal",
            "integration": "hubspot",
            "conversation_id": "conv-1",
            "goal": "Advance Q4 expansion opportunity",
        },
        verified_output={
            "entity_type": "deal",
            "entity_id": "deal-42",
            "summary": "Created deal in HubSpot",
            "integration": "hubspot",
        },
        actor_id="user-1",
        workflow_id="wf-1",
    )
    second = record_execution_work_object(
        client,
        org_id="org-1",
        run_id="run-2",
        terminal_status="completed",
        metadata={
            "invoke_action": "hubspot.update_deal",
            "integration": "hubspot",
            "conversation_id": "conv-1",
        },
        verified_output={
            "entity_type": "deal",
            "entity_id": "deal-42",
            "summary": "Updated deal stage",
            "integration": "hubspot",
        },
        actor_id="user-1",
        workflow_id="wf-1",
    )

    assert first is not None
    assert second is not None
    assert first["work_object_id"] == second["work_object_id"]
    assert len(client.store["work_objects"]) == 1
    assert len(client.store["work_object_events"]) == 2
    row = client.store["work_objects"][0]
    assert row["object_type"] == "opportunity"
    assert row["department"] == "sales"
    assert "run-1" in row["business_outcome_refs"]
    assert "run-2" in row["business_outcome_refs"]
