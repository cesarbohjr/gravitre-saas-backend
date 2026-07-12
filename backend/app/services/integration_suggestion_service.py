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
from app.workflows.schema_sync import mirror_legacy_workflow_row_to_contract

logger = logging.getLogger(__name__)

AUDIT_INTEGRATION_SUGGESTIONS_SCANNED = "integration.suggestions.scanned"
AUDIT_INTEGRATION_SUGGESTION_APPLIED = "integration.suggestion.applied"
AUDIT_INTEGRATION_SUGGESTION_APPROVAL_REQUIRED = "integration.suggestion.approval_required"
RESOURCE_TYPE_INTEGRATION_SUGGESTION = "integration_suggestion"

# STA-317 — mutating applies require BOTH require_admin (router) AND chat-gate
# parity (catalog / write-authority check + awaiting_confirm before durable write).
MUTATING_SUGGESTION_TYPES = frozenset({"automate_workflow", "install_department_pack"})
PACK_INSTALL_TOOL = "marketplace_install_department_pack"
PACK_INSTALL_INVOKE = "marketplace.install_department_pack"

MANUAL_PCT_THRESHOLD = 0.40
MIN_EVENTS_FOR_SUGGESTION = 5
DEFAULT_LOOKBACK_DAYS = 30

CONNECTOR_LABELS: dict[str, str] = {
    "hubspot": "HubSpot",
    "pipedrive": "Pipedrive",
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
    "pipedrive": ["sales-ops"],
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


def _build_apply_summary(result: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    entities: list[dict[str, Any]] = []
    if result.get("workflowId"):
        entities.append(
            {
                "type": "workflow",
                "id": str(result["workflowId"]),
                "label": row.get("title") or "Workflow draft",
            }
        )
    install = result.get("installResult") or {}
    if isinstance(install, dict):
        for agent_id in install.get("agentIds") or install.get("agent_ids") or []:
            entities.append({"type": "agent", "id": str(agent_id), "label": "Agent"})
        for wf_id in install.get("workflowIds") or install.get("workflow_ids") or []:
            entities.append({"type": "workflow", "id": str(wf_id), "label": "Workflow"})
        if install.get("workflowId"):
            entities.append({"type": "workflow", "id": str(install["workflowId"]), "label": "Pack workflow"})

    evidence = row.get("evidence") or {}
    highlights: list[str] = []
    if isinstance(evidence, dict):
        for key, value in list(evidence.items())[:5]:
            highlights.append(f"{key}: {value}")

    return {
        "suggestionType": row.get("suggestion_type"),
        "title": row.get("title"),
        "entities": entities,
        "evidenceHighlights": highlights,
        "redirectPath": result.get("redirectPath"),
    }


def list_integration_suggestions(
    client: Any,
    org_id: str,
    *,
    status: str = "actionable",
    connector_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    statuses: list[str]
    if status == "actionable":
        statuses = ["open", "awaiting_confirm"]
    else:
        statuses = [status]

    def build_query(table):
        query = (
            table.select("*")
            .eq("org_id", org_id)
            .in_("status", statuses)
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


def _create_workflow_from_suggestion_stub(
    client: Any,
    org_id: str,
    suggestion: dict[str, Any],
    *,
    actor_id: str | None = None,
) -> str:
    from app.workflows.constants import SCHEMA_VERSION

    evidence = suggestion.get("evidence") or {}
    uncovered = evidence.get("uncoveredActions") or []
    connector_type = suggestion.get("connector_type") or suggestion.get("connectorType") or ""
    steps: list[dict[str, Any]] = []
    for index, action in enumerate(uncovered[:5]):
        if not action:
            continue
        steps.append(
            {
                "id": f"step-{index + 1}",
                "name": str(action).replace(".", " ").replace("_", " ").title(),
                "type": "invoke_tool",
                "config": {
                    "connectorType": connector_type,
                    "action": action,
                },
            }
        )
    if not steps:
        steps.append(
            {
                "id": "step-1",
                "name": "Review manual tasks",
                "type": "noop",
                "config": {"note": suggestion.get("message") or suggestion.get("title")},
            }
        )
    edges = [
        {"from": steps[i]["id"], "to": steps[i + 1]["id"]}
        for i in range(len(steps) - 1)
    ]
    definition = {"schema_version": SCHEMA_VERSION, "steps": steps, "edges": edges}
    row = {
        "org_id": org_id,
        "name": suggestion.get("title") or "Recommended workflow",
        "goal": (suggestion.get("message") or suggestion.get("title") or "")[:500],
        "description": "Created from integration recommendation (STA-123 apply)",
        "definition": definition,
        "schema_version": SCHEMA_VERSION,
        "status": "draft",
        "stage": "build",
        "version": "v1.0.0",
        "created_by": actor_id,
    }
    created = client.table("workflow_defs").insert(row).execute()
    if not created.data:
        raise IntegrationSuggestionError("Workflow create failed", code="WORKFLOW_CREATE_FAILED")
    mirror_legacy_workflow_row_to_contract(client, dict(created.data[0]))
    return str(created.data[0]["id"])


def _definition_from_generated_workflow(generated: Any) -> dict[str, Any]:
    from app.workflows.constants import SCHEMA_VERSION

    steps = [
        {
            "id": node.id,
            "name": node.name,
            "type": node.type,
            "config": node.config,
            "metadata": {
                "description": node.description,
                "position": node.position,
                "mesonGenerated": True,
            },
        }
        for node in generated.nodes
    ]
    edges = [
        {
            "id": edge.id,
            "from": edge.source,
            "to": edge.target,
            "label": edge.label,
        }
        for edge in generated.edges
    ]
    return {"schema_version": SCHEMA_VERSION, "steps": steps, "edges": edges}


async def _create_workflow_from_suggestion(
    client: Any,
    org_id: str,
    suggestion: dict[str, Any],
    *,
    actor_id: str | None = None,
) -> str:
    """Meson/goal-service enriched workflow draft with invoke_tool fallback."""
    from app.services.goal_service import GoalService
    from app.workflows.constants import SCHEMA_VERSION

    goal = (suggestion.get("message") or suggestion.get("title") or "Automate manual integration tasks").strip()
    connector_type = suggestion.get("connector_type") or suggestion.get("connectorType") or ""
    evidence = suggestion.get("evidence") or {}
    uncovered = evidence.get("uncoveredActions") or []
    org_context = None
    if uncovered:
        org_context = "Prioritize automating these manual tool actions: " + ", ".join(str(a) for a in uncovered[:5])

    try:
        generated = await GoalService().generate_workflow(
            goal=goal,
            department=None,
            connectors=[connector_type] if connector_type else None,
            approval_required=True,
            org_context=org_context,
            org_id=org_id,
        )
        definition = _definition_from_generated_workflow(generated)
        row = {
            "org_id": org_id,
            "name": generated.name,
            "goal": generated.goal[:500],
            "description": generated.description or "Created from integration recommendation (Meson apply)",
            "definition": definition,
            "schema_version": SCHEMA_VERSION,
            "status": "draft",
            "stage": "build",
            "version": "v1.0.0",
            "created_by": actor_id,
        }
        created = client.table("workflow_defs").insert(row).execute()
        if not created.data:
            raise IntegrationSuggestionError("Workflow create failed", code="WORKFLOW_CREATE_FAILED")
        mirror_legacy_workflow_row_to_contract(client, dict(created.data[0]))
        return str(created.data[0]["id"])
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "integration_suggestion_meson_fallback org_id=%s error=%s",
            org_id,
            str(exc),
        )
        return _create_workflow_from_suggestion_stub(client, org_id, suggestion, actor_id=actor_id)


async def apply_integration_suggestion(
    client: Any,
    org_id: str,
    suggestion_id: str,
    *,
    actor_id: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Apply an open integration suggestion (STA-123 Tier 6 / STA-317 gate).

    ``connect_connector`` remains an immediate redirect (no durable write).

    Mutating types (``automate_workflow``, ``install_department_pack``) stage
    ``awaiting_confirm`` after catalog/write-authority checks — they do **not**
    execute until ``confirm_integration_suggestion``. Router also enforces
    ``require_admin`` for mutating apply/confirm (human choice: both).
    """
    _ = settings  # reserved for confirm path callers that share the signature
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
    row = existing.data[0]
    status = str(row.get("status") or "")
    suggestion_type = row.get("suggestion_type")

    if status == "awaiting_confirm" and suggestion_type in MUTATING_SUGGESTION_TYPES:
        return _approval_required_response(row)

    if status != "open":
        raise IntegrationSuggestionError("Suggestion is not open", code="SUGGESTION_NOT_OPEN")

    result: dict[str, Any] = {
        "workflowId": None,
        "redirectPath": None,
        "installResult": None,
        "requiresApproval": False,
        "pendingTask": None,
        "confirmPath": None,
    }

    if suggestion_type == "connect_connector":
        connector_type = row.get("connector_type")
        result["redirectPath"] = f"/connectors?type={connector_type}" if connector_type else "/connectors"
        return _finalize_applied(client, org_id, suggestion_id, row, result, actor_id=actor_id)

    if suggestion_type in MUTATING_SUGGESTION_TYPES:
        pending = _build_mutating_pending_task(row)
        now = _now_iso()
        evidence = dict(row.get("evidence") or {})
        evidence["pending_approval"] = pending
        updated = (
            client.table("integration_suggestions")
            .update(
                {
                    "status": "awaiting_confirm",
                    "evidence": evidence,
                    "updated_at": now,
                }
            )
            .eq("org_id", org_id)
            .eq("id", suggestion_id)
            .execute()
        )
        staged = (updated.data or [{**row, "status": "awaiting_confirm", "evidence": evidence}])[0]
        if actor_id:
            write_audit_event(
                client,
                org_id,
                actor_id,
                AUDIT_INTEGRATION_SUGGESTION_APPROVAL_REQUIRED,
                RESOURCE_TYPE_INTEGRATION_SUGGESTION,
                suggestion_id,
                metadata={
                    "suggestionType": suggestion_type,
                    "toolName": (pending.get("params") or {}).get("tool_name"),
                    "invokeAction": (pending.get("params") or {}).get("invoke_action"),
                },
            )
        logger.info(
            "integration_suggestion_approval_required org_id=%s suggestion_id=%s type=%s",
            org_id,
            suggestion_id,
            suggestion_type,
        )
        return _approval_required_response(staged)

    raise IntegrationSuggestionError("Unsupported suggestion type", code="UNSUPPORTED_SUGGESTION_TYPE")


async def confirm_integration_suggestion(
    client: Any,
    org_id: str,
    suggestion_id: str,
    *,
    actor_id: str,
    settings: Settings,
) -> dict[str, Any]:
    """Execute a mutating suggestion after awaiting_confirm (STA-317 chat parity)."""
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
    row = existing.data[0]
    if str(row.get("status") or "") != "awaiting_confirm":
        raise IntegrationSuggestionError(
            "Suggestion is not awaiting confirmation",
            code="SUGGESTION_NOT_AWAITING_CONFIRM",
        )
    suggestion_type = row.get("suggestion_type")
    if suggestion_type not in MUTATING_SUGGESTION_TYPES:
        raise IntegrationSuggestionError("Unsupported suggestion type", code="UNSUPPORTED_SUGGESTION_TYPE")

    evidence = dict(row.get("evidence") or {})
    pending = evidence.get("pending_approval") if isinstance(evidence.get("pending_approval"), dict) else {}
    params = dict(pending.get("params") or {})

    result: dict[str, Any] = {
        "workflowId": None,
        "redirectPath": None,
        "installResult": None,
        "requiresApproval": False,
        "pendingTask": None,
        "confirmPath": None,
    }

    if suggestion_type == "automate_workflow":
        from app.services.assistant_tools import tool_create_workflow

        goal = str(
            params.get("workflow_goal")
            or row.get("message")
            or row.get("title")
            or "Assistant workflow"
        ).strip()
        # Re-check write authority at confirm time (catalog / platform allowlist).
        _assert_create_workflow_requires_approval()
        created = tool_create_workflow(org_id, goal, settings, user_id=actor_id)
        if created.get("error"):
            raise IntegrationSuggestionError(
                str(created.get("error") or "Workflow create failed"),
                code="WORKFLOW_CREATE_FAILED",
            )
        workflow_id = str(created.get("id") or "")
        result["workflowId"] = workflow_id or None
        result["redirectPath"] = f"/workflows/{workflow_id}/builder" if workflow_id else "/workflows"
    else:  # install_department_pack
        pack_id = str(params.get("pack_id") or row.get("pack_id") or "").strip()
        if not pack_id:
            raise IntegrationSuggestionError("Pack id missing on suggestion", code="PACK_ID_MISSING")
        from app.services.agent_role_marketplace_service import install_department_pack

        write_audit_event(
            client,
            org_id,
            actor_id,
            "tool.invoke.requested",
            "marketplace_pack",
            pack_id,
            metadata={"action": PACK_INSTALL_INVOKE, "suggestionId": suggestion_id},
        )
        try:
            install_result = install_department_pack(
                client,
                org_id,
                pack_id,
                actor_id=actor_id,
            )
        except Exception as exc:  # noqa: BLE001
            write_audit_event(
                client,
                org_id,
                actor_id,
                "tool.invoke.failed",
                "marketplace_pack",
                pack_id,
                metadata={
                    "action": PACK_INSTALL_INVOKE,
                    "suggestionId": suggestion_id,
                    "error": str(exc)[:500],
                },
            )
            raise
        write_audit_event(
            client,
            org_id,
            actor_id,
            "tool.invoke.completed",
            "marketplace_pack",
            pack_id,
            metadata={"action": PACK_INSTALL_INVOKE, "suggestionId": suggestion_id},
        )
        result["installResult"] = install_result
        result["redirectPath"] = f"/marketplace/assets/{pack_id}"

    evidence.pop("pending_approval", None)
    return _finalize_applied(
        client,
        org_id,
        suggestion_id,
        {**row, "evidence": evidence},
        result,
        actor_id=actor_id,
        evidence_override=evidence,
    )


def _assert_create_workflow_requires_approval() -> None:
    from app.services.react_write_gate import tool_requires_user_write_approval
    from app.services.tool_registry import get_tool_registry

    requires, invoke_action, _integration, _label = tool_requires_user_write_approval(
        "assistant_create_workflow",
        get_tool_registry(),
    )
    if not requires:
        raise IntegrationSuggestionError(
            "assistant_create_workflow is not gated by write authority",
            code="WRITE_AUTHORITY_MISSING",
        )
    if invoke_action and invoke_action != "assistant.create_workflow":
        raise IntegrationSuggestionError(
            f"Unexpected invoke_action for create workflow: {invoke_action}",
            code="WRITE_AUTHORITY_MISMATCH",
        )


def _build_mutating_pending_task(row: dict[str, Any]) -> dict[str, Any]:
    suggestion_type = str(row.get("suggestion_type") or "")
    suggestion_id = str(row.get("id") or "")
    if suggestion_type == "automate_workflow":
        _assert_create_workflow_requires_approval()
        goal = str(row.get("message") or row.get("title") or "Assistant workflow").strip()
        name = str(row.get("title") or "").strip()[:120] or None
        return {
            "type": "create_workflow",
            "status": "awaiting_confirm",
            "params": {
                "workflow_goal": goal,
                **({"workflow_name": name} if name else {}),
                "source": "integration_suggestion_apply",
                "suggestion_id": suggestion_id,
                "tool_name": "assistant_create_workflow",
                "invoke_action": "assistant.create_workflow",
            },
        }
    if suggestion_type == "install_department_pack":
        pack_id = str(row.get("pack_id") or "").strip()
        if not pack_id:
            raise IntegrationSuggestionError("Pack id missing on suggestion", code="PACK_ID_MISSING")
        # Pack install is not a connector-catalog action; treat as platform-class write
        # that always requires approval (parity with PLATFORM_WRITE_TOOLS gating).
        return {
            "type": "install_department_pack",
            "status": "awaiting_confirm",
            "params": {
                "pack_id": pack_id,
                "source": "integration_suggestion_apply",
                "suggestion_id": suggestion_id,
                "tool_name": PACK_INSTALL_TOOL,
                "invoke_action": PACK_INSTALL_INVOKE,
            },
        }
    raise IntegrationSuggestionError("Unsupported suggestion type", code="UNSUPPORTED_SUGGESTION_TYPE")


def _approval_required_response(row: dict[str, Any]) -> dict[str, Any]:
    evidence = row.get("evidence") or {}
    pending = evidence.get("pending_approval") if isinstance(evidence, dict) else None
    if not isinstance(pending, dict):
        pending = _build_mutating_pending_task(row)
    suggestion_id = str(row.get("id") or "")
    suggestion = _serialize_suggestion(row)
    return {
        "workflowId": None,
        "redirectPath": None,
        "installResult": None,
        "requiresApproval": True,
        "pendingTask": pending,
        "confirmPath": f"/api/enterprise/integration-suggestions/{suggestion_id}/confirm",
        "suggestion": suggestion,
        "applySummary": {
            "suggestionType": row.get("suggestion_type"),
            "title": row.get("title"),
            "entities": [],
            "evidenceHighlights": ["Approval required before this write can run"],
            "redirectPath": None,
        },
    }


def _finalize_applied(
    client: Any,
    org_id: str,
    suggestion_id: str,
    row: dict[str, Any],
    result: dict[str, Any],
    *,
    actor_id: str | None = None,
    evidence_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = _now_iso()
    payload: dict[str, Any] = {"status": "applied", "updated_at": now}
    if evidence_override is not None:
        payload["evidence"] = evidence_override
    updated = (
        client.table("integration_suggestions")
        .update(payload)
        .eq("org_id", org_id)
        .eq("id", suggestion_id)
        .execute()
    )
    applied_row = (updated.data or [{**row, **payload}])[0]
    suggestion = _serialize_suggestion(applied_row)
    result["suggestion"] = suggestion
    result["applySummary"] = _build_apply_summary(result, row)
    result.setdefault("requiresApproval", False)
    result.setdefault("pendingTask", None)
    result.setdefault("confirmPath", None)

    if actor_id:
        write_audit_event(
            client,
            org_id,
            actor_id,
            AUDIT_INTEGRATION_SUGGESTION_APPLIED,
            RESOURCE_TYPE_INTEGRATION_SUGGESTION,
            suggestion_id,
            metadata={
                "suggestionType": row.get("suggestion_type"),
                "workflowId": result.get("workflowId"),
                "redirectPath": result.get("redirectPath"),
            },
        )

    logger.info(
        "integration_suggestion_applied org_id=%s suggestion_id=%s type=%s",
        org_id,
        suggestion_id,
        row.get("suggestion_type"),
    )
    return result


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
