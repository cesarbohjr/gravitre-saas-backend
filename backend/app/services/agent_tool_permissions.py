"""Agent-scoped tool permissions (STA-11)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.tool_types import ToolContext, ToolPermissionDeniedError

# Canonical tool action → required scopes (any one match grants access).
ACTION_REQUIRED_SCOPES: dict[str, list[str]] = {
    "slack.post_message": ["slack:messages:write", "slack:*"],
    "email.send": ["email:send", "email:*"],
    "webhook.post": ["webhook:post", "webhook:*"],
    "hubspot.contacts.get": ["hubspot:contacts:read", "hubspot:*"],
    "hubspot.contacts.update": ["hubspot:contacts:write", "hubspot:*"],
    "hubspot.notes.create": ["hubspot:notes:write", "hubspot:*"],
    "hubspot.deals.update_stage": ["hubspot:deals:write", "hubspot:*"],
    "hubspot.sequences.enroll": ["hubspot:sequences:enroll", "hubspot:contacts:write", "hubspot:*"],
    "hubspot.contacts.create": ["hubspot:contacts:write", "hubspot:*"],
    "hubspot.contacts.search": ["hubspot:contacts:read", "hubspot:*"],
    "hubspot.deals.get": ["hubspot:deals:read", "hubspot:*"],
    "hubspot.deals.create": ["hubspot:deals:write", "hubspot:*"],
    "hubspot.deals.update": ["hubspot:deals:write", "hubspot:*"],
    "hubspot.lists.add_contact": ["hubspot:lists:write", "hubspot:contacts:write", "hubspot:*"],
    "salesforce.leads.get": ["salesforce:leads:read", "salesforce:*"],
    "salesforce.leads.update": ["salesforce:leads:write", "salesforce:*"],
    "salesforce.accounts.get": ["salesforce:accounts:read", "salesforce:*"],
    "salesforce.opportunities.create": ["salesforce:opportunities:write", "salesforce:*"],
    "salesforce.opportunities.update_stage": ["salesforce:opportunities:write", "salesforce:*"],
    "salesforce.tasks.create": ["salesforce:tasks:write", "salesforce:*"],
    "salesforce.leads.create": ["salesforce:leads:write", "salesforce:*"],
    "salesforce.leads.search": ["salesforce:leads:read", "salesforce:*"],
    "salesforce.opportunities.get": ["salesforce:opportunities:read", "salesforce:*"],
    "salesforce.opportunities.update": ["salesforce:opportunities:write", "salesforce:*"],
    "salesforce.accounts.create": ["salesforce:accounts:write", "salesforce:*"],
    "salesforce.accounts.update": ["salesforce:accounts:write", "salesforce:*"],
    "quickbooks.invoices.list": ["quickbooks:invoices:read", "quickbooks:*"],
    "quickbooks.invoices.get": ["quickbooks:invoices:read", "quickbooks:*"],
    "quickbooks.payments.list": ["quickbooks:payments:read", "quickbooks:*"],
    "quickbooks.vendors.get": ["quickbooks:vendors:read", "quickbooks:*"],
    "quickbooks.customers.list": ["quickbooks:customers:read", "quickbooks:*"],
    "quickbooks.customers.get": ["quickbooks:customers:read", "quickbooks:*"],
    "quickbooks.customers.search": ["quickbooks:customers:read", "quickbooks:*"],
    "quickbooks.vendors.list": ["quickbooks:vendors:read", "quickbooks:*"],
    "quickbooks.accounts.list": ["quickbooks:accounts:read", "quickbooks:*"],
    "quickbooks.bills.list": ["quickbooks:bills:read", "quickbooks:*"],
    "quickbooks.bills.get": ["quickbooks:bills:read", "quickbooks:*"],
    "quickbooks.companyinfo.get": ["quickbooks:company:read", "quickbooks:*"],
    "stripe.invoices.list": ["stripe:invoices:read", "stripe:*"],
    "stripe.subscriptions.get": ["stripe:subscriptions:read", "stripe:*"],
    "zendesk.tickets.get": ["zendesk:tickets:read", "zendesk:*"],
    "zendesk.tickets.create": ["zendesk:tickets:write", "zendesk:*"],
    "zendesk.tickets.update": ["zendesk:tickets:write", "zendesk:*"],
    "zendesk.tickets.add_tags": ["zendesk:tickets:write", "zendesk:*"],
    "github.pulls.list": ["github:pulls:read", "github:*"],
    "github.issues.create": ["github:issues:write", "github:*"],
    "github.issues.comment": ["github:issues:write", "github:*"],
    "github.pulls.request_reviewer": ["github:pulls:write", "github:*"],
    "calendar.freebusy": ["calendar:read", "calendar:*"],
    "calendar.events.create": ["calendar:write", "calendar:*"],
}

WILDCARD_SCOPE = "*"


def required_scopes_for_action(action: str) -> list[str]:
    if action in ACTION_REQUIRED_SCOPES:
        return list(ACTION_REQUIRED_SCOPES[action])
    prefix = action.split(".", 1)[0]
    return [f"{prefix}:*", action]


def _scope_satisfied(granted: list[str], required: list[str]) -> bool:
    granted_set = {s.strip() for s in granted if s and s.strip()}
    if WILDCARD_SCOPE in granted_set:
        return True
    for req in required:
        if req in granted_set:
            return True
        if ":" in req:
            family = req.split(":", 1)[0] + ":*"
            if family in granted_set:
                return True
    return False


def _is_expired(row: dict[str, Any]) -> bool:
    expires = row.get("expires_at")
    if not expires:
        return False
    if isinstance(expires, str):
        expires_at = datetime.fromisoformat(expires.replace("Z", "+00:00"))
    else:
        expires_at = expires
    return expires_at <= datetime.now(timezone.utc)


def list_agent_tool_permissions(client: Any, org_id: str, agent_id: str) -> list[dict[str, Any]]:
    r = (
        client.table("agent_tool_permissions")
        .select(
            "id, org_id, agent_id, connector_id, connector_type, scopes, "
            "granted_by, granted_at, expires_at, created_at, updated_at"
        )
        .eq("org_id", org_id)
        .eq("agent_id", agent_id)
        .execute()
    )
    return list(r.data or [])


def upsert_agent_tool_permission(
    client: Any,
    org_id: str,
    agent_id: str,
    *,
    connector_id: str | None,
    connector_type: str | None,
    scopes: list[str],
    granted_by: str | None = None,
    expires_at: str | None = None,
) -> dict[str, Any]:
    if not connector_id and not connector_type:
        raise ValueError("connector_id or connector_type is required")
    row = {
        "org_id": org_id,
        "agent_id": agent_id,
        "connector_id": connector_id,
        "connector_type": connector_type,
        "scopes": scopes,
        "granted_by": granted_by,
        "expires_at": expires_at,
    }
    q = (
        client.table("agent_tool_permissions")
        .select("id")
        .eq("org_id", org_id)
        .eq("agent_id", agent_id)
    )
    if connector_id:
        q = q.eq("connector_id", connector_id)
    else:
        q = q.is_("connector_id", "null").eq("connector_type", connector_type)
    existing = q.limit(1).execute()
    if existing.data:
        rid = existing.data[0]["id"]
        r = client.table("agent_tool_permissions").update(row).eq("id", rid).execute()
    else:
        r = client.table("agent_tool_permissions").insert(row).execute()
    data = r.data or []
    return data[0] if data else row


def delete_agent_tool_permission(client: Any, org_id: str, permission_id: str) -> None:
    client.table("agent_tool_permissions").delete().eq("org_id", org_id).eq("id", permission_id).execute()


def assert_agent_tool_permission(
    ctx: ToolContext,
    action: str,
    connector_id: str | None,
    connector_type: str | None,
) -> None:
    """Enforce agent-scoped permissions. Workflows without agent_id skip this check."""
    if not ctx.agent_id:
        return

    required = required_scopes_for_action(action)
    ctype = connector_type or (action.split(".", 1)[0] if "." in action else action)
    rows = list_agent_tool_permissions(ctx.client, ctx.org_id, ctx.agent_id)
    active = [r for r in rows if not _is_expired(r)]
    if not active:
        raise ToolPermissionDeniedError(f"Agent {ctx.agent_id} has no tool permissions")

    matching: list[dict[str, Any]] = []
    for row in active:
        row_connector = row.get("connector_id")
        row_type = (row.get("connector_type") or "").strip()
        if connector_id and row_connector and str(row_connector) == str(connector_id):
            matching.append(row)
        elif connector_id and row_connector:
            continue
        elif row_type and row_type == ctype:
            matching.append(row)
        elif not row_connector and not row_type:
            matching.append(row)

    if not matching:
        raise ToolPermissionDeniedError(
            f"Agent lacks permission for {action} on connector type {ctype}"
        )

    for row in matching:
        scopes = row.get("scopes") or []
        if isinstance(scopes, list) and _scope_satisfied(scopes, required):
            return

    raise ToolPermissionDeniedError(
        f"Agent lacks required scope for {action}: {', '.join(required)}"
    )


def default_demo_scopes_for_system(system: str) -> list[str]:
    """Scopes granted to demo seed agents by declared systems[]."""
    if system == "hubspot":
        return [
            "hubspot:contacts:read",
            "hubspot:contacts:write",
            "hubspot:deals:write",
            "hubspot:notes:write",
            "hubspot:sequences:enroll",
            "hubspot:lists:write",
            "hubspot:deals:read",
            "hubspot:*",
        ]
    if system == "salesforce":
        return [
            "salesforce:leads:read",
            "salesforce:leads:write",
            "salesforce:accounts:read",
            "salesforce:accounts:write",
            "salesforce:opportunities:read",
            "salesforce:opportunities:write",
            "salesforce:tasks:write",
            "salesforce:*",
        ]
    if system == "quickbooks":
        return [
            "quickbooks:invoices:read",
            "quickbooks:payments:read",
            "quickbooks:vendors:read",
            "quickbooks:customers:read",
            "quickbooks:accounts:read",
            "quickbooks:bills:read",
            "quickbooks:company:read",
            "quickbooks:*",
        ]
    if system == "stripe":
        return [
            "stripe:invoices:read",
            "stripe:subscriptions:read",
            "stripe:*",
        ]
    if system == "slack":
        return ["slack:messages:write", "slack:*"]
    return [f"{system}:*"]
