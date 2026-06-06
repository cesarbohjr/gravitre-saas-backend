"""Marketplace sandbox service tests (STA-72)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.marketplace_sandbox_service import (
    DEMO_INVOKE_ACTION,
    build_marketplace_sandbox_payload,
    get_sandbox_status,
    provision_sandbox,
    run_sandbox_demo,
)
from app.services.tool_types import NormalizedResult

SANDBOX_ORG_ID = "00000000-0000-0000-0000-000000000099"


def test_build_sandbox_payload_includes_qa_agent():
    payload = build_marketplace_sandbox_payload("00000000-0000-0000-0000-000000000099")
    assert len(payload["agents"]) == 1
    assert payload["agents"][0]["name"] == "Integration QA Agent"
    assert any(c["vendor"] == "acme_tools" for c in payload["connectors"])


def test_get_sandbox_status_not_provisioned():
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[]
    )
    status = get_sandbox_status(client, "org-publisher")
    assert status["provisioned"] is False


@patch("app.services.marketplace_sandbox_service._normalize_status")
@patch("app.services.marketplace_sandbox_service._seed_sandbox_data")
@patch("app.services.marketplace_sandbox_service._create_sandbox_org")
@patch("app.services.marketplace_sandbox_service._load_org_name", return_value="Acme Partner")
@patch("app.services.marketplace_sandbox_service.get_sandbox_mapping", return_value=None)
def test_provision_sandbox_creates_mapping(
    _mock_mapping,
    _mock_name,
    mock_create_org,
    mock_seed,
    mock_normalize,
):
    mock_create_org.return_value = "sandbox-org-1"
    mock_seed.return_value = {"welcome_message": "welcome"}
    mock_normalize.return_value = {
        "provisioned": True,
        "created": True,
        "publisherOrgId": "org-publisher",
        "sandboxOrgId": "sandbox-org-1",
    }

    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "m1"}]
    )
    client.table.return_value.insert.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[
            {
                "publisher_org_id": "org-publisher",
                "sandbox_org_id": "sandbox-org-1",
                "created_by": "user-1",
            }
        ]
    )
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[{"id": "sandbox-org-1", "name": "Partner Sandbox", "slug": "sandbox"}]
    )

    settings = SimpleNamespace(connector_secrets_encryption_key="a" * 64, encryption_key="")
    result = provision_sandbox(
        client,
        settings,
        publisher_org_id="org-publisher",
        user_id="user-1",
    )
    assert result["sandboxOrgId"] == "sandbox-org-1"
    mock_create_org.assert_called_once()
    mock_seed.assert_called_once()


@patch("app.services.marketplace_sandbox_service._fetch_recent_audit_trail")
@patch("app.services.tool_service.invoke_tool")
@patch("app.connectors.partners.acme_tools_demo.ensure_acme_tools_demo_registered")
@patch("app.workflows.audit.write_audit_event")
@patch(
    "app.services.marketplace_sandbox_service.get_sandbox_mapping",
    return_value={"sandbox_org_id": SANDBOX_ORG_ID},
)
def test_run_sandbox_demo_invokes_acme_and_returns_audit(
    _mock_mapping,
    _mock_audit,
    _mock_register,
    mock_invoke,
    mock_audit_trail,
):
    mock_invoke.return_value = NormalizedResult(
        success=True,
        action=DEMO_INVOKE_ACTION,
        data={"tickets": [{"id": "T-1", "subject": "Login issue"}]},
    )
    mock_audit_trail.return_value = [
        {
            "id": "a1",
            "action": "tool.invoke.completed",
            "resourceType": "connector",
            "resourceId": "conn-1",
            "metadata": {},
            "createdAt": "2026-05-29T12:00:00Z",
        }
    ]

    settings = SimpleNamespace(connector_secrets_encryption_key="a" * 64, encryption_key="")
    result = run_sandbox_demo(
        MagicMock(),
        settings,
        publisher_org_id="org-publisher",
        actor_id="user-1",
    )

    assert result["success"] is True
    assert result["action"] == DEMO_INVOKE_ACTION
    assert result["sandboxOrgId"] == SANDBOX_ORG_ID
    assert len(result["tickets"]) == 1
    assert result["auditTrail"][0]["action"] == "tool.invoke.completed"
    mock_invoke.assert_called_once()
    call_args = mock_invoke.call_args
    assert call_args[0][1] == DEMO_INVOKE_ACTION
