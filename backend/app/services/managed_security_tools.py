"""Managed/Nango security operations tool executors.

Nango owns managed authorization/proxying only. Gravitre retains tenant
isolation, permissions, audit, execution governance, and outcome truth.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.connectors.nango_client import proxy_request
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolError,
    ToolValidationError,
)


from app.services.managed_service_desk_tools import _managed_connector


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
            f"{vendor} request failed ({exc.response.status_code})"
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
        endpoint=f"/api/v1/users/{quote(str(user_id), safe='')}",
    )
    user = data if isinstance(data, dict) else {"result": data}
    return NormalizedResult(
        success=True,
        action="okta.users.get",
        connector_id=cid,
        data={"user": user, "id": str(user.get("id") or user_id)},
    )


def _okta_groups_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    allowed = ("q", "filter", "search", "limit", "after")
    query = {k: params[k] for k in allowed if params.get(k) is not None}
    cid, data = _request(
        ctx,
        params,
        vendor="okta",
        endpoint="/api/v1/groups",
        query=query or None,
    )
    groups = data if isinstance(data, list) else data.get("groups", []) if isinstance(data, dict) else []
    return NormalizedResult(
        success=True,
        action="okta.groups.list",
        connector_id=cid,
        data={"groups": groups, "count": len(groups)},
    )


def _okta_apps_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    allowed = ("q", "filter", "limit", "after")
    query = {k: params[k] for k in allowed if params.get(k) is not None}
    cid, data = _request(
        ctx,
        params,
        vendor="okta",
        endpoint="/api/v1/apps",
        query=query or None,
    )
    apps = data if isinstance(data, list) else data.get("apps", []) if isinstance(data, dict) else []
    return NormalizedResult(
        success=True,
        action="okta.apps.list",
        connector_id=cid,
        data={"apps": apps, "count": len(apps)},
    )


def _okta_user_factors_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    user_id = params.get("user_id") or params.get("userId") or params.get("id")
    if not user_id:
        raise ToolValidationError("okta.users.factors.list requires user_id")
    cid, data = _request(
        ctx,
        params,
        vendor="okta",
        endpoint=f"/api/v1/users/{quote(str(user_id), safe='')}/factors",
    )
    factors = data if isinstance(data, list) else data.get("factors", []) if isinstance(data, dict) else []
    return NormalizedResult(
        success=True,
        action="okta.users.factors.list",
        connector_id=cid,
        data={"factors": factors, "count": len(factors), "user_id": str(user_id)},
    )


MANAGED_SECURITY_TOOL_EXECUTORS = {
    "okta.system_logs.list": _okta_system_logs_list,
    "okta.users.get": _okta_users_get,
    "okta.groups.list": _okta_groups_list,
    "okta.apps.list": _okta_apps_list,
    "okta.users.factors.list": _okta_user_factors_list,
}

