"""Finseo agent tool executors (BYO API key)."""
from __future__ import annotations

from typing import Any

from app.connectors.finseo_api import (
    FinseoAPIError,
    competitors_compare,
    exports_run,
    list_projects,
    metrics_overview,
    prompts_list,
    prompts_track,
    resolve_finseo_connector,
)
from app.connectors.rate_limit import enforce_rate_limit
from app.services.tool_types import (
    NormalizedResult,
    ToolAuthExpiredError,
    ToolContext,
    ToolRateLimitedError,
    ToolValidationError,
)


def _handle_error(exc: FinseoAPIError) -> Exception:
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
        cid, api_key = resolve_finseo_connector(
            ctx.client,
            ctx.org_id,
            str(connector_id) if connector_id else None,
            ctx.settings,
            environment_name=ctx.environment_name,
        )
    except FinseoAPIError as exc:
        raise _handle_error(exc) from exc
    enforce_rate_limit(ctx.client, ctx.org_id, "finseo", "finseo", cid)
    return cid, api_key


def _exec_projects_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    try:
        data = list_projects(api_key)
    except FinseoAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="finseo.projects.list", connector_id=cid, data=data)


def _exec_metrics_overview(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    project_id = str(params.get("project_id") or params.get("project") or "").strip() or None
    domain = str(params.get("domain") or params.get("target") or "").strip() or None
    timeframe = str(params.get("timeframe") or "30d").strip() or "30d"
    if not project_id and not domain:
        raise ToolValidationError("finseo.metrics.overview requires project_id or domain")
    try:
        data = metrics_overview(
            api_key, project_id=project_id, domain=domain, timeframe=timeframe
        )
    except FinseoAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="finseo.metrics.overview", connector_id=cid, data=data)


def _exec_prompts_list(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    project_id = str(params.get("project_id") or params.get("project") or "").strip()
    if not project_id:
        raise ToolValidationError("finseo.prompts.list requires project_id")
    try:
        data = prompts_list(api_key, project_id=project_id)
    except FinseoAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="finseo.prompts.list", connector_id=cid, data=data)


def _exec_prompts_track(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    project_id = str(params.get("project_id") or params.get("project") or "").strip()
    prompts = params.get("prompts")
    if isinstance(prompts, str) and prompts.strip():
        prompts = [prompts.strip()]
    if not isinstance(prompts, list):
        single = str(params.get("prompt") or "").strip()
        prompts = [single] if single else []
    if not project_id:
        raise ToolValidationError("finseo.prompts.track requires project_id")
    if not prompts:
        raise ToolValidationError("finseo.prompts.track requires prompts")
    try:
        data = prompts_track(api_key, project_id=project_id, prompts=[str(p) for p in prompts])
    except FinseoAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="finseo.prompts.track", connector_id=cid, data=data)


def _exec_competitors_compare(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    project_id = str(params.get("project_id") or params.get("project") or "").strip()
    timeframe = str(params.get("timeframe") or "30d").strip() or "30d"
    if not project_id:
        raise ToolValidationError("finseo.competitors.compare requires project_id")
    try:
        data = competitors_compare(api_key, project_id=project_id, timeframe=timeframe)
    except FinseoAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(
        success=True, action="finseo.competitors.compare", connector_id=cid, data=data
    )


def _exec_exports_run(ctx: ToolContext, params: dict[str, Any]) -> NormalizedResult:
    cid, api_key = _session(ctx, params)
    project_id = str(params.get("project_id") or params.get("project") or "").strip()
    if not project_id:
        raise ToolValidationError("finseo.exports.run requires project_id")
    try:
        data = exports_run(api_key, project_id=project_id)
    except FinseoAPIError as exc:
        raise _handle_error(exc) from exc
    return NormalizedResult(success=True, action="finseo.exports.run", connector_id=cid, data=data)


FINSEO_TOOL_EXECUTORS: dict[str, Any] = {
    "finseo.projects.list": _exec_projects_list,
    "finseo.metrics.overview": _exec_metrics_overview,
    "finseo.prompts.list": _exec_prompts_list,
    "finseo.prompts.track": _exec_prompts_track,
    "finseo.competitors.compare": _exec_competitors_compare,
    "finseo.exports.run": _exec_exports_run,
}
