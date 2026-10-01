"""Reviewed bindings from portable declarations to native Gravitre entities."""
from __future__ import annotations

from typing import Any

_ALLOWED_TARGETS = {
    "agent": {"agent"},
    "play": {"play", "workflow"},
    "template": {"marketplace_asset"},
    "trigger": {"workflow_schedule"},
}


def _declared_component_names(package: dict[str, Any], kind: str) -> set[str]:
    inspection = package.get("inspection") if isinstance(package.get("inspection"), dict) else {}
    rows = inspection.get("components") if isinstance(inspection.get("components"), list) else []
    return {
        str(row.get("name") or "").strip()
        for row in rows
        if isinstance(row, dict)
        and str(row.get("kind") or "") == kind
        and str(row.get("name") or "").strip()
    }


def _target_exists(client: Any, *, org_id: str, target_type: str, target_id: str) -> bool:
    if target_type == "play":
        from app.plays.catalog import get_platform_play
        return get_platform_play(target_id) is not None

    table_map = {
        "agent": "agents",
        "workflow": "workflows",
        "workflow_schedule": "workflow_schedules",
        "marketplace_asset": "marketplace_assets",
    }
    table = table_map.get(target_type)
    if not table:
        return False
    if target_type == "marketplace_asset":
        rows = (
            client.table(table)
            .select("id,org_id,visibility,status")
            .eq("id", target_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            return False
        row = rows[0]
        return (
            str(row.get("org_id") or "") == org_id
            or (
                str(row.get("visibility") or "") == "public"
                and str(row.get("status") or "") == "published"
            )
        )

    rows = (
        client.table(table)
        .select("id")
        .eq("id", target_id)
        .eq("org_id", org_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    return bool(rows)


def bind_component(
    client: Any,
    *,
    org_id: str,
    package: dict[str, Any],
    component_kind: str,
    component_name: str,
    target_type: str,
    target_id: str,
    user_id: str,
) -> dict[str, Any]:
    if str(package.get("status") or "") != "installed":
        raise ValueError("Capability package must be installed before native components can be bound")
    kind = str(component_kind or "").strip()
    name = str(component_name or "").strip()
    target = str(target_type or "").strip()
    tid = str(target_id or "").strip()
    if target not in _ALLOWED_TARGETS.get(kind, set()):
        raise ValueError(f"Unsupported native binding: {kind} -> {target}")
    if name not in _declared_component_names(package, kind):
        raise ValueError("Portable component is not declared by this package")
    if not tid or not _target_exists(client, org_id=org_id, target_type=target, target_id=tid):
        raise ValueError("Native Gravitre binding target was not found")

    row = {
        "org_id": org_id,
        "package_id": str(package.get("id") or ""),
        "component_kind": kind,
        "component_name": name,
        "target_type": target,
        "target_id": tid,
        "enabled": True,
        "created_by": user_id or None,
    }
    response = client.table("capability_component_bindings").upsert(
        row,
        on_conflict="package_id,component_kind,component_name,target_type,target_id",
    ).execute()
    rows = list(response.data or [])
    return rows[0] if rows else row


def list_component_bindings(client: Any, *, org_id: str, package_id: str) -> list[dict[str, Any]]:
    try:
        response = (
            client.table("capability_component_bindings")
            .select("id,package_id,component_kind,component_name,target_type,target_id,enabled,created_by,created_at,updated_at")
            .eq("org_id", org_id)
            .eq("package_id", package_id)
            .order("created_at")
            .execute()
        )
        return list(response.data or [])
    except Exception:
        return []


def remove_component_binding(client: Any, *, org_id: str, package_id: str, binding_id: str) -> bool:
    response = (
        client.table("capability_component_bindings")
        .delete()
        .eq("id", binding_id)
        .eq("org_id", org_id)
        .eq("package_id", package_id)
        .execute()
    )
    return bool(response.data)


def deactivate_component_bindings(client: Any, *, org_id: str, package_id: str) -> int:
    try:
        query = client.table("capability_component_bindings")
        query = query.eq("org_id", org_id).eq("package_id", package_id).eq("enabled", True)
        response = query.update({"enabled": False}).execute()
        return len(response.data or [])
    except Exception:
        return 0
