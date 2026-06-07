"""Org data residency configuration and enforcement (STA-80)."""
from __future__ import annotations

from typing import Any

SUPPORTED_REGIONS = frozenset({"us", "eu"})


def normalize_region(value: str | None) -> str:
    region = (value or "us").strip().lower()
    if region not in SUPPORTED_REGIONS:
        raise ValueError(f"Unsupported data region: {region}")
    return region


def get_org_data_region(
    org_settings: dict[str, Any] | None,
    *,
    data_region: str | None = None,
) -> str:
    if data_region:
        try:
            return normalize_region(data_region)
        except ValueError:
            pass
    settings = org_settings or {}
    enterprise = settings.get("enterprise") if isinstance(settings.get("enterprise"), dict) else {}
    residency = enterprise.get("dataResidency") if isinstance(enterprise.get("dataResidency"), dict) else {}
    return normalize_region(residency.get("region") or settings.get("data_region") or "us")


def storage_prefix(org_id: str, region: str) -> str:
    return f"{region}/{org_id}"


def enforce_region_for_connector_tokens(region: str, connector_region: str | None) -> None:
    if connector_region and connector_region != region:
        raise PermissionError("Connector tokens cannot be replicated across data regions")


def resolve_execution_region(
    org_settings: dict[str, Any] | None,
    *,
    data_region: str | None = None,
) -> str:
    """Resolve workflow/agent execution region from org settings (STA-93)."""
    return get_org_data_region(org_settings, data_region=data_region)
