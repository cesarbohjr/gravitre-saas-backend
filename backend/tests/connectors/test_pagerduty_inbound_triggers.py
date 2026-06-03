from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.pagerduty_trigger_service import process_pagerduty_event_batch


@pytest.mark.asyncio
async def test_process_pagerduty_event_batch_starts_workflow():
    settings = SimpleNamespace(
        supabase_url="http://x",
        supabase_service_role_key="k",
    )
    connector = {
        "id": "conn-pd",
        "org_id": "org-1",
        "type": "pagerduty",
        "config": {
            "webhook_secret": "secret",
            "pagerduty_triggers": [
                {
                    "id": "t1",
                    "event": "incident.triggered",
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

    with patch(
        "app.services.pagerduty_trigger_service.get_supabase_client",
        return_value=client,
    ):
        with patch(
            "app.services.pagerduty_trigger_service.start_workflow_from_pagerduty",
            new_callable=AsyncMock,
            return_value={"workflow_id": "wf-1", "run_id": "run-1", "status": "completed"},
        ) as start:
            results = await process_pagerduty_event_batch(
                settings,
                "conn-pd",
                [
                    {
                        "event": {
                            "event_type": "incident.triggered",
                            "data": {"incident": {"id": "INC1", "summary": "Outage"}},
                        }
                    }
                ],
            )
    assert len(results) == 1
    start.assert_awaited_once()
    params = start.await_args.kwargs["parameters"]
    assert params["incident"]["id"] == "INC1"
