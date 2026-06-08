"""STA-115: real estate vertical pack."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from app.services.real_estate_vertical_service import (
    build_listing_workflow_definition,
    enrich_listing_parameters,
    install_real_estate_vertical_pack,
    listing_coordinator_agent_id,
    listing_workflow_id,
)


def test_listing_workflow_id_stable():
    org = str(uuid.uuid4())
    assert listing_workflow_id(org) == listing_workflow_id(org)


def test_build_listing_definition_includes_steps():
    org_id = str(uuid.uuid4())
    definition = build_listing_workflow_definition(org_id=org_id, hubspot_connector_id="hs-1")
    actions = [
        step.get("config", {}).get("action")
        for step in definition["steps"]
        if step.get("type") == "invoke_tool"
    ]
    assert "hubspot.contacts.search" in actions
    assert "real_estate.mls.note" in actions
    assert "real_estate.handoff.brief" in actions
    agent_steps = [s for s in definition["steps"] if s.get("type") == "agent"]
    assert agent_steps[0]["metadata"]["agent_id"] == listing_coordinator_agent_id(org_id)


def test_enrich_listing_parameters_sets_defaults():
    out = enrich_listing_parameters({}, {"config": {"real_estate": {"demo_list_price": "500000"}}})
    assert out["property_address"] == "742 Evergreen Terrace"
    assert out["list_price"] == "500000"


@patch("app.services.real_estate_vertical_service.ensure_active_workflow_version", return_value="version-1")
@patch("app.services.real_estate_vertical_service.write_audit_event")
def test_install_real_estate_vertical_pack(mock_audit, _mock_version):
    client = MagicMock()
    org_id = str(uuid.uuid4())

    def table_side_effect(name: str):
        mock = MagicMock()
        mock.select.return_value = mock
        mock.eq.return_value = mock
        mock.limit.return_value = mock
        mock.upsert.return_value = mock
        mock.update.return_value = mock
        if name == "organizations":
            mock.execute.return_value = MagicMock(data=[{"settings": {}}])
        elif name == "connectors":
            mock.execute.return_value = MagicMock(data=[])
        else:
            mock.execute.return_value = MagicMock(data=[{}])
        return mock

    client.table.side_effect = table_side_effect
    status = install_real_estate_vertical_pack(client, org_id, actor_id="user-1")
    assert status["installed"] is True
    assert status["listingWorkflowId"]
    mock_audit.assert_called_once()
