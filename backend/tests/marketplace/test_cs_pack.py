"""Customer Success pack unit tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.marketplace.connector_category_templates import CONNECTOR_CATEGORY_TEMPLATES
from app.marketplace.intelligence_packs.catalog import get_intelligence_pack_spec, list_intelligence_pack_specs
from app.services.tool_service import list_registered_actions


def test_cs_intelligence_pack_demo_in_catalog():
    spec = get_intelligence_pack_spec("customer-success-intelligence-pack")
    assert spec is not None
    assert spec.demo_agent_name == "Customer Success Health Analyst"
    assert spec.connector_template_id == "customer-success-intelligence-sources"
    assert "hubspot" in (spec.demo_systems or [])
    assert "zendesk" in (spec.demo_systems or [])
    actions = {s.get("config", {}).get("action") for s in spec.workflow_steps}
    assert "hubspot.pipelines.list" in actions
    assert "hubspot.deals.list" in actions
    assert "zendesk.tickets.list" in actions
    assert "customer-success-intelligence-pack" in {s.pack_id for s in list_intelligence_pack_specs()}


def test_cs_intelligence_sources_template():
    tpl = CONNECTOR_CATEGORY_TEMPLATES["customer-success-intelligence-sources"]
    assert "hubspot" in tpl["connectors"]
    assert "zendesk" in tpl["connectors"]
    assert "crunchbase" not in tpl["connectors"]
    assert "apollo" not in tpl["connectors"]


def test_cs_demo_actions_registered():
    registered = set(list_registered_actions())
    assert "hubspot.pipelines.list" in registered
    assert "zendesk.tickets.list" in registered


def test_hubspot_pipelines_list_result_url(monkeypatch):
    from types import SimpleNamespace

    from app.services.tool_service import _exec_hubspot_pipelines_list
    from app.services.tool_types import ToolContext

    ctx = ToolContext(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="actor-1",
    )
    with (
        patch("app.services.tool_service._hubspot_connector_and_token", return_value=("conn-1", "token")),
        patch(
            "app.services.tool_service.list_deal_pipelines",
            return_value={"results": [{"id": "default", "label": "Sales Pipeline"}]},
        ),
        patch("app.services.intelligence_pack_tools.emit_pack_source_notification") as emit,
    ):
        result = _exec_hubspot_pipelines_list(ctx, {})
    assert result.success is True
    assert result.data.get("result_url")
    emit.assert_called_once()
    assert emit.call_args.kwargs["action"] == "hubspot.pipelines.list"


def test_hubspot_deals_list_result_url(monkeypatch):
    from types import SimpleNamespace

    from app.services.tool_service import _exec_hubspot_deals_list
    from app.services.tool_types import ToolContext

    ctx = ToolContext(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="actor-1",
    )
    with (
        patch("app.services.tool_service._hubspot_connector_and_token", return_value=("conn-1", "token")),
        patch(
            "app.services.tool_service.list_deals",
            return_value={"results": [{"id": "d1"}]},
        ),
        patch("app.services.intelligence_pack_tools.emit_pack_source_notification") as emit,
    ):
        result = _exec_hubspot_deals_list(ctx, {"limit": 5})
    assert result.success is True
    assert result.data.get("result_url")
    emit.assert_called_once()
    assert emit.call_args.kwargs["action"] == "hubspot.deals.list"


def test_zendesk_tickets_list_result_url(monkeypatch):
    from types import SimpleNamespace

    from app.services.tool_service import _exec_zendesk_tickets_list
    from app.services.tool_types import ToolContext

    ctx = ToolContext(
        settings=SimpleNamespace(),
        client=MagicMock(),
        org_id="org-1",
        actor_id="actor-1",
    )
    with (
        patch(
            "app.services.tool_service._zendesk_credentials",
            return_value=("conn-z", "acme", "a@b.com", "tok", None),
        ),
        patch(
            "app.services.tool_service.list_tickets",
            return_value=[{"id": 1, "subject": "Hello"}],
        ),
        patch("app.services.intelligence_pack_tools.emit_pack_source_notification") as emit,
    ):
        result = _exec_zendesk_tickets_list(ctx, {"limit": 5})
    assert result.success is True
    assert "acme.zendesk.com" in (result.data.get("result_url") or "")
    emit.assert_called_once()
    assert emit.call_args.kwargs["action"] == "zendesk.tickets.list"
