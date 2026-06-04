"""STA-32: Salesforce inbound webhook triggers."""
from __future__ import annotations

import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.connectors.salesforce_webhooks import (
    canonical_event_type,
    event_matches_trigger,
    normalize_salesforce_event,
    verify_salesforce_webhook_signature,
)
from app.services.salesforce_trigger_service import process_salesforce_event_batch


def _sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def test_canonical_event_type_aliases():
    assert canonical_event_type("Lead.created") == "lead.created"
    assert canonical_event_type("Opportunity.stageChange") == "opportunity.stageChange"


def test_verify_salesforce_webhook_signature_valid():
    body = b'{"event":"lead.created","recordId":"00Q1"}'
    secret = "whsec-test"
    sig = _sign(body, secret)
    assert verify_salesforce_webhook_signature(body=body, signature=sig, secret=secret)
    assert verify_salesforce_webhook_signature(body=body, signature=f"sha256={sig}", secret=secret)


def test_event_matches_trigger_stage_filter():
    trigger = {
        "event": "opportunity.stageChange",
        "stage": "Closed Won",
        "workflow_id": "wf-1",
        "active": True,
    }
    assert event_matches_trigger(
        trigger,
        event_type="opportunity.stageChange",
        stage_name="Closed Won",
    )
    assert not event_matches_trigger(
        trigger,
        event_type="opportunity.stageChange",
        stage_name="Prospecting",
    )


def test_normalize_salesforce_event_lead():
    out = normalize_salesforce_event(
        {
            "event": "lead.created",
            "recordId": "00Q456",
            "organizationId": "00D123",
        }
    )
    assert out["lead"]["id"] == "00Q456"
    assert out["salesforce_event"]["event"] == "lead.created"


@pytest.mark.asyncio
async def test_process_salesforce_event_batch_starts_workflow():
    settings = SimpleNamespace(
        supabase_url="http://x",
        supabase_service_role_key="k",
    )
    connector = {
        "id": "conn-sf",
        "org_id": "org-1",
        "type": "salesforce",
        "config": {
            "webhook_secret": "secret",
            "salesforce_triggers": [
                {
                    "event": "lead.created",
                    "workflow_id": "wf-1",
                    "active": True,
                }
            ],
        },
        "environment": "production",
    }
    mock_client = MagicMock()

    workflow = {
        "id": "wf-1",
        "org_id": "org-1",
        "status": "active",
        "definition": {"schema_version": "v1", "steps": []},
    }

    def _table(name: str) -> MagicMock:
        table = MagicMock()
        if name == "connectors":
            table.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[connector]
            )
        elif name == "workflow_defs":
            chain = table.select.return_value.eq.return_value.eq.return_value.limit.return_value
            chain.execute.return_value = MagicMock(data=[workflow])
        elif name == "organization_members":
            table.select.return_value.eq.return_value.in_.return_value.limit.return_value.execute.return_value = (
                MagicMock(data=[{"user_id": "user-1"}])
            )
        elif name == "workflow_runs":
            table.insert.return_value.execute.return_value = MagicMock(data=[{"id": "run-1"}])
            table.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[{"id": "run-1"}])
        return table

    mock_client.table.side_effect = _table

    mock_execution = AsyncMock()
    mock_execution.execute_workflow = AsyncMock(
        return_value=SimpleNamespace(status="completed", results=[])
    )

    with patch("app.services.salesforce_trigger_service.get_supabase_client", return_value=mock_client):
        with patch(
            "app.services.salesforce_trigger_service.ensure_salesforce_session",
            return_value=(None, None, "no token"),
        ):
            with patch(
                "app.services.salesforce_trigger_service.get_execution_service",
                return_value=mock_execution,
            ):
                results = await process_salesforce_event_batch(
                    settings,
                    "conn-sf",
                    [
                        {
                            "event": "lead.created",
                            "recordId": "00Q456",
                        }
                    ],
                    execution_service=mock_execution,
                )

    assert len(results) == 1
    assert results[0]["workflow_id"] == "wf-1"
    assert results[0]["status"] == "completed"
    mock_execution.execute_workflow.assert_awaited_once()
