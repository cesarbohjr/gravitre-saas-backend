"""STA-113: healthcare vertical pack."""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

from app.services.healthcare_vertical_service import (
    build_prior_auth_workflow_definition,
    clinical_admin_agent_id,
    enrich_prior_auth_parameters,
    install_healthcare_vertical_pack,
    prior_auth_workflow_id,
)


def test_prior_auth_workflow_id_stable():
    org = str(uuid.uuid4())
    assert prior_auth_workflow_id(org) == prior_auth_workflow_id(org)


def test_build_prior_auth_definition_includes_fhir_steps():
    org_id = str(uuid.uuid4())
    definition = build_prior_auth_workflow_definition(org_id=org_id, fhir_connector_id="fhir-1")
    actions = [
        step.get("config", {}).get("action")
        for step in definition["steps"]
        if step.get("type") == "invoke_tool"
    ]
    assert "fhir.patients.search" in actions
    assert "fhir.appointments.search" in actions
    assert "fhir.prior_auth.checklist" in actions
    agent_steps = [s for s in definition["steps"] if s.get("type") == "agent"]
    assert agent_steps[0]["metadata"]["agent_id"] == clinical_admin_agent_id(org_id)


def test_enrich_prior_auth_parameters_sets_defaults():
    out = enrich_prior_auth_parameters({}, {"config": {"healthcare": {"payer": "Aetna"}}})
    assert out["patient_name"] == "Smith"
    assert out["payer"] == "Aetna"


@patch("app.services.healthcare_vertical_service.ensure_active_workflow_version", return_value="version-1")
@patch("app.services.healthcare_vertical_service.write_audit_event")
def test_install_healthcare_vertical_pack(mock_audit, _mock_version):
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
    status = install_healthcare_vertical_pack(client, org_id, actor_id="user-1")
    assert status["installed"] is True
    assert status["fhirConnectorId"]
    assert status["priorAuthWorkflowId"]
    mock_audit.assert_called_once()
