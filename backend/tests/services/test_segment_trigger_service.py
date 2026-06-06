from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.connectors.segment_webhooks import verify_segment_webhook_signature
from app.services.segment_trigger_service import process_segment_event_batch


def test_verify_segment_webhook_signature():
    body = b'{"type":"track","event":"Webinar Attended"}'
    secret = "test-secret"
    import hashlib
    import hmac

    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert verify_segment_webhook_signature(body=body, signature=digest, secret=secret) is True
    assert verify_segment_webhook_signature(body=body, signature="bad", secret=secret) is False


@pytest.mark.asyncio
async def test_process_segment_event_batch_starts_workflow():
    settings = SimpleNamespace(supabase_url="http://x", supabase_service_role_key="k")
    connector = {
        "id": "conn-seg",
        "org_id": "org-1",
        "type": "segment",
        "config": {
            "webhook_secret": "secret",
            "segment_triggers": [
                {
                    "id": "t1",
                    "event_type": "track",
                    "event_name": "Webinar Attended",
                    "workflow_id": "wf-1",
                    "active": True,
                }
            ],
        },
        "environment": "production",
    }
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
        data=[connector]
    )

    with patch("app.services.segment_trigger_service.get_supabase_client", return_value=client):
        with patch(
            "app.services.segment_trigger_service.start_workflow_from_segment",
            new_callable=AsyncMock,
            return_value={"workflow_id": "wf-1", "run_id": "run-1", "status": "completed"},
        ) as start:
            results = await process_segment_event_batch(
                settings,
                "conn-seg",
                [{"type": "track", "event": "Webinar Attended", "userId": "u1"}],
            )
    assert len(results) == 1
    start.assert_awaited_once()
    assert start.await_args.kwargs["parameters"]["event_name"] == "Webinar Attended"
