"""Marketplace sandbox service tests (STA-72)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.marketplace_sandbox_service import (
    build_marketplace_sandbox_payload,
    get_sandbox_status,
    provision_sandbox,
)


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
