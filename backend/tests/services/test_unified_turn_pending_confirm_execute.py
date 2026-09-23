from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.unified_turn_pending_live import resolve_unified_live_pending_reply


@pytest.mark.asyncio
async def test_live_pending_yes_executes_frozen_connector_write() -> None:
    task_state = {
        "pending_task": {
            "type": "connector_action",
            "status": "awaiting_confirm",
            "params": {
                "invoke_action": "hubspot.contacts.create",
                "integration": "hubspot",
                "kind": "write",
                "args": {"email": "placeholder.isolated@gravitre-smoke.example.com"},
                "requires_approval": True,
            },
        }
    }
    executed = {
        "stop_pipeline": True,
        "message": "Created the placeholder HubSpot contact.",
        "task_state": {**task_state, "pending_task": None},
        "execution_result": {"success": True},
        "provider_invoked": True,
    }
    with patch(
        "app.services.unified_turn_pending_live.classify_pending_reply",
        new=AsyncMock(return_value="confirm"),
    ), patch(
        "app.services.chat_connector_execution_service.get_chat_connector_execution_service",
    ) as get_svc:
        svc = MagicMock()
        svc.process_turn = AsyncMock(return_value=executed)
        get_svc.return_value = svc
        result = await resolve_unified_live_pending_reply(
            message="yes",
            task_state=task_state,
            org_id="org-1",
            user_id="user-1",
            conversation_id="conv-1",
            client=object(),
            settings=MagicMock(),
        )
    assert result is not None
    assert result.live_served is True
    assert result.tool_invoke_action == "hubspot.contacts.create"
    assert "Created the placeholder" in (result.user_message or "")
    svc.process_turn.assert_awaited_once()
