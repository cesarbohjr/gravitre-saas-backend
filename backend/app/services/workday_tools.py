"""Workday HRIS tool executors (STA-60)."""
from __future__ import annotations

from typing import Any

from app.connectors.rate_limit import enforce_rate_limit
from app.connectors.repository import get_connector, get_connector_by_type
from app.connectors.workday import (
    WorkdayAPIError,
    get_timeoff_balance,
    get_worker,
    list_org_units,
    list_positions,
)
from app.connectors.workday_oauth import ensure_workday_session
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolError,
    ToolRateLimitedError,
    ToolValidationError,
)


def _workday_connector_and_session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str, str]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    conn = None
    if connector_id:
        conn = get_connector(ctx.client, ctx.org_id, str(connector_id), environment_name=ctx.environment_name)
    else:
        conn = get_connector_by_type(ctx.client, ctx.org_id, "workday", environment_name=ctx.environment_name)
    if not conn:
        raise ToolValidationError("No active Workday connector found for org")
    cid = str(conn["id"])
    enforce_rate_limit(ctx.client, ctx.org_id, ctx.step_type or "workday", "workday", cid)
    token, _tenant_url, _tenant, api_base, err = ensure_workday_session(
        ctx.client,
        ctx.org_id,
        cid,
        ctx.settings,
        environment_name=conn.get("environment") or ctx.environment_name,
    )
    if err or not token or not api_base:
        raise ToolAuthExpiredError(err or "Workday OAuth not connected")
    return cid, token, api_base


def _handle_workday_error(exc: WorkdayAPIError) -> ToolError:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _exec_workday_workers_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _workday_connector_and_session(ctx, params)
    worker_id = params.get("worker_id") or params.get("workerId") or params.get("id")
    email = params.get("email")
    if not worker_id and not email:
        raise ToolValidationError("workday.workers.get requires worker_id or email")
    try:
        data = get_worker(
            api_base,
            token,
            worker_id=str(worker_id) if worker_id else None,
            email=str(email) if email else None,
        )
    except WorkdayAPIError as exc:
        raise _handle_workday_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="workday.workers.get",
        connector_id=cid,
        data={"worker": data},
    )


def _exec_workday_orgunits_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _workday_connector_and_session(ctx, params)
    try:
        data = list_org_units(
            api_base,
            token,
            limit=int(params.get("limit") or params.get("max_results") or 100),
            search=params.get("search") or params.get("q"),
        )
    except WorkdayAPIError as exc:
        raise _handle_workday_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="workday.orgunits.list",
        connector_id=cid,
        data=data,
    )


def _exec_workday_timeoff_balance_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _workday_connector_and_session(ctx, params)
    worker_id = params.get("worker_id") or params.get("workerId")
    if not worker_id:
        raise ToolValidationError("workday.timeoff.balance.get requires worker_id")
    time_off_plan_id = params.get("time_off_plan_id") or params.get("timeOffPlanId")
    try:
        data = get_timeoff_balance(
            api_base,
            token,
            worker_id=str(worker_id),
            time_off_plan_id=str(time_off_plan_id) if time_off_plan_id else None,
        )
    except WorkdayAPIError as exc:
        raise _handle_workday_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="workday.timeoff.balance.get",
        connector_id=cid,
        data=data,
    )


def _exec_workday_positions_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, token, api_base = _workday_connector_and_session(ctx, params)
    try:
        data = list_positions(
            api_base,
            token,
            limit=int(params.get("limit") or params.get("max_results") or 50),
            status=params.get("status") or "OPEN",
        )
    except WorkdayAPIError as exc:
        raise _handle_workday_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="workday.positions.list",
        connector_id=cid,
        data=data,
    )


WORKDAY_TOOL_EXECUTORS: dict[str, Any] = {
    "workday.workers.get": _exec_workday_workers_get,
    "workday.orgunits.list": _exec_workday_orgunits_list,
    "workday.timeoff.balance.get": _exec_workday_timeoff_balance_get,
    "workday.positions.list": _exec_workday_positions_list,
}
