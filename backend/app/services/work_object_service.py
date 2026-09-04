"""WorkObject lifecycle service.

Adds a durable business entity spine across runs/conversations without replacing
BusinessOutcome. BusinessOutcome remains the per-run evidence projection; a
WorkObject aggregates those outcomes over time.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from app.core.logging import get_logger
from app.core.safe_dict import safe_normalize_stored_dict

logger = get_logger(__name__)

WorkObjectType = Literal[
    "opportunity",
    "campaign",
    "candidate",
    "financial_issue",
    "ticket",
    "contract_matter",
    "incident",
    "vulnerability",
    "vendor",
    "feature",
    "issue_pr",
    "objective",
    "other",
]
WorkObjectStatus = Literal[
    "identified",
    "planned",
    "in_progress",
    "awaiting_approval",
    "blocked",
    "completed",
    "failed",
    "archived",
]
WorkObjectPriority = Literal["low", "medium", "high", "critical"]

WORK_OBJECT_TYPES: frozenset[str] = frozenset(
    {
        "opportunity",
        "campaign",
        "candidate",
        "financial_issue",
        "ticket",
        "contract_matter",
        "incident",
        "vulnerability",
        "vendor",
        "feature",
        "issue_pr",
        "objective",
        "other",
    }
)
WORK_OBJECT_STATUS: frozenset[str] = frozenset(
    {
        "identified",
        "planned",
        "in_progress",
        "awaiting_approval",
        "blocked",
        "completed",
        "failed",
        "archived",
    }
)
WORK_OBJECT_PRIORITY: frozenset[str] = frozenset({"low", "medium", "high", "critical"})

_ENTITY_TYPE_MAP: dict[str, WorkObjectType] = {
    "deal": "opportunity",
    "opportunity": "opportunity",
    "campaign": "campaign",
    "candidate": "candidate",
    "invoice": "financial_issue",
    "financial_issue": "financial_issue",
    "payment": "financial_issue",
    "ticket": "ticket",
    "case": "ticket",
    "contract": "contract_matter",
    "matter": "contract_matter",
    "incident": "incident",
    "vulnerability": "vulnerability",
    "cve": "vulnerability",
    "vendor": "vendor",
    "supplier": "vendor",
    "feature": "feature",
    "issue": "issue_pr",
    "pull_request": "issue_pr",
    "pr": "issue_pr",
    "objective": "objective",
    "goal": "objective",
}

_DEPARTMENT_BY_TYPE: dict[str, str] = {
    "opportunity": "sales",
    "campaign": "marketing",
    "candidate": "hr",
    "financial_issue": "finance",
    "ticket": "support",
    "contract_matter": "legal",
    "incident": "security",
    "vulnerability": "security",
    "vendor": "procurement",
    "feature": "engineering",
    "issue_pr": "engineering",
    "objective": "operations",
    "other": "operations",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_str(value: Any) -> str:
    return str(value or "").strip()


def _normalize_str_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[str] = []
    for item in value:
        text = _as_str(item)
        if text and text not in out:
            out.append(text)
    return out


def _merge_str_list(existing: Any, additions: list[str]) -> list[str]:
    merged = _normalize_str_list(existing)
    for item in additions:
        text = _as_str(item)
        if text and text not in merged:
            merged.append(text)
    return merged


def _normalize_work_object_type(value: Any) -> WorkObjectType:
    text = _as_str(value).lower().replace("-", "_")
    return text if text in WORK_OBJECT_TYPES else "other"


def _normalize_status(value: Any) -> WorkObjectStatus:
    text = _as_str(value).lower()
    return text if text in WORK_OBJECT_STATUS else "identified"


def _normalize_priority(value: Any) -> WorkObjectPriority:
    text = _as_str(value).lower()
    return text if text in WORK_OBJECT_PRIORITY else "medium"


def _priority_from_signal_score(score_0_100: float | None, fallback: WorkObjectPriority) -> WorkObjectPriority:
    if score_0_100 is None:
        return fallback
    try:
        score = float(score_0_100)
    except (TypeError, ValueError):
        return fallback
    if score >= 85:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _infer_type_from_entity(entity_type: str) -> WorkObjectType:
    normalized = entity_type.lower().replace("-", "_").replace(".", "_")
    if normalized in _ENTITY_TYPE_MAP:
        return _ENTITY_TYPE_MAP[normalized]
    for token, mapped in _ENTITY_TYPE_MAP.items():
        if token in normalized:
            return mapped
    return "other"


def infer_work_object_type(
    *,
    explicit_type: Any = None,
    entity_type: str | None = None,
    invoke_action: str | None = None,
) -> WorkObjectType:
    normalized_explicit = _normalize_work_object_type(explicit_type)
    if normalized_explicit != "other" or _as_str(explicit_type).lower() == "other":
        return normalized_explicit
    if entity_type:
        inferred = _infer_type_from_entity(entity_type)
        if inferred != "other":
            return inferred
    action = _as_str(invoke_action).lower().replace(".", "_")
    if "ticket" in action or "case" in action:
        return "ticket"
    if "campaign" in action:
        return "campaign"
    if "deal" in action or "opportunit" in action:
        return "opportunity"
    if "invoice" in action or "payment" in action or "billing" in action:
        return "financial_issue"
    if "contract" in action or "matter" in action:
        return "contract_matter"
    if "vulnerab" in action or "security" in action:
        return "vulnerability"
    if "candidate" in action or "applicant" in action:
        return "candidate"
    if "vendor" in action or "supplier" in action:
        return "vendor"
    if "issue" in action or "pull" in action or "pr" in action:
        return "issue_pr"
    return "objective"


def infer_work_object_department(work_object_type: WorkObjectType, explicit_department: Any = None) -> str:
    explicit = _as_str(explicit_department).lower().replace("-", "_")
    if explicit:
        return explicit
    return _DEPARTMENT_BY_TYPE.get(work_object_type, "operations")


def _derive_work_object_title(
    *,
    metadata: dict[str, Any],
    work_object_type: WorkObjectType,
    entity_type: str,
    entity_id: str,
    invoke_action: str,
    run_id: str,
) -> str:
    for key in ("work_object_title", "objective", "goal", "label", "summary", "title"):
        text = _as_str(metadata.get(key))
        if text:
            return text[:220]
    if entity_id:
        prefix = work_object_type.replace("_", " ").title()
        return f"{prefix} {entity_id}"[:220]
    if invoke_action:
        return invoke_action.replace(".", " ")[:220]
    if entity_type:
        return f"{entity_type.replace('_', ' ').title()} lifecycle"[:220]
    if run_id:
        return f"Work object {run_id[:8]}"
    return "Work object"


def _derive_objective(metadata: dict[str, Any], fallback: str) -> str | None:
    for key in ("objective", "goal", "summary", "label"):
        text = _as_str(metadata.get(key))
        if text:
            return text[:2000]
    text = _as_str(fallback)
    return text[:2000] if text else None


def _derive_work_status(terminal_status: str, *, current_status: str, metadata: dict[str, Any]) -> WorkObjectStatus:
    explicit = _normalize_status(metadata.get("work_object_status"))
    if _as_str(metadata.get("work_object_status")):
        return explicit
    closed = bool(metadata.get("work_object_closed"))
    if terminal_status in {"failed"}:
        return "failed"
    if terminal_status in {"cancelled"}:
        return "blocked"
    if terminal_status in {"flagged_for_review"}:
        return "awaiting_approval"
    if terminal_status in {"completed", "partial_success"}:
        if closed:
            return "completed"
        if current_status in {"completed", "archived"}:
            return current_status  # don't reopen explicitly closed objects.
        return "in_progress"
    return "identified"


def _resolve_existing_work_object(
    client: Any,
    *,
    org_id: str,
    explicit_work_object_id: str,
    work_object_type: WorkObjectType,
    entity_type: str,
    entity_id: str,
    conversation_id: str,
) -> dict[str, Any] | None:
    if explicit_work_object_id:
        row = (
            client.table("work_objects")
            .select("*")
            .eq("org_id", org_id)
            .eq("id", explicit_work_object_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if row:
            return row[0]

    if entity_type and entity_id:
        row = (
            client.table("work_objects")
            .select("*")
            .eq("org_id", org_id)
            .eq("object_type", work_object_type)
            .eq("external_entity_type", entity_type)
            .eq("external_entity_id", entity_id)
            .order("last_activity_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        if row:
            return row[0]

    if conversation_id:
        row = (
            client.table("work_objects")
            .select("*")
            .eq("org_id", org_id)
            .eq("anchor_conversation_id", conversation_id)
            .eq("object_type", work_object_type)
            .neq("status", "archived")
            .order("last_activity_at", desc=True)
            .limit(1)
            .execute()
            .data
            or []
        )
        if row:
            return row[0]
    return None


def _serialize_work_object(row: dict[str, Any]) -> dict[str, Any]:
    signal_priority = safe_normalize_stored_dict(safe_normalize_stored_dict(row.get("metadata")), key="signalPriority")
    return {
        "id": _as_str(row.get("id")),
        "orgId": _as_str(row.get("org_id")),
        "objectType": _as_str(row.get("object_type")),
        "department": _as_str(row.get("department")),
        "title": _as_str(row.get("title")),
        "objective": _as_str(row.get("objective")) or None,
        "owner": _as_str(row.get("owner_user_id") or row.get("owner")) or None,
        "status": _as_str(row.get("status")) or "identified",
        "priority": _as_str(row.get("priority")) or "medium",
        "externalEntityType": _as_str(row.get("external_entity_type")) or None,
        "externalEntityId": _as_str(row.get("external_entity_id")) or None,
        "anchorConversationId": _as_str(row.get("anchor_conversation_id")) or None,
        "systemsInvolved": _normalize_str_list(row.get("systems_involved")),
        "agentsInvolved": _normalize_str_list(row.get("agents_involved")),
        "businessOutcomeRefs": _normalize_str_list(row.get("business_outcome_refs")),
        "plan": safe_normalize_stored_dict(row.get("plan")),
        "humanApprovals": safe_normalize_stored_dict(row.get("human_approvals")),
        "outcome": safe_normalize_stored_dict(row.get("outcome")),
        "roi": safe_normalize_stored_dict(row.get("roi")),
        "metadata": safe_normalize_stored_dict(row.get("metadata")),
        "signalPriority": signal_priority or None,
        "createdAt": _as_str(row.get("created_at")) or None,
        "updatedAt": _as_str(row.get("updated_at")) or None,
        "lastActivityAt": _as_str(row.get("last_activity_at")) or None,
    }


def _serialize_work_object_event(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _as_str(row.get("id")),
        "workObjectId": _as_str(row.get("work_object_id")),
        "orgId": _as_str(row.get("org_id")),
        "runId": _as_str(row.get("run_id")) or None,
        "businessOutcomeId": _as_str(row.get("business_outcome_id")) or None,
        "conversationId": _as_str(row.get("conversation_id")) or None,
        "eventType": _as_str(row.get("event_type")) or "action_attributed",
        "actionName": _as_str(row.get("action_name")) or None,
        "actionStatus": _as_str(row.get("action_status")) or None,
        "systemName": _as_str(row.get("system_name")) or None,
        "agentId": _as_str(row.get("agent_id")) or None,
        "humanApproval": safe_normalize_stored_dict(row.get("human_approval")),
        "evidence": safe_normalize_stored_dict(row.get("evidence")),
        "outcome": safe_normalize_stored_dict(row.get("outcome")),
        "roi": safe_normalize_stored_dict(row.get("roi")),
        "auditRef": safe_normalize_stored_dict(row.get("audit_ref")),
        "metadata": safe_normalize_stored_dict(row.get("metadata")),
        "createdAt": _as_str(row.get("created_at")) or None,
    }


def record_execution_work_object(
    client: Any,
    *,
    org_id: str,
    run_id: str | None,
    terminal_status: str,
    metadata: dict[str, Any] | None,
    verified_output: dict[str, Any] | None,
    actor_id: str | None = None,
    workflow_id: str | None = None,
    error_summary: str | None = None,
) -> dict[str, Any] | None:
    """Resolve or create a WorkObject and append an attribution event."""
    meta = safe_normalize_stored_dict(metadata)
    verified = safe_normalize_stored_dict(meta, key="verified_output")
    verified.update(safe_normalize_stored_dict(verified_output))

    invoke_action = _as_str(meta.get("invoke_action") or meta.get("action_type") or meta.get("tool_name"))
    integration = _as_str(
        meta.get("integration")
        or meta.get("connector")
        or verified.get("integration")
        or safe_normalize_stored_dict(meta, key="structured").get("integration")
    ).lower()
    entity_type = _as_str(
        meta.get("work_object_entity_type")
        or verified.get("entity_type")
        or safe_normalize_stored_dict(meta, key="structured").get("entity_type")
    ).lower()
    entity_id = _as_str(
        meta.get("work_object_entity_id")
        or verified.get("entity_id")
        or safe_normalize_stored_dict(meta, key="structured").get("entity_id")
    )
    conversation_id = _as_str(meta.get("conversation_id"))
    explicit_work_object_id = _as_str(meta.get("work_object_id"))

    if not (invoke_action or entity_id or conversation_id or run_id):
        return None

    work_object_type = infer_work_object_type(
        explicit_type=meta.get("work_object_type"),
        entity_type=entity_type,
        invoke_action=invoke_action,
    )
    department = infer_work_object_department(work_object_type, meta.get("department"))
    now_iso = _now_iso()

    existing = _resolve_existing_work_object(
        client,
        org_id=org_id,
        explicit_work_object_id=explicit_work_object_id,
        work_object_type=work_object_type,
        entity_type=entity_type,
        entity_id=entity_id,
        conversation_id=conversation_id,
    )
    if existing is None:
        title = _derive_work_object_title(
            metadata=meta,
            work_object_type=work_object_type,
            entity_type=entity_type,
            entity_id=entity_id,
            invoke_action=invoke_action,
            run_id=_as_str(run_id),
        )
        objective = _derive_objective(meta, fallback=title)
        plan = safe_normalize_stored_dict(meta, key="plan")
        if not plan:
            plan = safe_normalize_stored_dict(meta, key="current_plan")
        owner = _as_str(meta.get("owner_user_id") or meta.get("owner") or actor_id) or None
        inserted = (
            client.table("work_objects")
            .insert(
                {
                    "org_id": org_id,
                    "object_type": work_object_type,
                    "department": department,
                    "title": title,
                    "objective": objective,
                    "owner_user_id": owner,
                    "status": _derive_work_status(terminal_status, current_status="identified", metadata=meta),
                    "priority": _normalize_priority(meta.get("priority")),
                    "external_entity_type": entity_type or None,
                    "external_entity_id": entity_id or None,
                    "anchor_conversation_id": conversation_id or None,
                    "systems_involved": _normalize_str_list([integration] if integration else []),
                    "agents_involved": _normalize_str_list(
                        [
                            _as_str(meta.get("agent_id") or ""),
                            _as_str(meta.get("agent_name") or ""),
                        ]
                    ),
                    "plan": plan,
                    "human_approvals": safe_normalize_stored_dict(meta, key="human_approvals"),
                    "outcome": {
                        "latest_status": terminal_status,
                        "latest_summary": _as_str(verified.get("summary") or error_summary) or None,
                        "latest_run_id": run_id,
                        "latest_workflow_id": workflow_id,
                        "latest_at": now_iso,
                    },
                    "roi": safe_normalize_stored_dict(meta, key="roi")
                    or {"outcome_effect": _as_str(meta.get("outcome_effect")) or None},
                    "business_outcome_refs": _normalize_str_list([run_id] if run_id else []),
                    "metadata": safe_normalize_stored_dict(meta, key="work_object_metadata"),
                    "last_activity_at": now_iso,
                }
            )
            .execute()
            .data
            or []
        )
        if not inserted:
            return None
        existing = inserted[0]
    else:
        current_status = _normalize_status(existing.get("status"))
        merged_systems = _merge_str_list(existing.get("systems_involved"), [integration] if integration else [])
        merged_agents = _merge_str_list(
            existing.get("agents_involved"),
            [
                _as_str(meta.get("agent_id") or ""),
                _as_str(meta.get("agent_name") or ""),
            ],
        )
        merged_refs = _merge_str_list(existing.get("business_outcome_refs"), [_as_str(run_id)] if run_id else [])
        plan = safe_normalize_stored_dict(existing.get("plan"))
        if not plan:
            plan = safe_normalize_stored_dict(meta, key="plan") or safe_normalize_stored_dict(meta, key="current_plan")
        human_approvals = safe_normalize_stored_dict(existing.get("human_approvals"))
        human_approvals.update(safe_normalize_stored_dict(meta, key="human_approvals"))
        if _as_str(meta.get("approval_status")):
            human_approvals["latest_status"] = _as_str(meta.get("approval_status"))
        roi = safe_normalize_stored_dict(existing.get("roi"))
        roi.update(safe_normalize_stored_dict(meta, key="roi"))
        if _as_str(meta.get("outcome_effect")) and "outcome_effect" not in roi:
            roi["outcome_effect"] = _as_str(meta.get("outcome_effect"))

        update_payload = {
            "status": _derive_work_status(terminal_status, current_status=current_status, metadata=meta),
            "priority": _normalize_priority(meta.get("priority") or existing.get("priority")),
            "systems_involved": merged_systems,
            "agents_involved": merged_agents,
            "business_outcome_refs": merged_refs,
            "plan": plan,
            "human_approvals": human_approvals,
            "outcome": {
                **safe_normalize_stored_dict(existing.get("outcome")),
                "latest_status": terminal_status,
                "latest_summary": _as_str(verified.get("summary") or error_summary) or None,
                "latest_run_id": run_id,
                "latest_workflow_id": workflow_id,
                "latest_at": now_iso,
            },
            "roi": roi,
            "last_activity_at": now_iso,
            "updated_at": now_iso,
        }
        objective = _derive_objective(meta, fallback="")
        if objective and not _as_str(existing.get("objective")):
            update_payload["objective"] = objective
        owner = _as_str(meta.get("owner_user_id") or meta.get("owner"))
        if owner:
            update_payload["owner_user_id"] = owner
        existing = (
            client.table("work_objects")
            .update(update_payload)
            .eq("id", existing.get("id"))
            .eq("org_id", org_id)
            .execute()
            .data
            or [existing]
        )[0]

    evidence: dict[str, Any] = {}
    if run_id:
        evidence["run_url"] = f"/runs/{run_id}"
        evidence["business_outcome_id"] = run_id
    if verified.get("external_url"):
        evidence["external_url"] = verified.get("external_url")
    if entity_type:
        evidence["entity_type"] = entity_type
    if entity_id:
        evidence["entity_id"] = entity_id

    event_id: str | None = None
    if run_id:
        existing_event = (
            client.table("work_object_events")
            .select("id")
            .eq("org_id", org_id)
            .eq("work_object_id", existing.get("id"))
            .eq("run_id", run_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if existing_event:
            event_id = _as_str(existing_event[0].get("id")) or None
    if event_id is None:
        event_row = (
            client.table("work_object_events")
            .insert(
                {
                    "org_id": org_id,
                    "work_object_id": existing.get("id"),
                    "run_id": run_id,
                    "business_outcome_id": run_id,
                    "conversation_id": conversation_id or None,
                    "event_type": "action_attributed",
                    "action_name": invoke_action or None,
                    "action_status": terminal_status,
                    "system_name": integration or None,
                    "agent_id": _as_str(meta.get("agent_id")) or None,
                    "human_approval": safe_normalize_stored_dict(meta, key="human_approvals"),
                    "evidence": evidence,
                    "outcome": {
                        "summary": _as_str(verified.get("summary") or error_summary) or None,
                        "status": terminal_status,
                    },
                    "roi": safe_normalize_stored_dict(meta, key="roi"),
                    "audit_ref": {
                        "source": _as_str(meta.get("source")),
                        "workflow_id": workflow_id,
                    },
                    "metadata": {
                        "invoke_action": invoke_action or None,
                        "integration": integration or None,
                        "outcome_effect": _as_str(meta.get("outcome_effect")) or None,
                    },
                }
            )
            .execute()
            .data
            or []
        )
        event_id = _as_str((event_row[0] if event_row else {}).get("id")) or None

    # Attach explainable department signal score so WorkObjects carry
    # score + rationale in list/detail views.
    try:
        from app.services.department_signal_scoring_service import (
            get_department_signal_scoring_service,
        )

        scorer = get_department_signal_scoring_service()
        scored = scorer.score_department(
            org_id,
            client=client,
            department=department,
            limit=1,
            work_object_ids=[_as_str(existing.get("id"))],
        )
        scored_rows = list(scored.get("priorities") or [])
        if scored_rows:
            top = scored_rows[0]
            existing_metadata = safe_normalize_stored_dict(existing.get("metadata"))
            existing_metadata["signalPriority"] = {
                "department": department,
                "score": top.get("priorityScore"),
                "band": top.get("priorityBand"),
                "explanations": list(top.get("explanations") or [])[:4],
                "contributions": list(top.get("signalContributions") or [])[:6],
                "gaps": list(top.get("gaps") or [])[:6],
                "capturedAt": scored.get("capturedAt"),
            }
            updated_priority = _priority_from_signal_score(
                top.get("priorityScore"), _normalize_priority(existing.get("priority"))
            )
            existing = (
                client.table("work_objects")
                .update(
                    {
                        "priority": updated_priority,
                        "metadata": existing_metadata,
                        "updated_at": _now_iso(),
                    }
                )
                .eq("id", existing.get("id"))
                .eq("org_id", org_id)
                .execute()
                .data
                or [existing]
            )[0]
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "work_object_signal_priority_skipped org_id=%s work_object_id=%s error=%s",
            org_id,
            existing.get("id"),
            exc,
        )

    return {
        "work_object_id": _as_str(existing.get("id")),
        "work_object": _serialize_work_object(existing),
        "event_id": event_id,
    }


def list_work_objects(
    client: Any,
    *,
    org_id: str,
    object_type: str | None = None,
    department: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    query = (
        client.table("work_objects")
        .select("*")
        .eq("org_id", org_id)
        .order("last_activity_at", desc=True)
        .limit(max(1, min(limit, 200)))
    )
    if object_type:
        query = query.eq("object_type", _normalize_work_object_type(object_type))
    if department:
        query = query.eq("department", _as_str(department).lower())
    if status:
        query = query.eq("status", _normalize_status(status))
    if priority:
        query = query.eq("priority", _normalize_priority(priority))
    rows = query.execute().data or []
    return [_serialize_work_object(row) for row in rows if isinstance(row, dict)]


def get_work_object(client: Any, *, org_id: str, work_object_id: str) -> dict[str, Any] | None:
    rows = (
        client.table("work_objects")
        .select("*")
        .eq("org_id", org_id)
        .eq("id", work_object_id)
        .limit(1)
        .execute()
        .data
        or []
    )
    if not rows:
        return None
    return _serialize_work_object(rows[0])


def list_work_object_events(
    client: Any,
    *,
    org_id: str,
    work_object_id: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = (
        client.table("work_object_events")
        .select("*")
        .eq("org_id", org_id)
        .eq("work_object_id", work_object_id)
        .order("created_at", desc=False)
        .limit(max(1, min(limit, 500)))
        .execute()
        .data
        or []
    )
    return [_serialize_work_object_event(row) for row in rows if isinstance(row, dict)]


def summarize_work_object_coverage(client: Any, *, org_id: str) -> dict[str, Any]:
    rows = (
        client.table("work_objects")
        .select("id, object_type, department, status, priority")
        .eq("org_id", org_id)
        .limit(1000)
        .execute()
        .data
        or []
    )
    by_type: dict[str, int] = {}
    by_department: dict[str, int] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        typ = _as_str(row.get("object_type")) or "other"
        by_type[typ] = by_type.get(typ, 0) + 1
        dep = _as_str(row.get("department")) or "operations"
        by_department[dep] = by_department.get(dep, 0) + 1
    return {
        "count": len(rows),
        "byType": by_type,
        "byDepartment": by_department,
    }
