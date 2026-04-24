"""Connector dispatch helpers (DB-backed throttling)."""
from __future__ import annotations


def connector_capacity(connector_type: str) -> tuple[float, float]:
    """Return (capacity, refill_per_sec) for connector type."""
    if connector_type == "slack":
        return 3.0, 1.0
    if connector_type == "email":
        return 2.0, 0.2
    if connector_type == "webhook":
        return 5.0, 2.0
    return 1.0, 1.0
