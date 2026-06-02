"""Tests for org demo seed service."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.org_seed_service import WELCOME_MESSAGE, build_seed_payload, seed_org_if_needed

ORG_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _table_mock(responses: dict[str, dict]) -> MagicMock:
    """Build a chained Supabase table mock keyed by table name."""

    def table_factory(name: str) -> MagicMock:
        chain = MagicMock()
        payload = responses.get(name, {"data": [], "count": 0})

        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.limit.return_value = chain
        chain.upsert.return_value = chain
        chain.update.return_value = chain
        chain.execute.return_value = MagicMock(**payload)
        return chain

    client = MagicMock()
    client.table.side_effect = table_factory
    return client


def test_build_seed_payload_includes_sales_and_marketing_agents():
    payload = build_seed_payload(ORG_ID)
    names = {agent["name"] for agent in payload["agents"]}
    assert "Sales Agent" in names
    assert "Marketing Agent" in names
    assert len(payload["workflows"]) == 1
    assert len(payload["runs"]) == 3
    assert payload["connected_systems"][0]["config"]["demo"] is True


def test_seed_org_if_needed_skips_when_already_seeded():
    client = _table_mock(
        {
            "organizations": {
                "data": [{"settings": {"onboarding": {"seeded": True}}}],
            },
            "agents": {"data": [], "count": 2},
            "workflows": {"data": [], "count": 1},
            "runs": {"data": [], "count": 3},
        }
    )

    result = seed_org_if_needed(client, ORG_ID)

    assert result["seeded"] is True
    assert result["agents_created"] == 2
    assert result["workflows_created"] == 1
    assert result["runs_created"] == 3
    assert result["welcome_message"] == WELCOME_MESSAGE
    client.table("agents").upsert.assert_not_called()


@patch("app.services.org_seed_service._seed_demo_agent_tool_permissions")
def test_seed_org_if_needed_inserts_demo_rows_once(_mock_tool_perms):
    settings_holder: dict = {"settings": {"onboarding": {"seeded": False}}}
    upsert_calls: list[str] = []

    def org_execute():
        return MagicMock(data=[settings_holder])

    org_chain = MagicMock()
    org_chain.select.return_value = org_chain
    org_chain.eq.return_value = org_chain
    org_chain.limit.return_value = org_chain
    org_chain.execute.side_effect = org_execute
    org_chain.update.return_value = org_chain

    upsert_chain = MagicMock()
    upsert_chain.execute.return_value = MagicMock(data=[])

    client = MagicMock()

    def table_factory(name: str) -> MagicMock:
        if name == "organizations":
            return org_chain
        chain = MagicMock()

        def upsert(*_args, **_kwargs):
            upsert_calls.append(name)
            return upsert_chain

        chain.upsert.side_effect = upsert
        return chain

    client.table.side_effect = table_factory

    result = seed_org_if_needed(client, ORG_ID)

    assert result["seeded"] is True
    assert result["agents_created"] == 2
    assert result["workflows_created"] == 1
    assert result["runs_created"] == 3
    assert settings_holder["settings"]["onboarding"]["seeded"] is True
    assert upsert_calls == ["agents", "workflows", "workflow_defs", "runs", "connected_systems"]


def test_seed_org_if_needed_raises_when_org_missing():
    client = _table_mock({"organizations": {"data": []}})
    with pytest.raises(ValueError, match="Organization not found"):
        seed_org_if_needed(client, ORG_ID)
