from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.mcp_client_service import MCPClientService


@pytest.mark.asyncio
async def test_portable_mcp_write_never_completes_from_provider_acceptance_alone() -> None:
    service = MCPClientService.__new__(MCPClientService)
    service.settings = MagicMock()
    service._load_tool = AsyncMock(
        return_value={
            "id": "tool-1",
            "server_id": "server-1",
            "tool_name": "create_contact",
            "tool_description": "Create contact",
            "input_schema": {},
            "capability_tier": "write",
            "requires_approval": True,
            "enabled": True,
        }
    )
    service._verify_approval = AsyncMock()
    service._load_server = AsyncMock(
        return_value={
            "id": "server-1",
            "server_name": "Portable CRM",
            "enabled": True,
            "activation_state": "configured",
            "source_capability_package_id": "pkg-1",
        }
    )
    service._call_mcp_server = AsyncMock(return_value={"id": "contact-1", "ok": True})
    service._log_execution = AsyncMock()
    service._audit_execution = AsyncMock()
    service._client = MagicMock()

    with (
        patch("app.capabilities.usage.record_mcp_execution"),
        patch("asyncio.create_task"),
    ):
        result = await service.execute_tool(
            "tool-1",
            "org-1",
            {"email": "a@example.com"},
            approval_id="approval-1",
        )

    assert result["status"] == "verification_inconclusive"
    assert result["verification"]["providerAccepted"] is True
    assert result["verification"]["providerAcceptanceIsTerminalSuccess"] is False
    service._log_execution.assert_awaited_once()
    assert service._log_execution.await_args.kwargs["status"] == "verification_inconclusive"


@pytest.mark.asyncio
async def test_manual_mcp_write_preserves_legacy_completed_behavior() -> None:
    service = MCPClientService.__new__(MCPClientService)
    service.settings = MagicMock()
    service._load_tool = AsyncMock(
        return_value={
            "id": "tool-1",
            "server_id": "server-1",
            "tool_name": "create_contact",
            "tool_description": "Create contact",
            "input_schema": {},
            "capability_tier": "write",
            "requires_approval": True,
            "enabled": True,
        }
    )
    service._verify_approval = AsyncMock()
    service._load_server = AsyncMock(
        return_value={
            "id": "server-1",
            "server_name": "Manual CRM",
            "enabled": True,
            "activation_state": "configured",
            "source_capability_package_id": None,
        }
    )
    service._call_mcp_server = AsyncMock(return_value={"id": "contact-1", "ok": True})
    service._log_execution = AsyncMock()
    service._audit_execution = AsyncMock()

    result = await service.execute_tool(
        "tool-1",
        "org-1",
        {"email": "a@example.com"},
        approval_id="approval-1",
    )

    assert result["status"] == "completed"
    service._log_execution.assert_awaited_once()
    assert service._log_execution.await_args.kwargs["status"] == "completed"
