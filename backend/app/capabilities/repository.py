"""Persistence for portable capability packages."""
from __future__ import annotations

from typing import Any

from app.capabilities.packages import PackageInspection


def list_packages(client: Any, org_id: str) -> list[dict[str, Any]]:
    response = (
        client.table("capability_packages")
        .select("id,org_id,name,package_format,version,description,license,license_policy,risk_level,source_type,source_uri,inspection,status,installed_by,installed_at,updated_at")
        .eq("org_id", org_id)
        .neq("status", "removed")
        .order("installed_at", desc=True)
        .execute()
    )
    return list(response.data or [])


def install_package(
    client: Any,
    *,
    org_id: str,
    user_id: str,
    inspection: PackageInspection,
    manifest: dict[str, Any],
    source_type: str = "manual",
    source_uri: str | None = None,
) -> dict[str, Any]:
    row = {
        "org_id": org_id,
        "name": inspection.name,
        "package_format": inspection.format,
        "version": inspection.version,
        "description": inspection.description,
        "license": inspection.license,
        "license_policy": inspection.license_policy,
        "risk_level": inspection.risk,
        "source_type": source_type,
        "source_uri": source_uri,
        "manifest": manifest,
        "inspection": inspection.as_dict(),
        "status": "quarantined" if inspection.risk == "high" else "installed",
        "installed_by": user_id,
    }
    response = client.table("capability_packages").upsert(
        row,
        on_conflict="org_id,name,version",
    ).execute()
    data = list(response.data or [])
    return data[0] if data else row
