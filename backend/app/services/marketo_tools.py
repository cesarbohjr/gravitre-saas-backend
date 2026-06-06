"""Marketo tool executors for agent/workflow invoke (STA-65)."""
from __future__ import annotations

from typing import Any

from app.connectors.marketo import (
    MarketoAPIError,
    add_to_static_list,
    get_lead,
    get_program_status,
    list_campaigns,
    update_leads,
)
from app.connectors.marketo_oauth import ensure_marketo_session
from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.repository import get_connector, get_connector_by_type
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolRateLimitedError,
    ToolValidationError,
)

ToolExecutor = Any  # Callable[[ToolContext, dict[str, Any]], NormalizedResult]


def _handle_marketo_error(exc: MarketoAPIError) -> Exception:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _marketo_connector_and_session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str, str]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    else:
        conn = get_connector_by_type(ctx.client, ctx.org_id, "marketo", environment_name=ctx.environment_name)
    if not conn:
        raise ToolValidationError("No active Marketo connector found for org")
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, "marketo", "marketo", cid)
    token, munchkin_id, err = ensure_marketo_session(
        ctx.client,
        ctx.org_id,
        cid,
        ctx.settings,
        environment_name=conn.get("environment") or ctx.environment_name,
    )
    if err or not token or not munchkin_id:
        raise ToolAuthExpiredError(err or "Marketo OAuth not connected")
    return cid, token, munchkin_id


def _exec_marketo_leads_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, munchkin_id = _marketo_connector_and_session(ctx, params)
    try:
        data = get_lead(
            token,
            munchkin_id,
            lead_id=params.get("lead_id") or params.get("leadId"),
            email=params.get("email"),
            filter_type=params.get("filter_type") or params.get("filterType"),
            filter_values=params.get("filter_values") or params.get("filterValues"),
        )
    except MarketoAPIError as exc:
        raise _handle_marketo_error(exc) from exc
    return NormalizedResult(success=True, action="marketo.leads.get", connector_id=cid, data=data)


def _exec_marketo_leads_update(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, munchkin_id = _marketo_connector_and_session(ctx, params)
    leads = params.get("leads") or params.get("input")
    if not isinstance(leads, list) or not leads:
        raise ToolValidationError("marketo.leads.update requires leads array")
    action = str(params.get("action") or "updateOnly")
    try:
        data = update_leads(
            token,
            munchkin_id,
            action=action,
            leads=leads,
            lookup_field=str(params.get("lookup_field") or params.get("lookupField") or "email"),
            async_request=bool(params.get("async") or params.get("asyncProcessing")),
        )
    except MarketoAPIError as exc:
        raise _handle_marketo_error(exc) from exc
    return NormalizedResult(success=True, action="marketo.leads.update", connector_id=cid, data=data)


def _exec_marketo_campaigns_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, munchkin_id = _marketo_connector_and_session(ctx, params)
    try:
        data = list_campaigns(
            token,
            munchkin_id,
            is_request=params.get("is_request") if "is_request" in params else params.get("isRequest"),
            offset=params.get("offset"),
            max_return=params.get("max_return") or params.get("maxReturn"),
        )
    except MarketoAPIError as exc:
        raise _handle_marketo_error(exc) from exc
    return NormalizedResult(success=True, action="marketo.campaigns.list", connector_id=cid, data=data)


def _exec_marketo_programs_status(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, munchkin_id = _marketo_connector_and_session(ctx, params)
    program_id = params.get("program_id") or params.get("programId")
    if not program_id:
        raise ToolValidationError("marketo.programs.status requires program_id")
    try:
        data = get_program_status(token, munchkin_id, program_id)
    except MarketoAPIError as exc:
        raise _handle_marketo_error(exc) from exc
    return NormalizedResult(success=True, action="marketo.programs.status", connector_id=cid, data=data)


def _exec_marketo_lists_add_to_static_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, munchkin_id = _marketo_connector_and_session(ctx, params)
    list_id = params.get("list_id") or params.get("listId")
    if not list_id:
        raise ToolValidationError("marketo.lists.add_to_static_list requires list_id")
    lead_ids = params.get("lead_ids") or params.get("leadIds")
    emails = params.get("emails")
    try:
        data = add_to_static_list(
            token,
            munchkin_id,
            list_id,
            lead_ids=lead_ids if isinstance(lead_ids, list) else None,
            emails=emails if isinstance(emails, list) else None,
        )
    except MarketoAPIError as exc:
        raise _handle_marketo_error(exc) from exc
    return NormalizedResult(success=True, action="marketo.lists.add_to_static_list", connector_id=cid, data=data)


TOOL_EXECUTORS: dict[str, ToolExecutor] = {
    "marketo.leads.get": _exec_marketo_leads_get,
    "marketo.leads.update": _exec_marketo_leads_update,
    "marketo.campaigns.list": _exec_marketo_campaigns_list,
    "marketo.programs.status": _exec_marketo_programs_status,
    "marketo.lists.add_to_static_list": _exec_marketo_lists_add_to_static_list,
}
