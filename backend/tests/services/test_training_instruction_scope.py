"""Instructions are guidance or guardrails, scoped to the team, a department or one agent."""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.services import training_service
from app.services.training_service import (
    fleet_department,
    list_custom_instructions,
    load_active_instruction_texts,
)

ROWS = [
    {"name": "Agent tone", "content": "Use first names.", "agent_id": "a1", "department": None, "kind": "guidance"},
    {"name": "Sales floor", "content": "Never quote below floor.", "agent_id": None, "department": "sales", "kind": "guardrail"},
    {"name": "Sales style", "content": "Lead with ROI.", "agent_id": None, "department": "sales", "kind": "guidance"},
    {"name": "Finance only", "content": "Read only.", "agent_id": None, "department": "finance", "kind": "guidance"},
    {"name": "Cite", "content": "Cite sources.", "agent_id": None, "department": None, "kind": "guidance"},
    {"name": "Email", "content": "Confirm before emailing.", "agent_id": None, "department": None, "kind": "guardrail"},
]


@pytest.fixture(autouse=True)
def _fresh_cache():
    training_service._instruction_cache.clear()
    yield
    training_service._instruction_cache.clear()


def _load(**kwargs: Any) -> list[str]:
    with patch.object(training_service, "execute_or_empty", return_value=[dict(r) for r in ROWS]), patch(
        "app.core.org_state_cache.cache_allowed", return_value=False
    ):
        return load_active_instruction_texts(MagicMock(), "org-1", **kwargs)


def test_guardrails_first_then_broad_to_specific() -> None:
    assert _load(agent_id="a1", department="Sales") == [
        "[Guardrail] Sales floor: Never quote below floor.",
        "[Guardrail] Email: Confirm before emailing.",
        "Cite: Cite sources.",
        "Sales style: Lead with ROI.",
        "Agent tone: Use first names.",
    ]


def test_other_departments_and_agents_do_not_apply() -> None:
    assert _load(agent_id="a2", department="Customer Success") == [
        "[Guardrail] Email: Confirm before emailing.",
        "Cite: Cite sources.",
    ]


def test_fleet_department_matches_web_mapping() -> None:
    assert fleet_department("Customer Success") == "customer_success"
    assert fleet_department("support") == "customer_success"
    assert fleet_department("HR") == "general"
    assert fleet_department("Revenue Ops") == "sales"
    assert fleet_department("") is None


def test_list_falls_back_when_scope_columns_are_missing() -> None:
    calls: list[str] = []

    def _table(name: str) -> MagicMock:
        mock = MagicMock()

        def _select(columns: str) -> MagicMock:
            calls.append(columns)
            chain = MagicMock()
            if "kind" in columns:
                chain.eq.return_value.order.return_value.execute.return_value = SimpleNamespace(
                    data=None, error="column custom_instructions.kind does not exist"
                )
            else:
                chain.eq.return_value.order.return_value.execute.return_value = SimpleNamespace(
                    data=[{"id": "i1", "agent_id": None, "name": "Tone", "content": "Be brief", "is_active": True}],
                    error=None,
                )
            return chain

        mock.select.side_effect = _select
        return mock

    client = MagicMock()
    client.table.side_effect = _table
    rows = list_custom_instructions(client, "org-1")
    assert len(calls) == 2
    assert rows[0]["kind"] == "guidance"
    assert rows[0]["department"] is None
