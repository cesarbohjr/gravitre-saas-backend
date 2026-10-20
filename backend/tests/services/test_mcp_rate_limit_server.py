"""MCP rate limits must use MCP server identity, never connector FK identities."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.connectors.rate_limit import RateLimitError, enforce_mcp_rate_limit


def test_mcp_rate_limit_uses_atomic_server_scoped_rpc():
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=True)

    enforce_mcp_rate_limit(
        client, "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
    )

    client.rpc.assert_called_once_with(
        "consume_mcp_server_token",
        {
            "p_org_id": "11111111-1111-4111-8111-111111111111",
            "p_server_id": "22222222-2222-4222-8222-222222222222",
            "p_step_type": "mcp",
            "p_capacity": 10.0,
            "p_refill_per_sec": 2.0,
        },
    )


def test_mcp_rate_limit_denies_quota_exhaustion():
    client = MagicMock()
    client.rpc.return_value.execute.return_value = SimpleNamespace(data=False)
    with pytest.raises(RateLimitError):
        enforce_mcp_rate_limit(client, "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222")


def test_mcp_rate_limit_fails_closed_on_database_error():
    client = MagicMock()
    client.rpc.return_value.execute.side_effect = RuntimeError("quota RPC unavailable")
    with pytest.raises(RuntimeError, match="quota RPC unavailable"):
        enforce_mcp_rate_limit(client, "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222")
