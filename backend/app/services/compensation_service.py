"""Compensating transactions for failed autonomous workflow runs (STA-107)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.workflows.audit import write_audit_event
from app.workflows.constants import RESOURCE_TYPE_WORKFLOW_RUN
from app.core.safe_dict import safe_normalize_stored_dict

AUDIT_COMPENSATION_STARTED = "workflow.compensation.started"
AUDIT_COMPENSATION_COMPLETED = "workflow.compensation.completed"
AUDIT_COMPENSATION_NOTIFY = "workflow.compensation.notify"

# Legacy frozensets retained only as fallbacks during ActionSpec migration.
# Queries must prefer catalog_reversal (ActionSpec.compensating_action / supports_diff).
FORWARD_ACTIONS_WITH_SNAPSHOT = frozenset(
    {
        "hubspot.contacts.update",
        "hubspot.deals.update",
        "hubspot.deals.update_stage",
        "zendesk.tickets.update",
    }
)

COMPENSATABLE_FORWARD_ACTIONS = frozenset(
    {
        "hubspot.contacts.create",
        "hubspot.contacts.update",
        "hubspot.deals.create",
        "hubspot.deals.update",
        "hubspot.deals.update_stage",
        "hubspot.notes.create",
        "zendesk.tickets.create",
        "zendesk.tickets.update",
    }
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def should_track_compensation(ctx: Any, action: str) -> bool:
    from app.services.business_outcome.catalog_reversal import get_compensating_action

    return bool(ctx.run_id) and bool(get_compensating_action(action))


def prepare_forward_snapshot(ctx: Any, action: str, params: dict[str, Any]) -> dict[str, Any] | None:
    from app.services.business_outcome.catalog_reversal import supports_vendor_diff

    if not supports_vendor_diff(action):
        return None
    try:
        from app.services.tool_service import (
            _hubspot_connector_and_token,
            _zendesk_credentials,
        )
        from app.connectors.hubspot import get_contact, get_deal
        from app.connectors.zendesk import get_ticket

        if action.startswith("hubspot."):
            cid, token = _hubspot_connector_and_token(ctx, params)
            if action == "hubspot.contacts.update":
                contact_id = params.get("contact_id") or params.get("contactId")
                if not contact_id:
                    return None
                row = get_contact(token, contact_id=str(contact_id))
                return {"connector_id": cid, "properties": safe_normalize_stored_dict(row, key="properties")}
            if action in {"hubspot.deals.update", "hubspot.deals.update_stage"}:
                deal_id = params.get("deal_id") or params.get("dealId")
                if not deal_id:
                    return None
                row = get_deal(token, str(deal_id))
                return {
                    "connector_id": cid,
                    "properties": safe_normalize_stored_dict(row, key="properties"),
                    "dealstage": (row.get("properties") or {}).get("dealstage"),
                }
        if action == "zendesk.tickets.update":
            cid, subdomain, email, token, oauth_token = _zendesk_credentials(ctx, params)
            ticket_id = params.get("ticket_id") or params.get("ticketId")
            if not ticket_id:
                return None
            ticket = get_ticket(subdomain, email, token, ticket_id, oauth_access_token=oauth_token)
            return {
                "connector_id": cid,
                "status": ticket.get("status"),
                "priority": ticket.get("priority"),
                "tags": list(ticket.get("tags") or []),
            }
    except Exception:  # noqa: BLE001
        return None
    return None


def build_compensation_plan(
    *,
    forward_action: str,
    forward_params: dict[str, Any],
    forward_result: dict[str, Any],
    connector_id: str | None,
    snapshot: dict[str, Any] | None,
) -> tuple[str, dict[str, Any]] | None:
    cid = connector_id or forward_params.get("connector_id")
    base = {"connector_id": cid} if cid else {}

    if forward_action == "hubspot.contacts.create":
        contact_id = (forward_result.get("contact") or {}).get("id")
        if not contact_id:
            return None
        return "hubspot.contacts.delete", {**base, "contact_id": str(contact_id)}

    if forward_action == "hubspot.deals.create":
        deal_id = (forward_result.get("deal") or {}).get("id")
        if not deal_id:
            return None
        return "hubspot.deals.delete", {**base, "deal_id": str(deal_id)}

    if forward_action == "hubspot.notes.create":
        note_id = (forward_result.get("note") or {}).get("id")
        if not note_id:
            return None
        return "hubspot.notes.delete", {**base, "note_id": str(note_id)}

    if forward_action == "hubspot.contacts.update" and snapshot:
        contact_id = forward_params.get("contact_id") or forward_params.get("contactId")
        changed = forward_params.get("properties") if isinstance(forward_params.get("properties"), dict) else {}
        prior = snapshot.get("properties") if isinstance(snapshot.get("properties"), dict) else {}
        restore = {k: prior[k] for k in changed if k in prior}
        if not contact_id or not restore:
            return None
        return "hubspot.contacts.update", {**base, "contact_id": str(contact_id), "properties": restore}

    if forward_action == "hubspot.deals.update" and snapshot:
        deal_id = forward_params.get("deal_id") or forward_params.get("dealId")
        changed = forward_params.get("properties") if isinstance(forward_params.get("properties"), dict) else {}
        prior = snapshot.get("properties") if isinstance(snapshot.get("properties"), dict) else {}
        restore = {k: prior[k] for k in changed if k in prior}
        if not deal_id or not restore:
            return None
        return "hubspot.deals.update", {**base, "deal_id": str(deal_id), "properties": restore}

    if forward_action == "hubspot.deals.update_stage" and snapshot:
        deal_id = forward_params.get("deal_id") or forward_params.get("dealId")
        prior_stage = snapshot.get("dealstage")
        if not deal_id or not prior_stage:
            return None
        return "hubspot.deals.update_stage", {**base, "deal_id": str(deal_id), "dealstage": prior_stage}

    if forward_action == "zendesk.tickets.create":
        ticket_id = (forward_result.get("ticket") or {}).get("id")
        if not ticket_id:
            return None
        return "zendesk.tickets.close", {**base, "ticket_id": str(ticket_id)}

    if forward_action == "zendesk.tickets.update" and snapshot:
        ticket_id = forward_params.get("ticket_id") or forward_params.get("ticketId")
        if not ticket_id:
            return None
        comp: dict[str, Any] = {**base, "ticket_id": str(ticket_id)}
        if snapshot.get("status"):
            comp["status"] = snapshot["status"]
        if snapshot.get("priority"):
            comp["priority"] = snapshot["priority"]
        if snapshot.get("tags") is not None:
            comp["tags"] = snapshot["tags"]
        return "zendesk.tickets.update", comp

    return None


def record_compensatable_action(
    client: Any,
    *,
    org_id: str,
    run_id: str,
    step_id: str | None,
    forward_action: str,
    forward_params: dict[str, Any],
    forward_result: dict[str, Any],
    connector_id: str | None,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    plan = build_compensation_plan(
        forward_action=forward_action,
        forward_params=forward_params,
        forward_result=forward_result,
        connector_id=connector_id,
        snapshot=snapshot,
    )
    if not plan:
        return None
    compensating_action, compensating_params = plan
    row = {
        "org_id": org_id,
        "run_id": run_id,
        "step_id": step_id,
        "forward_action": forward_action,
        "compensating_action": compensating_action,
        "connector_id": connector_id,
        "forward_params": forward_params,
        "compensating_params": compensating_params,
        "status": "pending",
    }
    inserted = client.table("workflow_compensation_records").insert(row).execute()
    return dict(inserted.data[0]) if inserted.data else None


def list_compensation_records(
    client: Any,
    org_id: str,
    run_id: str,
    *,
    status: str | None = "pending",
) -> list[dict[str, Any]]:
    query = (
        client.table("workflow_compensation_records")
        .select("*")
        .eq("org_id", org_id)
        .eq("run_id", run_id)
        .order("created_at", desc=False)
    )
    if status:
        query = query.eq("status", status)
    return list(query.execute().data or [])


def authorize_compensation_write(forward_action: str, compensating_action: str) -> None:
    """Refuse undo writes that bypass catalog_write_authority / catalog reversal.

    Every BusinessOutcome undo path must call this before invoke_tool.
    """
    from app.services.business_outcome.catalog_reversal import get_compensating_action
    from app.services.catalog_write_authority import invoke_action_requires_write_approval

    expected = get_compensating_action(forward_action)
    if not expected:
        raise PermissionError(
            f"No catalog compensating action for forward write {forward_action!r}; undo blocked"
        )
    if str(compensating_action or "").strip() != str(expected).strip():
        raise PermissionError(
            f"Compensating action {compensating_action!r} does not match catalog "
            f"counterpart {expected!r} for {forward_action!r}"
        )
    if not invoke_action_requires_write_approval(compensating_action):
        # Compensating counterparts are writes; if catalog says otherwise, refuse.
        raise PermissionError(
            f"Compensating action {compensating_action!r} is not classified as a write "
            "by catalog_write_authority; undo blocked"
        )


def execute_compensations(
    client: Any,
    settings: Any,
    *,
    org_id: str,
    run_id: str,
    actor_id: str,
    environment_name: str = "default",
) -> dict[str, Any]:
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    records = list_compensation_records(client, org_id, run_id, status="pending")
    if not records:
        return {"runId": run_id, "compensated": 0, "failed": 0, "skipped": 0, "results": []}

    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_COMPENSATION_STARTED,
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata={"pendingCount": len(records)},
    )

    compensated = failed = skipped = 0
    results: list[dict[str, Any]] = []
    for record in records:
        record_id = str(record["id"])
        comp_action = str(record["compensating_action"])
        forward_action = str(record.get("forward_action") or record.get("original_action") or "")
        comp_params = record.get("compensating_params") if isinstance(record.get("compensating_params"), dict) else {}
        ctx = ToolContext(
            settings=settings,
            client=client,
            org_id=org_id,
            actor_id=actor_id,
            environment_name=environment_name,
            run_id=run_id,
            step_id=record.get("step_id"),
            step_type="compensation",
            connector_id=str(record.get("connector_id") or comp_params.get("connector_id") or "") or None,
        )
        try:
            if forward_action:
                authorize_compensation_write(forward_action, comp_action)
            else:
                # Still require write classification when forward action is absent.
                from app.services.catalog_write_authority import invoke_action_requires_write_approval

                if not invoke_action_requires_write_approval(comp_action):
                    raise PermissionError(
                        f"Compensating action {comp_action!r} is not a catalog write; undo blocked"
                    )
            outcome = invoke_tool(ctx, comp_action, comp_params)
            if outcome.success:
                client.table("workflow_compensation_records").update(
                    {"status": "compensated", "compensated_at": _now(), "error_message": None}
                ).eq("id", record_id).execute()
                compensated += 1
                results.append({"recordId": record_id, "action": comp_action, "status": "compensated"})
            else:
                client.table("workflow_compensation_records").update(
                    {
                        "status": "failed",
                        "error_message": (outcome.error_message or outcome.error_code or "compensation failed")[:500],
                    }
                ).eq("id", record_id).execute()
                failed += 1
                results.append(
                    {
                        "recordId": record_id,
                        "action": comp_action,
                        "status": "failed",
                        "error": outcome.error_message,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            client.table("workflow_compensation_records").update(
                {"status": "failed", "error_message": str(exc)[:500]}
            ).eq("id", record_id).execute()
            failed += 1
            results.append({"recordId": record_id, "action": comp_action, "status": "failed", "error": str(exc)})

    summary = {
        "runId": run_id,
        "compensated": compensated,
        "failed": failed,
        "skipped": skipped,
        "results": results,
    }
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_COMPENSATION_COMPLETED,
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata=summary,
    )
    return summary


def _org_compensation_webhook_connector_id(client: Any, org_id: str) -> str | None:
    row = client.table("organizations").select("settings").eq("id", org_id).limit(1).execute().data
    if not row:
        return None
    settings = row[0].get("settings") if isinstance(row[0].get("settings"), dict) else {}
    enterprise = settings.get("enterprise") if isinstance(settings.get("enterprise"), dict) else {}
    notify = enterprise.get("compensationNotify") if isinstance(enterprise.get("compensationNotify"), dict) else {}
    connector_id = notify.get("connectorId") or notify.get("webhookConnectorId")
    return str(connector_id) if connector_id else None


def notify_compensation_webhook(
    client: Any,
    settings: Any,
    *,
    org_id: str,
    run_id: str,
    actor_id: str,
    summary: dict[str, Any],
    environment_name: str = "default",
) -> dict[str, Any] | None:
    connector_id = _org_compensation_webhook_connector_id(client, org_id)
    if not connector_id:
        return None
    from app.services.tool_service import invoke_tool
    from app.services.tool_types import ToolContext

    payload = {
        "event": "workflow.compensation.partial_failure",
        "runId": run_id,
        "orgId": org_id,
        "summary": summary,
    }
    ctx = ToolContext(
        settings=settings,
        client=client,
        org_id=org_id,
        actor_id=actor_id,
        environment_name=environment_name,
        run_id=run_id,
        step_type="compensation_notify",
        connector_id=connector_id,
    )
    result = invoke_tool(
        ctx,
        "webhook.post",
        {"connector_id": connector_id, "payload": payload},
    )
    write_audit_event(
        client,
        org_id=org_id,
        actor_id=actor_id,
        action=AUDIT_COMPENSATION_NOTIFY,
        resource_type=RESOURCE_TYPE_WORKFLOW_RUN,
        resource_id=run_id,
        metadata={"success": result.success, "connectorId": connector_id},
    )
    return {"success": result.success, "connectorId": connector_id}


def compensate_failed_autonomous_run(
    client: Any,
    settings: Any,
    *,
    org_id: str,
    run_id: str,
    actor_id: str,
    parameters: dict[str, Any],
    environment_name: str = "default",
) -> dict[str, Any] | None:
    if not parameters.get("_autonomous_run"):
        return None
    summary = execute_compensations(
        client,
        settings,
        org_id=org_id,
        run_id=run_id,
        actor_id=actor_id,
        environment_name=environment_name,
    )
    if summary["compensated"] or summary["failed"]:
        notify_compensation_webhook(
            client,
            settings,
            org_id=org_id,
            run_id=run_id,
            actor_id=actor_id,
            summary=summary,
            environment_name=environment_name,
        )
    return summary
