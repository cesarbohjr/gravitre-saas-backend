"""Executive pack + Phase 4 hubspot.lists.create unit tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.marketplace.intelligence_packs.catalog import get_intelligence_pack_spec, list_intelligence_pack_specs
from app.services.tool_service import list_registered_actions


def test_executive_intelligence_pack_in_catalog():
    spec = get_intelligence_pack_spec("executive-intelligence-pack")
    assert spec is not None
    assert spec.demo_agent_name
    assert spec.connector_template_id == "executive-intelligence-sources"
    assert any(s.get("config", {}).get("action") == "fred.series.get" for s in spec.workflow_steps)
    slugs = {s.pack_id for s in list_intelligence_pack_specs()}
    assert "executive-intelligence-pack" in slugs


def test_hubspot_lists_create_registered():
    assert "hubspot.lists.create" in set(list_registered_actions())


def test_hubspot_lists_create_executor(monkeypatch):
    from app.services.tool_service import _exec_hubspot_lists_create
    from app.services.tool_types import ToolContext
    from types import SimpleNamespace

    ctx = ToolContext(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="actor-1",
    )
    with (
        patch("app.services.tool_service._hubspot_connector_and_token", return_value=("conn-1", "token")),
        patch(
            "app.connectors.hubspot.create_list",
            return_value={"listId": "99", "name": "Phase4 Smoke"},
        ),
    ):
        result = _exec_hubspot_lists_create(ctx, {"name": "Phase4 Smoke"})
    assert result.success is True
    assert result.data.get("list_id") == "99"
    assert result.data.get("result_url")
