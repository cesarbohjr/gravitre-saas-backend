"""Outcome Pack connector alternative groups (OR-group readiness).

A required PSA/CRM/system class is satisfied when any registered alternative
in that group is connected. Enrichment-only groups never block install.
"""
from __future__ import annotations

from typing import Any

from app.marketplace.schemas import RequiredConnectorRef


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def required_connector_or_groups(
    required_connectors: list[RequiredConnectorRef] | list[dict[str, Any]],
    alternatives: list[list[str]] | None = None,
) -> list[list[str]]:
    """Return required OR-groups. Each inner list is satisfied by any member."""
    required: list[str] = []
    for row in required_connectors or []:
        if isinstance(row, RequiredConnectorRef):
            if not row.required:
                continue
            connector = _norm(row.connector_type)
        elif isinstance(row, dict):
            if row.get("required", True) is False:
                continue
            connector = _norm(row.get("connectorType") or row.get("connector_type"))
        else:
            connector = _norm(getattr(row, "connector_type", ""))
        if connector:
            required.append(connector)

    groups: list[list[str]] = []
    covered: set[str] = set()
    for raw_group in alternatives or []:
        members = [_norm(item) for item in raw_group if _norm(item)]
        if not members:
            continue
        if any(member in required for member in members):
            unique = list(dict.fromkeys(members))
            groups.append(unique)
            covered.update(member for member in unique if member in required)

    for connector in required:
        if connector not in covered:
            groups.append([connector])
            covered.add(connector)
    return groups


def evaluate_connector_or_groups(
    *,
    connected: set[str],
    required_connectors: list[RequiredConnectorRef] | list[dict[str, Any]],
    alternatives: list[list[str]] | None = None,
) -> dict[str, Any]:
    groups = required_connector_or_groups(required_connectors, alternatives)
    connected_norm = {_norm(item) for item in connected if _norm(item)}
    group_rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for group in groups:
        satisfied = any(member in connected_norm for member in group)
        connected_members = [member for member in group if member in connected_norm]
        row = {
            "connectors": group,
            "satisfied": satisfied,
            "connectedMembers": connected_members,
            "required": True,
        }
        group_rows.append(row)
        if not satisfied:
            blockers.append(
                {
                    "connector": group[0],
                    "alternatives": group,
                    "reason": (
                        f"Connect one of: {', '.join(group)}"
                        if len(group) > 1
                        else f"{group[0]} is not connected"
                    ),
                    "action_url": f"/connectors?type={group[0]}",
                }
            )
    return {
        "can_install": len(blockers) == 0,
        "groups": group_rows,
        "blockers": blockers,
    }
