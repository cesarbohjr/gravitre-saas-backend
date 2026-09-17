"""Org-scoped resolution of WorkspaceFocus through existing stores.

Does not invent a generic object-fetch API. Each object_type uses its
canonical getter (agent registry, workflow store, run store, connectors,
org_knowledge_nodes / org_entity_relationships).
"""

from __future__ import annotations

import time
from typing import Any

from app.core.logging import get_logger
from app.schemas.workspace_focus import (
    ALLOWED_OBJECT_TYPES,
    ENTITY_STORE_TYPES,
    IDENTITY_ONLY_TYPES,
    WorkspaceFocus,
)
from app.services.agent_security_gateway import fence_page_context_block

logger = get_logger(__name__)

RESOLUTION_RESOLVED = "resolved"
RESOLUTION_UNRESOLVED = "unresolved"
RESOLUTION_INVALID_TYPE = "invalid_type"
RESOLUTION_IDENTITY_ONLY = "identity_only"
RESOLUTION_NONE = "none"


def _safe_str(value: Any, limit: int = 200) -> str:
    text = str(value or "").strip()
    return text[:limit]


def resolve_workspace_focus(
    *,
    org_id: str,
    client: Any,
    focus: WorkspaceFocus | None,
    environment_name: str = "production",
) -> dict[str, Any]:
    """Resolve client identity against this org only. Never use another org's rows."""
    t0 = time.perf_counter()
    if focus is None:
        result = {
            "resolution": RESOLUTION_NONE,
            "surface": None,
            "route": None,
            "selection": None,
            "canonical": None,
            "duration_ms": 0.0,
        }
        result["duration_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        return result

    selection = focus.selection
    base: dict[str, Any] = {
        "resolution": RESOLUTION_NONE,
        "surface": focus.surface,
        "route": focus.route,
        "selection": None,
        "canonical": None,
    }
    if selection is None:
        base["duration_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        return base

    object_type = selection.object_type.lower()
    object_id = selection.object_id
    client_label = selection.label
    base["selection"] = {
        "object_type": object_type,
        "object_id": object_id,
        "label": client_label,
    }

    if object_type not in ALLOWED_OBJECT_TYPES:
        base["resolution"] = RESOLUTION_INVALID_TYPE
        base["duration_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        return base

    if not org_id or client is None:
        base["resolution"] = RESOLUTION_UNRESOLVED
        base["duration_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        return base

    try:
        canonical = _resolve_in_org(
            client=client,
            org_id=org_id,
            object_type=object_type,
            object_id=object_id,
            environment_name=environment_name,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "workspace_focus_resolve_failed org_id=%s type=%s error=%s",
            org_id,
            object_type,
            exc,
        )
        canonical = None

    if object_type in IDENTITY_ONLY_TYPES:
        base["resolution"] = RESOLUTION_IDENTITY_ONLY
        base["canonical"] = {
            "object_type": object_type,
            "object_id": object_id,
            "name": None,
            "store": "identity_only",
        }
        base["duration_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        return base

    if canonical is None:
        base["resolution"] = RESOLUTION_UNRESOLVED
    else:
        base["resolution"] = RESOLUTION_RESOLVED
        base["canonical"] = canonical
    base["duration_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
    return base


def _resolve_in_org(
    *,
    client: Any,
    org_id: str,
    object_type: str,
    object_id: str,
    environment_name: str,
) -> dict[str, Any] | None:
    if object_type == "agent":
        from app.operators.agent_intelligence import resolve_agent_record

        row = resolve_agent_record(client, org_id, object_id, environment_name=environment_name)
        if not row:
            return None
        return {
            "object_type": "agent",
            "object_id": str(row.get("id") or object_id),
            "name": _safe_str(row.get("name")),
            "store": "agents",
            "role": _safe_str(row.get("role"), 120) or None,
        }

    if object_type == "workflow":
        from app.workflows.repository import get_workflow_def

        row = get_workflow_def(client, org_id, object_id)
        if not row:
            return None
        return {
            "object_type": "workflow",
            "object_id": str(row.get("id") or object_id),
            "name": _safe_str(row.get("name")),
            "store": "workflows",
            "status": _safe_str(row.get("status"), 64) or None,
        }

    if object_type == "run":
        from app.workflows.repository import get_run_with_steps

        row = get_run_with_steps(client, org_id, object_id, environment_name=environment_name)
        if not row:
            row = get_run_with_steps(client, org_id, object_id, environment_name="default")
        if not row:
            return None
        return {
            "object_type": "run",
            "object_id": str(row.get("id") or object_id),
            "name": _safe_str(row.get("status") or object_id),
            "store": "workflow_runs",
            "workflow_id": _safe_str(row.get("workflow_id") or row.get("workflowId"), 128) or None,
        }

    if object_type == "connector":
        result = (
            client.table("connectors")
            .select("id,name,type,status")
            .eq("id", object_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return None
        row = dict(rows[0])
        return {
            "object_type": "connector",
            "object_id": str(row.get("id") or object_id),
            "name": _safe_str(row.get("name")),
            "store": "connectors",
            "connector_type": _safe_str(row.get("type"), 64) or None,
        }

    if object_type == "relationship":
        result = (
            client.table("org_entity_relationships")
            .select(
                "id,relationship_type,source_entity_id,target_entity_id,"
                "source_entity_type,target_entity_type"
            )
            .eq("id", object_id)
            .eq("org_id", org_id)
            .is_("archived_at", "null")
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return None
        row = dict(rows[0])
        return {
            "object_type": "relationship",
            "object_id": str(row.get("id") or object_id),
            "name": _safe_str(row.get("relationship_type") or object_id),
            "store": "org_entity_relationships",
            "source_entity_id": _safe_str(row.get("source_entity_id"), 128) or None,
            "target_entity_id": _safe_str(row.get("target_entity_id"), 128) or None,
        }

    if object_type in ENTITY_STORE_TYPES:
        result = (
            client.table("org_knowledge_nodes")
            .select("id,node_type,name")
            .eq("id", object_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return None
        row = dict(rows[0])
        db_type = _safe_str(row.get("node_type"), 64) or "entity"
        return {
            "object_type": db_type,
            "object_id": str(row.get("id") or object_id),
            "name": _safe_str(row.get("name")),
            "store": "org_knowledge_nodes",
            "client_claimed_type": object_type,
        }

    return None


def format_workspace_focus_compiler_block(resolved: dict[str, Any]) -> str:
    """Small fenced identity block. Resolved DB name is authority; client label is not."""
    resolution = str(resolved.get("resolution") or RESOLUTION_NONE)
    if resolution == RESOLUTION_NONE and not resolved.get("selection"):
        return ""

    lines = [
        f"resolution={resolution}",
        f"surface={resolved.get('surface') or ''}",
        f"route={resolved.get('route') or ''}",
    ]
    selection = resolved.get("selection") if isinstance(resolved.get("selection"), dict) else None
    if selection:
        lines.append(
            "client_selection="
            f"{selection.get('object_type')}:{selection.get('object_id')}"
        )
        if selection.get("label"):
            lines.append(
                "client_label_is_not_authority=" + _safe_str(selection.get("label"))
            )
    canonical = resolved.get("canonical") if isinstance(resolved.get("canonical"), dict) else None
    if canonical:
        lines.append(
            "canonical="
            f"{canonical.get('object_type')}:{canonical.get('object_id')} "
            f"name={canonical.get('name') or ''} store={canonical.get('store') or ''}"
        )
    if resolution == RESOLUTION_UNRESOLVED:
        lines.append(
            "The claimed object was not found in this organization. "
            "Do not invent details about it. Answer the user question without fabricating the object."
        )
    elif resolution == RESOLUTION_INVALID_TYPE:
        lines.append("Unknown selection type. Ignore as object identity.")
    elif resolution == RESOLUTION_IDENTITY_ONLY:
        lines.append("Selection is a UI identity hint only (no registry row).")

    body = "WORKSPACE FOCUS (current turn only — not historical):\n" + "\n".join(lines)
    return fence_page_context_block(body)


def workspace_focus_trace_meta(resolved: dict[str, Any]) -> dict[str, Any]:
    selection = resolved.get("selection") if isinstance(resolved.get("selection"), dict) else {}
    canonical = resolved.get("canonical") if isinstance(resolved.get("canonical"), dict) else {}
    return {
        "context.surface": resolved.get("surface"),
        "context.route": resolved.get("route"),
        "context.selection.type": selection.get("object_type") or canonical.get("object_type"),
        "context.selection.id": selection.get("object_id") or canonical.get("object_id"),
        "context.resolution": resolved.get("resolution"),
        "context.resolve_ms": resolved.get("duration_ms"),
    }
