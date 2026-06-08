"""STA-114: legal vertical pack."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from app.services.legal_vertical_service import (
    build_intake_workflow_definition,
    conflict_review_agent_id,
    enrich_intake_parameters,
    install_legal_vertical_pack,
    intake_workflow_id,
)


def test_intake_workflow_id_stable():
    org = str(uuid.uuid4())
    assert intake_workflow_id(org) == intake_workflow_id(org)


def test_build_intake_definition_includes_clio_steps():
    org_id = str(uuid.uuid4())
    definition = build_intake_workflow_definition(org_id=org_id, clio_connector_id="clio-1")
    actions = [
        step.get("config", {}).get("action")
        for step in definition["steps"]
        if step.get("type") == "invoke_tool"
    ]
    assert "clio.contacts.search" in actions
    assert "clio.matters.search" in actions
    assert "clio.conflict.checklist" in actions
    assert "clio.intake.tasks" in actions
    agent_steps = [s for s in definition["steps"] if s.get("type") == "agent"]
    assert agent_steps[0]["metadata"]["agent_id"] == conflict_review_agent_id(org_id)


def test_enrich_intake_parameters_sets_defaults():
    out = enrich_intake_parameters({}, {"config": {"legal": {"demo_matter_type": "Litigation intake"}}})
    assert out["prospect_name"] == "Acme Holdings LLC"
    assert out["matter_type"] == "Litigation intake"


@patch("app.services.legal_vertical_service.ensure_active_workflow_version", return_value="version-1")
@patch("app.services.legal_vertical_service.write_audit_event")
def test_install_legal_vertical_pack(mock_audit, _mock_version):
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
        else:
            mock.execute.return_value = MagicMock(data=[{}])
        return mock

    client.table.side_effect = table_side_effect
    status = install_legal_vertical_pack(client, org_id, actor_id="user-1")
    assert status["installed"] is True
    assert status["clioConnectorId"]
    assert status["intakeWorkflowId"]
    mock_audit.assert_called_once()
