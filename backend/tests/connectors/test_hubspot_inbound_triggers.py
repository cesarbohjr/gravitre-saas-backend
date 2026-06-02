"""STA-16: HubSpot inbound webhook triggers."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.connectors.hubspot_webhooks import (
    decode_hubspot_request_uri,
    event_matches_trigger,
    normalize_hubspot_event,
    verify_hubspot_signature_v3,
)
from app.services.hubspot_trigger_service import process_hubspot_event_batch


def _sign_v3(*, method: str, uri: str, body: bytes, secret: str, timestamp_ms: str) -> str:
    source = f"{method.upper()}{uri}{body.decode('utf-8')}{timestamp_ms}"
    digest = hmac.new(secret.encode("utf-8"), source.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def test_decode_hubspot_request_uri():
    assert decode_hubspot_request_uri("/api/webhooks/hubspot/inbound%3Ffoo%3D1") == "/api/webhooks/hubspot/inbound?foo=1"


def test_verify_hubspot_signature_v3_valid():
    secret = "test-secret"
    body = b'[{"portalId":1,"subscriptionType":"contact.creation","objectId":99}]'
    ts = str(int(time.time() * 1000))
    uri = "/api/webhooks/hubspot/inbound"
    sig = _sign_v3(method="POST", uri=uri, body=body, secret=secret, timestamp_ms=ts)
    assert verify_hubspot_signature_v3(
        method="POST",
        request_uri=uri,
        body=body,
        timestamp_ms=ts,
        signature=sig,
        client_secret=secret,
    )


def test_event_matches_trigger_property_filter():
    trigger = {
        "event": "deal.propertyChange",
        "property": "dealstage",
        "workflow_id": "wf-1",
        "active": True,
    }
    assert event_matches_trigger(
        trigger,
        subscription_type="deal.propertyChange",
        property_name="dealstage",
    )
    assert not event_matches_trigger(
        trigger,
        subscription_type="deal.propertyChange",
        property_name="amount",
    )


def test_normalize_hubspot_event_contact():
    out = normalize_hubspot_event(
        {
            "eventId": 1,
            "subscriptionType": "contact.creation",
            "portalId": 123,
            "objectId": 456,
        }
    )
    assert out["contact"]["id"] == "456"
    assert out["hubspot_event"]["subscriptionType"] == "contact.creation"


@pytest.mark.asyncio
async def test_process_hubspot_event_batch_starts_workflow():
    settings = SimpleNamespace(
        supabase_url="http://x",
        supabase_service_role_key="k",
        hubspot_client_secret="secret",
        hubspot_client_id="id",
        hubspot_sandbox_client_id="",
        hubspot_sandbox_client_secret="",
    )
    connector = {
        "id": "conn-1",
        "org_id": "org-1",
        "type": "hubspot",
        "config": {
            "hub_id": 123,
            "hubspot_triggers": [
                {
                    "event": "contact.creation",
                    "workflow_id": "wf-1",
                    "active": True,
                }
            ],
        },
        "environment": "production",
    }
    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[connector]
    )

    workflow = {
        "id": "wf-1",
        "org_id": "org-1",
        "status": "active",
        "definition": {"schema_version": "v1", "steps": []},
    }

    def _table(name: str) -> MagicMock:
        table = MagicMock()
        if name == "connectors":
            table.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[connector])
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

    with patch("app.services.hubspot_trigger_service.get_supabase_client", return_value=mock_client):
        with patch(
            "app.services.hubspot_trigger_service.ensure_hubspot_access_token",
            return_value=(None, "no token"),
        ):
            with patch(
                "app.services.hubspot_trigger_service.get_execution_service",
                return_value=mock_execution,
            ):
                results = await process_hubspot_event_batch(
                    settings,
                    [
                        {
                            "portalId": 123,
                            "subscriptionType": "contact.creation",
                            "objectId": 456,
                        }
                    ],
                    execution_service=mock_execution,
                )

    assert len(results) == 1
    assert results[0]["workflow_id"] == "wf-1"
    assert results[0]["status"] == "completed"
    mock_execution.execute_workflow.assert_awaited_once()
