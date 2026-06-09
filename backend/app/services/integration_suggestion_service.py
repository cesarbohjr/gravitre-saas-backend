"""Auto-suggest connectors and workflows from audit usage patterns (STA-123)."""
from __future__ import annotations

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import Settings
from app.services.department_pack_catalog import get_pack_spec
from app.services.tool_service import STEP_TYPE_TO_ACTION
from app.workflows.audit import write_audit_event

logger = logging.getLogger(__name__)

AUDIT_INTEGRATION_SUGGESTIONS_SCANNED = "integration.suggestions.scanned"
RESOURCE_TYPE_INTEGRATION_SUGGESTION = "integration_suggestion"

MANUAL_PCT_THRESHOLD = 0.40
MIN_EVENTS_FOR_SUGGESTION = 5
DEFAULT_LOOKBACK_DAYS = 30

CONNECTOR_LABELS: dict[str, str] = {
    "hubspot": "HubSpot",
    "salesforce": "Salesforce",
    "zendesk": "Zendesk",
    "slack": "Slack",
    "quickbooks": "QuickBooks",
    "jira": "Jira",
    "email": "Email",
    "webhook": "Webhook",
}

CONNECTOR_TO_PACKS: dict[str, list[str]] = {
    "hubspot": ["sales-ops", "marketing-ops"],
    "zendesk": ["support-ops"],
    "quickbooks": ["finance-ops"],
}

CONNECTOR_STA_REF: dict[str, str] = {
    "hubspot": "STA-15 HubSpot v1 actions",
    "salesforce": "STA-22 Salesforce actions",
    "zendesk": "STA-21 Zendesk integration",
}


class IntegrationSuggestionError(Exception):
    code = "INTEGRATION_SUGGESTION_ERROR"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _is_missing_table_error(error: Exception | None) -> bool:
    if error is None:
        return False
    message = str(error).lower()
    return "does not exist" in message or ("relation" in message and "does not exist" in message)


def _select_rows(client: Any, table: str, build_query) -> list[dict[str, Any]]:
    try:
        result = build_query(client.table(table)).execute()
    except Exception as exc:
        if _is_missing_table_error(exc):
            return []
        raise
    if _is_missing_table_error(getattr(result, "error", None)):
        return []
    return list(result.data or [])


def _connector_label(connector_type: str) -> str:
    return CONNECTOR_LABELS.get(connector_type, connector_type.replace("_", " ").title())


def _parse_event_time(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _event_metadata(row: dict[str, Any]) -> dict[str, Any]:
    meta = row.get("metadata")
    if isinstance(meta, dict):
        return meta
    details = row.get("details")
    if isinstance(details, dict):
        return details
    return {}


def _tool_action_from_row(row: dict[str, Any]) -> str | None:
    action = str(row.get("action") or "")
    if action.startswith("tool.invoke"):
        meta = _event_metadata(row)
        tool_action = str(meta.get("action") or "").strip()
        return tool_action or None
    return None


def _is_manual_invoke(meta: dict[str, Any]) -> bool:
    return not meta.get("run_id")


def aggregate_tool_usage(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize manual vs workflow tool usage by connector and action."""
    by_connector: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "manual": 0, "workflow": 0})
    by_action: Counter[str] = Counter()
    manual_by_action: Counter[str] = Counter()

    for row in events:
        tool_action = _tool_action_from_row(row)
        if not tool_action or "." not in tool_action:
            continue
        connector_type = tool_action.split(".", 1)[0]
        meta = _event_metadata(row)
        manual = _is_manual_invoke(meta)
        by_connector[connector_type]["total"] += 1
        by_action[tool_action] += 1
        if manual:
            by_connector[connector_type]["manual"] += 1
            manual_by_action[tool_action] += 1
        else:
            by_connector[connector_type]["workflow"] += 1

    connector_stats: list[dict[str, Any]] = []
    for connector_type, counts in by_connector.items():
        total = counts["total"]
        manual = counts["manual"]
        connector_stats.append(
            {
                "connectorType": connector_type,
                "label": _connector_label(connector_type),
                "totalInvocations": total,
                "manualInvocations": manual,
                "workflowInvocations": counts["workflow"],
                "manualPct": round(manual / total, 3) if total else 0.0,
                "topManualActions": [
                    {"action": action, "count": count}
                    for action, count in manual_by_action.most_common(5)
                    if action.startswith(f"{connector_type}.")
                ],
            }
        )
    connector_stats.sort(key=lambda item: item["manualInvocations"], reverse=True)
    return {
        "connectors": connector_stats,
        "totalToolEvents": sum(item["totalInvocations"] for item in connector_stats),
        "topActions": [{"action": action, "count": count} for action, count in by_action.most_common(10)],
    }


def fetch_tool_usage_events(
    client: Any,
    org_id: str,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> list[dict[str, Any]]:
    since = (_now() - timedelta(days=lookback_days)).isoformat()
    result = (
        client.table("audit_events")
        .select("id,action,metadata,created_at")
        .eq("org_id", org_id)
        .gte("created_at", since)
        .like("action", "tool.invoke%")
        .order("created_at", desc=True)
        .limit(5000)
        .execute()
    )
    return list(result.data or [])


def _active_connector_types(client: Any, org_id: str) -> set[str]:
    result = (
        client.table("connectors")
        .select("type")
        .eq("org_id", org_id)
        .eq("status", "active")
        .execute()
    )
    return {str(row["type"]) for row in (result.data or []) if row.get("type")}


def _installed_pack_ids(client: Any, org_id: str) -> set[str]:
    result = (
        client.table("org_department_pack_installs")
        .select("pack_id")
        .eq("org_id", org_id)
        .execute()
    )
    return {str(row["pack_id"]) for row in (result.data or []) if row.get("pack_id")}


def _workflow_automated_actions(client: Any, org_id: str) -> set[str]:
    result = (
        client.table("workflow_defs")
        .select("definition")
        .eq("org_id", org_id)
        .execute()
    )
    actions: set[str] = set()
    for row in result.data or []:
        definition = row.get("definition") or {}
        for step in definition.get("steps") or []:
            if not isinstance(step, dict):
                continue
            config = step.get("config") or {}
            action = str(config.get("action") or STEP_TYPE_TO_ACTION.get(step.get("type") or "") or "").strip()
            if action:
                actions.add(action)
    return actions


def _suggestion_row(
    *,
    org_id: str,
    suggestion_type: str,
    title: str,
    message: str,
    evidence: dict[str, Any],
    connector_type: str | None = None,
    pack_id: str | None = None,
    workflow_template_id: str | None = None,
    confidence: float,
    priority: int,
) -> dict[str, Any]:
    return {
        "org_id": org_id,
        "suggestion_type": suggestion_type,
        "connector_type": connector_type,
        "pack_id": pack_id,
        "workflow_template_id": workflow_template_id,
        "title": title,
        "message": message,
        "evidence": evidence,
        "confidence": confidence,
        "priority": priority,
        "status": "open",
        "suggested_at": _now_iso(),
    }


def _pick_department_pack(connector_type: str, installed: set[str]) -> str | None:
    for pack_id in CONNECTOR_TO_PACKS.get(connector_type, []):
        if pack_id not in installed:
            spec = get_pack_spec(pack_id)
            if spec:
                return pack_id
    return None


def build_integration_suggestions(
    client: Any,
    org_id: str,
    usage: dict[str, Any],
    *,
    active_connectors: set[str] | None = None,
    installed_packs: set[str] | None = None,
    automated_actions: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Generate connector/workflow suggestions from aggregated audit usage."""
    active = active_connectors if active_connectors is not None else _active_connector_types(client, org_id)
    installed = installed_packs if installed_packs is not None else _installed_pack_ids(client, org_id)
    workflow_actions = automated_actions if automated_actions is not None else _workflow_automated_actions(client, org_id)

    suggestions: list[dict[str, Any]] = []
    for stat in usage.get("connectors") or []:
        connector_type = str(stat["connectorType"])
        total = int(stat["totalInvocations"])
        manual = int(stat["manualInvocations"])
        manual_pct = float(stat["manualPct"])
        label = str(stat["label"])
        top_manual = stat.get("topManualActions") or []

        if total < MIN_EVENTS_FOR_SUGGESTION:
            continue

        evidence_base = {
            "connectorType": connector_type,
            "totalInvocations": total,
            "manualInvocations": manual,
            "manualPct": manual_pct,
            "topManualActions": top_manual,
        }

        if connector_type not in active:
            sta_ref = CONNECTOR_STA_REF.get(connector_type, "connector actions")
            suggestions.append(
                _suggestion_row(
                    org_id=org_id,
                    suggestion_type="connect_connector",
                    connector_type=connector_type,
                    title=f"Connect {label}",
                    message=(
                        f"You invoked {label} tools {total} times in the audit window, "
                        f"but no active {label} connector is connected. "
                        f"Connect {label} to enable {sta_ref} in workflows and agents."
                    ),
                    evidence=evidence_base,
                    confidence=min(0.95, 0.7 + min(total, 50) / 200),
                    priority=90,
                )
            )
            continue

        if manual_pct < MANUAL_PCT_THRESHOLD:
            continue

        pct_display = int(round(manual_pct * 100))
        pack_id = _pick_department_pack(connector_type, installed)
        if pack_id:
            spec = get_pack_spec(pack_id)
            pack_name = spec.name if spec else pack_id
            suggestions.append(
                _suggestion_row(
                    org_id=org_id,
                    suggestion_type="install_department_pack",
                    connector_type=connector_type,
                    pack_id=pack_id,
                    workflow_template_id=pack_id,
                    title=f"Install {pack_name}",
                    message=(
                        f"You run {pct_display}% of {label} tasks manually "
                        f"({manual} of {total} invocations). "
                        f"Install the {pack_name} to automate agents, RAG, and workflows."
                    ),
                    evidence={**evidence_base, "suggestedPackId": pack_id, "installPath": f"/api/marketplace/role-packs/{pack_id}/install"},
                    confidence=min(0.92, 0.65 + manual_pct / 2),
                    priority=80,
                )
            )
            continue

        uncovered = [
            item["action"]
            for item in top_manual
            if item.get("action") and item["action"] not in workflow_actions
        ]
        action_hint = ", ".join(uncovered[:3]) if uncovered else "repeated manual tool steps"
        suggestions.append(
            _suggestion_row(
                org_id=org_id,
                suggestion_type="automate_workflow",
                connector_type=connector_type,
                title=f"Automate {label} workflows",
                message=(
                    f"You run {pct_display}% of {label} tasks manually "
                    f"({manual} of {total} invocations). "
                    f"Create or enable a workflow for: {action_hint}."
                ),
                evidence={
                    **evidence_base,
                    "uncoveredActions": uncovered,
                    "existingWorkflowActions": sorted(workflow_actions),
                },
                confidence=min(0.88, 0.6 + manual_pct / 2),
                priority=65,
            )
        )

    suggestions.sort(key=lambda row: row.get("priority", 0), reverse=True)
    return suggestions


def _serialize_suggestion(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "orgId": row.get("org_id"),
        "suggestionType": row.get("suggestion_type"),
        "connectorType": row.get("connector_type"),
        "packId": row.get("pack_id"),
        "workflowTemplateId": row.get("workflow_template_id"),
        "title": row.get("title"),
        "message": row.get("message"),
        "evidence": row.get("evidence") or {},
        "confidence": float(row.get("confidence") or 0),
        "priority": int(row.get("priority") or 0),
        "status": row.get("status"),
        "suggestedAt": row.get("suggested_at"),
        "dismissedAt": row.get("dismissed_at"),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


def list_integration_suggestions(
    client: Any,
    org_id: str,
    *,
    status: str = "open",
    connector_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    def build_query(table):
        query = (
            table.select("*")
            .eq("org_id", org_id)
            .eq("status", status)
            .order("priority", desc=True)
            .order("suggested_at", desc=True)
            .limit(limit)
        )
        if connector_type:
            query = query.eq("connector_type", connector_type)
        return query

    rows = _select_rows(client, "integration_suggestions", build_query)
    return [_serialize_suggestion(row) for row in rows]


def dismiss_integration_suggestion(client: Any, org_id: str, suggestion_id: str) -> dict[str, Any]:
    existing = (
        client.table("integration_suggestions")
        .select("*")
        .eq("org_id", org_id)
        .eq("id", suggestion_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise IntegrationSuggestionError("Suggestion not found", code="SUGGESTION_NOT_FOUND")
    now = _now_iso()
    updated = (
        client.table("integration_suggestions")
        .update({"status": "dismissed", "dismissed_at": now})
        .eq("org_id", org_id)
        .eq("id", suggestion_id)
        .execute()
    )
    row = (updated.data or existing.data)[0]
    return _serialize_suggestion(row)


def scan_integration_suggestions(
    client: Any,
    org_id: str,
    *,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Analyze audit tool usage and persist integration suggestions."""
    events = fetch_tool_usage_events(client, org_id, lookback_days=lookback_days)
    usage = aggregate_tool_usage(events)
    suggestions = build_integration_suggestions(client, org_id, usage)

    try:
        client.table("integration_suggestions").delete().eq("org_id", org_id).eq("status", "open").execute()
    except Exception as exc:
        if not _is_missing_table_error(exc):
            raise

    persisted: list[dict[str, Any]] = []
    if suggestions:
        try:
            insert_result = client.table("integration_suggestions").insert(suggestions).execute()
            if _is_missing_table_error(getattr(insert_result, "error", None)):
                persisted = [_serialize_suggestion(row) for row in suggestions]
            else:
                persisted = [_serialize_suggestion(row) for row in (insert_result.data or suggestions)]
        except Exception as exc:
            if _is_missing_table_error(exc):
                persisted = [_serialize_suggestion(row) for row in suggestions]
            else:
                raise

    summary = {
        "lookbackDays": lookback_days,
        "usage": usage,
        "suggestionCount": len(persisted),
        "suggestions": persisted,
        "scannedAt": _now_iso(),
    }

    if actor_id:
        write_audit_event(
            client,
            org_id,
            actor_id,
            AUDIT_INTEGRATION_SUGGESTIONS_SCANNED,
            RESOURCE_TYPE_INTEGRATION_SUGGESTION,
            org_id,
            metadata={
                "suggestionCount": len(persisted),
                "totalToolEvents": usage.get("totalToolEvents", 0),
                "types": list({row["suggestionType"] for row in persisted}),
            },
        )

    logger.info(
        "integration_suggestions_scan org_id=%s events=%s suggestions=%s",
        org_id,
        usage.get("totalToolEvents", 0),
        len(persisted),
    )
    return summary
