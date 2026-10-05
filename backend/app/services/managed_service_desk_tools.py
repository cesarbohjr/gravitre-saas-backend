"""Managed/Nango service desk tool executors.

These tools use Gravitre's canonical invoke_tool spine. Nango provides managed
authorization/proxying only; permissions, approvals, audit, retries, and write
verification remain owned by Gravitre.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.connectors.nango_client import proxy_request
from app.connectors.repository import get_connector, get_connector_by_type
from app.connectors.rate_limit import enforce_rate_limit
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolError,
    ToolValidationError,
)


def _managed_connector(
    ctx: ToolContext,
    vendor: str,
    params: dict[str, Any],
) -> tuple[str, str, str]:
    connector_id = params.get("connector_id") or params.get("connectorId") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(
            ctx.client,
            ctx.org_id,
            str(connector_id),
            environment_name=ctx.environment_name,
        )
    else:
        conn = get_connector_by_type(
            ctx.client,
            ctx.org_id,
            vendor,
            environment_name=ctx.environment_name,
        )
    if not conn:
        raise ToolValidationError(f"No active {vendor} connector found for org")

    stored_vendor = str(conn.get("type") or conn.get("vendor") or "").strip().lower()
    if stored_vendor != vendor:
        raise ToolValidationError("Connector vendor mismatch")

    if conn.get("org_id") != ctx.org_id or str(conn.get("environment") or ctx.environment_name) != ctx.environment_name:
        raise ToolValidationError("Connector organization or environment mismatch")
    if conn.get("status") not in {"active", "connected", "healthy", "syncing"}:
        raise ToolAuthExpiredError("Connector is not active; reconnect the connector")
    cid = str(conn["id"])
    config = conn.get("config") if isinstance(conn.get("config"), dict) else {}
    if str(config.get("auth_provider") or "").strip().lower() != "managed":
        raise ToolValidationError(f"{vendor} connector is not using managed authorization")

    connection_id = str(config.get("managed_connection_id") or "").strip()
    integration_id = str(config.get("managed_integration_id") or "").strip()
    from app.connectors.nango_registry import get_nango_connector_spec
    spec = get_nango_connector_spec(vendor)
    if spec is None or integration_id != spec.integration_id:
        raise ToolValidationError("Managed integration mismatch")
    if not connection_id or not integration_id:
        raise ToolAuthExpiredError(
            f"{vendor} authorization is incomplete; reconnect the connector"
        )

    enforce_rate_limit(ctx.client, ctx.org_id, vendor, vendor, cid)
    return cid, connection_id, integration_id


def _request(
    ctx: ToolContext,
    params: dict[str, Any],
    *,
    vendor: str,
    method: str,
    endpoint: str,
    query: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    cid, connection_id, integration_id = _managed_connector(ctx, vendor, params)
    try:
        response = proxy_request(
            ctx.settings,
            method=method,
            endpoint=endpoint,
            connection_id=connection_id,
            integration_id=integration_id,
            params=query,
            json_body=body,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status in {401, 403}:
            raise ToolAuthExpiredError(
                f"{vendor} managed authorization was rejected by the provider"
            ) from exc
        raise ToolValidationError(
            f"{vendor} request failed ({status})"
        ) from exc
    except httpx.TimeoutException as exc:
        raise ToolError(f"{vendor} request timed out", code="connector_timeout") from exc
    except httpx.TransportError as exc:
        raise ToolError(f"{vendor} request failed: {exc}") from exc

    try:
        data = response.json() if response.content else {}
    except ValueError:
        data = {"raw": response.text[:2000]}
    if not isinstance(data, dict):
        data = {"result": data}
    return cid, data


def _ticket_id(value: Any) -> str:
    text = str(value)
    if not text.isascii() or not text.isdigit() or int(text) <= 0:
        raise ToolValidationError("ticket_id must be a positive integer")
    return text


def _freshservice_tickets_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    allowed = ("filter", "requester_id", "email", "updated_since", "type", "workspace_id", "page", "per_page")
    query = {key: params[key] for key in allowed if params.get(key) is not None}
    cid, data = _request(
        ctx,
        params,
        vendor="freshservice",
        method="GET",
        endpoint="/api/v2/tickets",
        query=query or None,
    )
    tickets = data.get("tickets") if isinstance(data.get("tickets"), list) else []
    return NormalizedResult(
        success=True,
        action="freshservice.tickets.list",
        connector_id=cid,
        data={"tickets": tickets, "count": len(tickets), **{k: v for k, v in data.items() if k != "tickets"}},
    )


def _freshservice_tickets_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    ticket_id = params.get("ticket_id") or params.get("ticketId") or params.get("id")
    if ticket_id is None:
        raise ToolValidationError("freshservice.tickets.get requires ticket_id")
    ticket_id = _ticket_id(ticket_id)
    query = {}
    if params.get("include") is not None:
        query["include"] = params["include"]
    cid, data = _request(
        ctx,
        params,
        vendor="freshservice",
        method="GET",
        endpoint=f"/api/v2/tickets/{ticket_id}",
        query=query or None,
    )
    ticket = data.get("ticket") if isinstance(data.get("ticket"), dict) else data
    normalized_id = str(ticket.get("id") or ticket_id) if isinstance(ticket, dict) else str(ticket_id)
    return NormalizedResult(
        success=True,
        action="freshservice.tickets.get",
        connector_id=cid,
        data={"ticket": ticket, "id": normalized_id},
    )


def _freshservice_ticket_activities(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    ticket_id = params.get("ticket_id") or params.get("ticketId") or params.get("id")
    if ticket_id is None:
        raise ToolValidationError("freshservice.tickets.activities requires ticket_id")
    ticket_id = _ticket_id(ticket_id)
    cid, data = _request(
        ctx,
        params,
        vendor="freshservice",
        method="GET",
        endpoint=f"/api/v2/tickets/{ticket_id}/activities",
    )
    return NormalizedResult(
        success=True,
        action="freshservice.tickets.activities",
        connector_id=cid,
        data={"ticket_id": str(ticket_id), **data},
    )


def _freshservice_ticket_update_status(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    ticket_id = params.get("ticket_id") or params.get("ticketId") or params.get("id")
    status_value = params.get("status")
    if ticket_id is None or status_value is None:
        raise ToolValidationError(
            "freshservice.tickets.update_status requires ticket_id and status"
        )
    ticket_id = _ticket_id(ticket_id)
    cid, data = _request(
        ctx,
        params,
        vendor="freshservice",
        method="PUT",
        endpoint=f"/api/v2/tickets/{ticket_id}",
        body={"status": status_value},
    )
    ticket = data.get("ticket") if isinstance(data.get("ticket"), dict) else data
    normalized_id = str(ticket.get("id") or ticket_id) if isinstance(ticket, dict) else str(ticket_id)
    return NormalizedResult(
        success=True,
        action="freshservice.tickets.update_status",
        connector_id=cid,
        data={
            "ticket": ticket,
            "id": normalized_id,
            "ticket_id": normalized_id,
            "outcome_effect": "updated",
        },
    )


MANAGED_SERVICE_DESK_TOOL_EXECUTORS = {
    "freshservice.tickets.list": _freshservice_tickets_list,
    "freshservice.tickets.get": _freshservice_tickets_get,
    "freshservice.tickets.activities": _freshservice_ticket_activities,
    "freshservice.tickets.update_status": _freshservice_ticket_update_status,
}
