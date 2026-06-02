"""STA-12: webhook triggers use the same step executor as manual /execute."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.execution_service import ExecutionService


@pytest.mark.asyncio
async def test_webhook_path_delegates_to_execute_workflow_steps():
    service = ExecutionService()
    definition = {
        "schema_version": "v1",
        "steps": [
            {
                "id": "slack_step",
                "name": "Notify",
                "type": "slack_post_message",
                "config": {"channel": "#general"},
            }
        ],
    }
    mock_client = MagicMock()
    mock_settings = SimpleNamespace(supabase_url="http://x", supabase_service_role_key="k")

    with patch("app.services.execution_service.get_settings", return_value=mock_settings):
        with patch("app.services.execution_service.get_supabase_client", return_value=mock_client):
            with patch(
                "app.services.execution_service.execute_workflow_steps",
                return_value=(
                    "completed",
                    [
                        {
                            "step_id": "slack_step",
                            "status": "completed",
                            "output_snapshot": {"ok": True, "channel": "#general"},
                        }
                    ],
                    [],
                    False,
                ),
            ) as mock_steps:
                result = await service.execute_workflow(
                    org_id="org-1",
                    workflow_id="wf-1",
                    run_id="run-webhook",
                    parameters={"message": "webhook fired"},
                    user_id="user-1",
                    definition=definition,
                    environment_name="production",
                )

    mock_steps.assert_called_once()
    args = mock_steps.call_args[0]
    assert args[2] == "user-1"
    assert args[3] == "run-webhook"
    assert args[4]["steps"][0]["type"] == "slack_post_message"
    assert result.status == "completed"
    assert result.results[0].output.get("ok") is True
