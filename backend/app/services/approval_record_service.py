"""Contract-table approval records — populate numeric_value at creation when genuinely available."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

NUMERIC_FIELD_SPECS: tuple[tuple[str, str], ...] = (
    ("invoice_amount", "invoice_amount"),
    ("amount", "amount"),
    ("deal_value", "deal_value"),
    ("budget_request", "budget_request"),
    ("total", "total"),
    ("amount_total", "invoice_amount"),
    ("mrr_cents", "subscription_mrr_cents"),
)


def _coerce_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_numeric_value(
    *,
    context: dict[str, Any] | None = None,
    parameters: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> tuple[float | None, str | None, str | None]:
    """Return (numeric_value, currency, label) when a genuine amount is present."""
    sources: list[dict[str, Any]] = []
    for block in (parameters, context, payload):
        if isinstance(block, dict):
            sources.append(block)
    currency = "USD"
    for source in sources:
        raw_currency = source.get("numeric_value_currency") or source.get("currency")
        if raw_currency:
            currency = str(raw_currency).strip().upper() or currency
        for key, label in NUMERIC_FIELD_SPECS:
            if key not in source:
                continue
            parsed = _coerce_float(source.get(key))
            if parsed is not None:
                return parsed, currency, label
        nested = source.get("upstream_outputs")
        if isinstance(nested, dict):
            for node_output in nested.values():
                if not isinstance(node_output, dict):
                    continue
                for key, field_label in NUMERIC_FIELD_SPECS:
                    parsed = _coerce_float(node_output.get(key))
                    if parsed is not None:
                        return parsed, currency, field_label
    return None, None, None


def create_contract_approval(
    client: Any,
    *,
    org_id: str,
    title: str,
    approval_type: str = "workflow",
    priority: str = "medium",
    status: str = "pending",
    run_id: str | None = None,
    requested_by: str | None = None,
    description: str | None = None,
    context: dict[str, Any] | None = None,
    parameters: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Insert a row into public.approvals; numeric_value is set only when extractable."""
    numeric_value, currency, label = extract_numeric_value(
        context=context,
        parameters=parameters,
        payload=payload,
    )
    row: dict[str, Any] = {
        "org_id": org_id,
        "run_id": run_id,
        "title": title,
        "description": description,
        "type": approval_type,
        "priority": priority,
        "status": status,
        "requested_by": requested_by,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "context": context or {},
        "numeric_value": numeric_value,
        "numeric_value_currency": currency if numeric_value is not None else None,
        "numeric_value_label": label if numeric_value is not None else None,
    }
    try:
        if run_id:
            existing = (
                client.table("approvals")
                .select("id")
                .eq("org_id", org_id)
                .eq("run_id", run_id)
                .limit(1)
                .execute()
                .data
                or []
            )
            if existing:
                updated = (
                    client.table("approvals")
                    .update(row)
                    .eq("id", existing[0]["id"])
                    .eq("org_id", org_id)
                    .execute()
                )
                return updated.data[0] if updated.data else row
        inserted = client.table("approvals").insert(row).execute()
        return inserted.data[0] if inserted.data else row
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "contract_approval_create_failed org=%s run=%s error=%s",
            org_id,
            run_id,
            exc,
        )
        return None


def finalize_contract_approval(
    client: Any,
    *,
    org_id: str,
    status: str,
    reviewed_by: str | None,
    run_id: str | None = None,
    agent_job_id: str | None = None,
) -> None:
    """Mark an existing contract approval approved/rejected after human review."""
    if not run_id and not agent_job_id:
        return
    try:
        query = client.table("approvals").select("id").eq("org_id", org_id)
        if run_id:
            query = query.eq("run_id", run_id)
        else:
            query = query.contains("context", {"agent_job_id": agent_job_id})
        rows = query.limit(1).execute().data or []
        if not rows:
            return
        client.table("approvals").update(
            {
                "status": status,
                "reviewed_by": reviewed_by,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", rows[0]["id"]).eq("org_id", org_id).execute()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "contract_approval_finalize_failed org=%s run=%s job=%s error=%s",
            org_id,
            run_id,
            agent_job_id,
            exc,
        )


def sync_workflow_pending_approval(
    client: Any,
    *,
    org_id: str,
    run_id: str,
    workflow_id: str,
    workflow_name: str | None,
    requested_by: str | None,
    parameters: dict[str, Any] | None,
    required_approvals: int,
) -> None:
    priority = "high" if int(required_approvals or 0) >= 2 else "medium"
    create_contract_approval(
        client,
        org_id=org_id,
        run_id=run_id,
        title=f"Approve workflow: {workflow_name or workflow_id}",
        description="Workflow execution requires human approval before running.",
        approval_type="workflow",
        priority=priority,
        status="pending",
        requested_by=requested_by,
        context={"workflow_id": workflow_id, "gate_type": "execute"},
        parameters=parameters,
    )


def maybe_create_agent_job_approval(
    client: Any,
    job: dict[str, Any],
    result: dict[str, Any],
) -> None:
    if not result.get("requires_approval") and not result.get("needs_human_input"):
        return
    org_id = str(job.get("org_id") or "")
    job_id = str(job.get("id") or "")
    if not org_id or not job_id:
        return
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    requested_by = str(payload.get("actor_id") or payload.get("user_id") or job.get("created_by") or "") or None
    title = str(result.get("action_title") or payload.get("task") or "Agent task approval")
    description = (
        str(result.get("action_description") or result.get("analysis_summary") or "")[:2000] or None
    )
    create_contract_approval(
        client,
        org_id=org_id,
        title=title,
        description=description,
        approval_type="agent_task",
        priority="medium",
        status="pending",
        requested_by=requested_by,
        context={"agent_job_id": job_id, "kind": job.get("kind")},
        parameters=payload if isinstance(payload, dict) else None,
        payload=result,
    )
    if requested_by:
        try:
            from app.services.agent_activity_notifications import notify_agent_needs_approval

            agent_id = str(payload.get("agent_id") or payload.get("agentId") or "").strip() or None
            notify_agent_needs_approval(
                client,
                org_id=org_id,
                user_id=requested_by,
                agent_id=agent_id,
                job_id=job_id,
                title=f"Approval needed: {title}"[:200],
                body=(description or "An agent task is waiting for your approval.")[:2000],
                result_url="/approvals",
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("agent_job_approval_notify_skipped job=%s error=%s", job_id, exc)
