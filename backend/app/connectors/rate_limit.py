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
