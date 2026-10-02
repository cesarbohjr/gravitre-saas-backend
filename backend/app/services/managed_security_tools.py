"""Managed/Nango security operations tool executors.

Nango owns managed authorization/proxying only. Gravitre retains tenant
isolation, permissions, audit, execution governance, and outcome truth.
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
    conn = (
        get_connector(
            ctx.client,
            ctx.org_id,
            str(connector_id),
            environment_name=ctx.environment_name,
        )
        if connector_id
        else get_connector_by_type(
            ctx.client,
            ctx.org_id,
            vendor,
            environment_name=ctx.environment_name,
        )
    )
    if not conn:
        raise ToolValidationError(f"No active {vendor} connector found for org")
    stored_vendor = str(conn.get("type") or conn.get("vendor") or "").strip().lower()
    if stored_vendor != vendor:
        raise ToolValidationError("Connector vendor mismatch")
    config = conn.get("config") if isinstance(conn.get("config"), dict) else {}
    if str(config.get("auth_provider") or "").strip().lower() != "managed":
        raise ToolValidationError(f"{vendor} connector is not using managed authorization")
    connection_id = str(config.get("managed_connection_id") or "").strip()
    integration_id = str(config.get("managed_integration_id") or "").strip()
    if not connection_id or not integration_id:
        raise ToolAuthExpiredError(f"{vendor} authorization is incomplete; reconnect the connector")
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, vendor, vendor, cid)
    return cid, connection_id, integration_id


def _request(
    ctx: ToolContext,
    params: dict[str, Any],
    *,
    vendor: str,
    endpoint: str,
    query: dict[str, Any] | None = None,
) -> tuple[str, Any]:
    cid, connection_id, integration_id = _managed_connector(ctx, vendor, params)
    try:
        response = proxy_request(
            ctx.settings,
            method="GET",
            endpoint=endpoint,
            connection_id=connection_id,
            integration_id=integration_id,
            params=query,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            raise ToolAuthExpiredError(
                f"{vendor} managed authorization was rejected by the provider"
            ) from exc
        raise ToolValidationError(
            f"{vendor} request failed ({exc.response.status_code}): {exc.response.text[:300]}"
        ) from exc
    except httpx.TimeoutException as exc:
        raise ToolError(f"{vendor} request timed out", code="connector_timeout") from exc
    except httpx.TransportError as exc:
        raise ToolError(f"{vendor} request failed: {exc}") from exc

    try:
        return cid, response.json() if response.content else {}
    except ValueError:
        return cid, {"raw": response.text[:2000]}


def _okta_system_logs_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    allowed = ("since", "until", "filter", "q", "limit", "sortOrder")
    query = {k: params[k] for k in allowed if params.get(k) is not None}
    cid, data = _request(
        ctx,
        params,
        vendor="okta",
        endpoint="/api/v1/logs",
        query=query or None,
    )
    events = data if isinstance(data, list) else data.get("events", []) if isinstance(data, dict) else []
    return NormalizedResult(
        success=True,
        action="okta.system_logs.list",
        connector_id=cid,
        data={"events": events, "count": len(events)},
    )


def _okta_users_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    user_id = params.get("user_id") or params.get("userId") or params.get("id")
    if not user_id:
        raise ToolValidationError("okta.users.get requires user_id")
    cid, data = _request(
        ctx,
        params,
        vendor="okta",
        endpoint=f"/api/v1/users/{user_id}",
    )
    user = data if isinstance(data, dict) else {"result": data}
    return NormalizedResult(
        success=True,
        action="okta.users.get",
        connector_id=cid,
        data={"user": user, "id": str(user.get("id") or user_id)},
    )


MANAGED_SECURITY_TOOL_EXECUTORS = {
    "okta.system_logs.list": _okta_system_logs_list,
    "okta.users.get": _okta_users_get,
}
