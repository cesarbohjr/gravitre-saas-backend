"""BambooHR tool executors (STA-87)."""
from __future__ import annotations

from typing import Any

from app.connectors.bamboohr import (
    BambooHRAPIError,
    _api_base,
    get_employee,
    list_employees,
    list_time_off_requests,
    resolve_bamboohr_credentials,
    run_report,
)
from app.connectors.rate_limit import enforce_rate_limit
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolRateLimitedError,
    ToolValidationError,
)


def _handle_error(exc: BambooHRAPIError) -> Exception:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str, str]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    try:
        cid, subdomain, api_key = resolve_bamboohr_credentials(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except BambooHRAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "bamboohr", "bamboohr", cid)
    return cid, _api_base(subdomain), api_key


def _exec_bamboohr_employees_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, base, api_key = _session(ctx, params)
    employee_id = params.get("employee_id") or params.get("employeeId")
    if not employee_id:
        raise ToolValidationError("bamboohr.employees.get requires employee_id")
    try:
        data = get_employee(base, api_key, str(employee_id))
    except BambooHRAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="bamboohr.employees.get", connector_id=cid, data=data)


def _exec_bamboohr_employees_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, base, api_key = _session(ctx, params)
    try:
        data = list_employees(base, api_key)
    except BambooHRAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="bamboohr.employees.list", connector_id=cid, data=data)


def _exec_bamboohr_timeoff_requests_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, base, api_key = _session(ctx, params)
    try:
        data = list_time_off_requests(base, api_key)
    except BambooHRAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True,
        action="bamboohr.timeoff.requests.list",
        connector_id=cid,
        data=data,
    )


def _exec_bamboohr_reports_run(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, base, api_key = _session(ctx, params)
    report_id = params.get("report_id") or params.get("reportId") or "1"
    try:
        data = run_report(base, api_key, str(report_id))
    except BambooHRAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="bamboohr.reports.run", connector_id=cid, data=data)


BAMBOOHR_TOOL_EXECUTORS: dict[str, Any] = {
    "bamboohr.employees.get": _exec_bamboohr_employees_get,
    "bamboohr.employees.list": _exec_bamboohr_employees_list,
    "bamboohr.timeoff.requests.list": _exec_bamboohr_timeoff_requests_list,
    "bamboohr.reports.run": _exec_bamboohr_reports_run,
}
