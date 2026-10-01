from unittest.mock import AsyncMock, patch

import pytest

from app.services.mcp_client_service import MCPClientService


class _Query:
    def __init__(self, rows):
        self.rows = rows
        self.updated = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def update(self, payload):
        self.updated = payload
        return self

    def insert(self, payload):
        self.updated = payload
        return self

    def execute(self):
        class R:
            data = self.rows
        return R()


class _Client:
    def __init__(self, existing_enabled: bool):
        self.existing_enabled = existing_enabled
        self.last_tool_query = None

    def table(self, name: str):
        if name == "mcp_tools":
            q = _Query([{"id": "tool-1", "enabled": self.existing_enabled}])
            self.last_tool_query = q
            return q
        raise AssertionError(name)


@pytest.mark.asyncio
@pytest.mark.parametrize("existing_enabled", [True, False])
async def test_package_mcp_rediscovery_preserves_reviewed_tool_state(existing_enabled: bool) -> None:
    service = MCPClientService.__new__(MCPClientService)
    client = _Client(existing_enabled)
    service._client = lambda: client
    service._load_server = AsyncMock(
        return_value={
            "id": "server-1",
            "server_name": "Portable CRM",
            "source_capability_package_id": "pkg-1",
            "enabled": True,
        }
    )
    service._list_remote_tools = AsyncMock(
        return_value=[
            {
                "name": "lookup_contact",
                "description": "Look up one contact",
                "inputSchema": {"type": "object", "properties": {"email": {"type": "string"}}},
            }
        ]
    )

    with (
        patch("app.services.mcp_catalog_sync.sync_mcp_server_to_catalog"),
        patch("app.connectors.action_catalog.extensions.register_action_schemas"),
    ):
        rows = await service.discover_tools("server-1", "org-1")

    assert rows[0]["enabled"] is existing_enabled
    assert client.last_tool_query.updated["enabled"] is existing_enabled
