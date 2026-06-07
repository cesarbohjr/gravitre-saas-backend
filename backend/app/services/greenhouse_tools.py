"""Greenhouse tool executors (STA-88)."""
from __future__ import annotations

from typing import Any

from app.connectors.greenhouse import (
    GreenhouseAPIError,
    get_candidate,
    list_applications,
    list_jobs,
    resolve_greenhouse_api_key,
)
from app.connectors.rate_limit import enforce_rate_limit
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolRateLimitedError,
    ToolValidationError,
)


def _handle_error(exc: GreenhouseAPIError) -> Exception:
    if exc.status_code == 429:
        return ToolRateLimitedError(str(exc))
    if exc.status_code in {401, 403}:
        return ToolAuthExpiredError(str(exc))
    return ToolValidationError(str(exc))


def _session(ctx: ToolContext, params: dict[str, Any]) -> tuple[str, str]:
    if ctx.settings.disable_connectors:
        raise ToolValidationError("Connectors are disabled")
    connector_id = params.get("connector_id") or ctx.connector_id
    try:
        cid, api_key = resolve_greenhouse_api_key(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except GreenhouseAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "greenhouse", "greenhouse", cid)
    return cid, api_key


def _exec_greenhouse_candidates_get(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    candidate_id = params.get("candidate_id") or params.get("candidateId")
    if not candidate_id:
        raise ToolValidationError("greenhouse.candidates.get requires candidate_id")
    try:
        data = get_candidate(api_key, str(candidate_id))
    except GreenhouseAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="greenhouse.candidates.get", connector_id=cid, data=data)


def _exec_greenhouse_applications_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    job_id = params.get("job_id") or params.get("jobId")
    try:
        data = list_applications(api_key, job_id=str(job_id) if job_id else None)
    except GreenhouseAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="greenhouse.applications.list", connector_id=cid, data=data)


def _exec_greenhouse_jobs_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    try:
        data = list_jobs(api_key)
    except GreenhouseAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="greenhouse.jobs.list", connector_id=cid, data=data)


GREENHOUSE_TOOL_EXECUTORS: dict[str, Any] = {
    "greenhouse.candidates.get": _exec_greenhouse_candidates_get,
    "greenhouse.applications.list": _exec_greenhouse_applications_list,
    "greenhouse.jobs.list": _exec_greenhouse_jobs_list,
}
