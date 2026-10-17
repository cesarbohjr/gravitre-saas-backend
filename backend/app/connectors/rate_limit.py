"""DB-backed token bucket rate limiting for connectors (beta-scope)."""
from __future__ import annotations

from app.connectors.dispatch import connector_capacity

class RateLimitError(Exception):
    """Raised when a connector is rate limited."""


def enforce_rate_limit(
    client,
    org_id: str,
    step_type: str,
    connector_type: str,
    connector_id: str,
) -> None:
    capacity, refill = connector_capacity(connector_type)
    r = client.rpc(
        "consume_connector_token",
        {
            "p_org_id": org_id,
            "p_step_type": step_type,
            "p_connector_type": connector_type,
            "p_connector_id": connector_id,
            "p_capacity": capacity,
            "p_refill_per_sec": refill,
        },
    ).execute()
    allowed = r.data
    if isinstance(allowed, list) and allowed:
        allowed = allowed[0]
    if isinstance(allowed, dict) and allowed:
        allowed = next(iter(allowed.values()))
    if not bool(allowed):
        raise RateLimitError("Rate limit exceeded")


def enforce_mcp_rate_limit(client, org_id: str, server_id: str) -> None:
    """Atomic, server-scoped token bucket; never use connector IDs for MCP servers.

    Fail closed for missing RPC, schema mismatch, and database faults.
    """
    capacity, refill = connector_capacity("mcp")
    result = client.rpc(
        "consume_mcp_server_token",
        {
            "p_org_id": org_id,
            "p_server_id": server_id,
            "p_step_type": "mcp",
            "p_capacity": capacity,
            "p_refill_per_sec": refill,
        },
    ).execute()
    allowed = result.data
    if isinstance(allowed, list) and allowed:
        allowed = allowed[0]
    if isinstance(allowed, dict) and allowed:
        allowed = next(iter(allowed.values()))
    if not bool(allowed):
        raise RateLimitError("MCP server rate limit exceeded")
